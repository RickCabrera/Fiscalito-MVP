"""
CFDI de retenciones de un cliente: de la bóveda al XML timbrado (P3-04).

FLUJO
-----
1. `terceros_del_periodo`: los CFDI RECIBIDOS del cliente pagados en el periodo (flujo de
   efectivo, `app/impuestos/flujo.py`: la retención se hace al pagar — Art. 1o.-A LIVA,
   Art. 106 último párrafo LISR) pasan por el motor existente
   `fiscal_engine/retenciones.generar_resumen_retenciones`, que los agrupa por tercero. Aquí
   no se suma ningún impuesto por fuera del motor.
2. `emitir`: arma el XML 2.0 (`generador.armar`), lo sella con el CSD del cliente, lo VALIDA
   contra el XSD (si no valida no se manda al PAC), lo timbra con el PAC configurado
   (`FISCALITO_PAC`) y guarda el XML timbrado en el almacenamiento de la bóveda.
3. `cancelar`: por el mismo PAC; guarda el acuse.

DECISIONES PROVISIONALES (configurables por petición)
-----------------------------------------------------
- `CveRetenc` por régimen del tercero (RegimenFiscal del emisor del CFDI): 606 → 05
  Arrendamiento; 625 → 26 Plataformas; cualquier otro → 01 Servicios profesionales. El
  despacho la cambia por tercero en la petición.
- `DomicilioFiscalR`: el `LugarExpedicion` del CFDI más reciente del tercero (en una persona
  física suele coincidir con su domicilio fiscal; no siempre). Se puede capturar por tercero.
- `TipoPagoRet`: ISR → 04 Pago provisional ISR; IVA → 01 Pago definitivo IVA.
- Monto gravado = monto de la operación (ISR); exento = 0.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from lxml import etree
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.boveda_cfdi.servicio import rfc_del_cliente
from app.credenciales.servicio import obtener_firmante
from app.exceptions import FiscalAgentError
from app.fiscal_engine.retenciones import generar_resumen_retenciones
from app.impuestos.flujo import Efectivo, flujo_del_mes
from app.impuestos.servicio import _como_cfdi
from app.integraciones.almacenamiento import Almacenamiento, obtener_almacenamiento
from app.integraciones.pac import Pac, obtener_pac
from app.modelos.nucleo import Cliente
from app.modelos.retenciones_cfdi import CfdiRetencion
from app.retenciones_cfdi import esquemas, generador

ZONA = ZoneInfo("America/Mexico_City")
CVE_POR_REGIMEN = {"606": "05", "625": "26"}
CERO = Decimal("0.00")


@dataclass
class Tercero:
    """Un tercero al que el cliente retuvo en el periodo."""

    rfc: str
    nombre: str
    regimen: str
    domicilio_fiscal: str
    monto_operacion: Decimal
    isr_retenido: Decimal
    iva_retenido: Decimal
    cantidad_cfdi: int
    uuids: list[str] = field(default_factory=list)

    @property
    def cve_retenc_sugerida(self) -> str:
        return CVE_POR_REGIMEN.get(self.regimen, "01")

    def a_dict(self) -> dict[str, Any]:
        return {
            "rfc": self.rfc, "nombre": self.nombre, "regimen": self.regimen,
            "domicilio_fiscal": self.domicilio_fiscal,
            "monto_operacion": str(self.monto_operacion), "isr_retenido": str(self.isr_retenido),
            "iva_retenido": str(self.iva_retenido), "cantidad_cfdi": self.cantidad_cfdi,
            "cve_retenc_sugerida": self.cve_retenc_sugerida, "uuids": self.uuids,
        }


def _dec(v: float) -> Decimal:
    return Decimal(str(v)).quantize(Decimal("0.01"))


def terceros_del_periodo(
    db: Session, cliente: Cliente, ejercicio: int, mes_ini: int, mes_fin: int
) -> list[Tercero]:
    """Terceros con ISR o IVA retenido en los CFDI recibidos y pagados en el periodo."""
    if not (1 <= mes_ini <= mes_fin <= 12):
        raise FiscalAgentError("El periodo va de MesIni a MesFin, entre 1 y 12.", 422)
    rfc = rfc_del_cliente(cliente)
    if not rfc:
        raise FiscalAgentError("Captura el RFC de este cliente.", 422)
    efectivos: list[Efectivo] = []
    for mes in range(mes_ini, mes_fin + 1):
        efectivos += [e for e in flujo_del_mes(db, cliente, ejercicio, mes)
                      if e.comprobante.direccion == "recibido"]
    resumen = generar_resumen_retenciones(rfc, [_como_cfdi(e) for e in efectivos])
    por_rfc: dict[str, list[Efectivo]] = {}
    for e in efectivos:
        por_rfc.setdefault(e.comprobante.rfc_emisor.upper(), []).append(e)
    salida = []
    for t in resumen:
        comps = sorted((e.comprobante for e in por_rfc.get(t.rfc, [])), key=lambda c: c.fecha)
        ultimo = comps[-1] if comps else None
        datos = (ultimo.datos or {}) if ultimo else {}
        salida.append(Tercero(
            rfc=t.rfc, nombre=(ultimo.nombre_emisor if ultimo else "") or t.nombre,
            regimen=str(datos.get("emisor", {}).get("RegimenFiscal", "")),
            domicilio_fiscal=str(datos.get("lugar_expedicion", "")),
            monto_operacion=_dec(t.total_pagado), isr_retenido=_dec(t.isr_retenido),
            iva_retenido=_dec(t.iva_retenido), cantidad_cfdi=t.cantidad_facturas,
            uuids=sorted({c.uuid for c in comps}),
        ))
    return sorted(salida, key=lambda t: t.rfc)


@dataclass
class OpcionesEmision:
    """Lo que el despacho puede ajustar por tercero antes de timbrar."""

    cve_retenc: str | None = None
    desc_retenc: str = ""
    domicilio_fiscal: str | None = None
    nombre: str | None = None


def datos_retencion(
    cliente: Cliente, t: Tercero, ejercicio: int, mes_ini: int, mes_fin: int,
    op: OpcionesEmision,
) -> generador.DatosRetencion:
    """El tercero ya agrupado → los datos del comprobante. 422 si falta algo obligatorio."""
    datos = cliente.datos or {}
    regimen = str(datos.get("regimen") or "")
    cp = str(datos.get("codigo_postal") or "")
    domicilio = (op.domicilio_fiscal or t.domicilio_fiscal or "").strip()
    faltan = [n for n, v in (("régimen del cliente", regimen), ("código postal del cliente", cp),
                             (f"domicilio fiscal (CP) del tercero {t.rfc}", domicilio)) if not v]
    if faltan:
        raise FiscalAgentError("Falta capturar: " + ", ".join(faltan) + ".", 422)
    impuestos = []
    if t.isr_retenido > 0:
        impuestos.append(generador.ImpuestoRetenido("001", t.monto_operacion, t.isr_retenido,
                                                    "04"))
    if t.iva_retenido > 0:
        impuestos.append(generador.ImpuestoRetenido("002", t.monto_operacion, t.iva_retenido,
                                                    "01"))
    return generador.DatosRetencion(
        rfc_emisor=rfc_del_cliente(cliente), nombre_emisor=(cliente.nombre or "").upper(),
        regimen_emisor=regimen, lugar_expedicion=cp, rfc_receptor=t.rfc,
        nombre_receptor=(op.nombre or t.nombre or t.rfc).upper(), domicilio_receptor=domicilio,
        ejercicio=ejercicio, mes_ini=mes_ini, mes_fin=mes_fin,
        cve_retenc=op.cve_retenc or t.cve_retenc_sugerida, desc_retenc=op.desc_retenc,
        monto_operacion=t.monto_operacion, monto_gravado=t.monto_operacion,
        monto_exento=CERO, impuestos=impuestos,
        fecha_expedicion=datetime.now(ZONA).replace(tzinfo=None, microsecond=0),
    )


def ruta_xml(cliente: Cliente, uuid: str, sufijo: str = "") -> str:
    return f"retenciones/{cliente.despacho_id}/{cliente.id}/{uuid}{sufijo}.xml"


def emitir(
    db: Session, cliente: Cliente, rfc_tercero: str, ejercicio: int, mes_ini: int, mes_fin: int,
    op: OpcionesEmision, usuario: str, pac: Pac | None = None,
    almacen: Almacenamiento | None = None,
) -> CfdiRetencion:
    """Arma, sella, valida, timbra y guarda el CFDI de retenciones de un tercero."""
    terceros = {t.rfc: t for t in terceros_del_periodo(db, cliente, ejercicio, mes_ini, mes_fin)}
    t = terceros.get(rfc_tercero.upper())
    if t is None:
        raise FiscalAgentError(
            f"No hay retenciones a {rfc_tercero} en el periodo en la bóveda del cliente.", 404)
    datos = datos_retencion(cliente, t, ejercicio, mes_ini, mes_fin, op)
    doc = generador.armar(datos)
    generador.sellar(doc, obtener_firmante(db, cliente, "csd"))
    errores = esquemas.validar(doc)
    if errores:
        raise FiscalAgentError("El CFDI de retenciones no valida contra el XSD del SAT: "
                               + "; ".join(errores[:5]), 422)
    pac = pac or obtener_pac()
    timbre = pac.timbrar(generador.a_bytes(doc), "retenciones")
    errores = esquemas.validar(etree.fromstring(timbre.xml_timbrado))
    if errores:
        raise FiscalAgentError("El PAC devolvió un XML que no valida: " + "; ".join(errores[:5]),
                               502)
    almacen = almacen or obtener_almacenamiento()
    ruta = almacen.guardar(timbre.xml_timbrado, ruta_xml(cliente, timbre.uuid))
    fecha = timbre.fecha if timbre.fecha.tzinfo else timbre.fecha.replace(tzinfo=ZONA)
    registro = CfdiRetencion(
        cliente_id=cliente.id, uuid=timbre.uuid, rfc_tercero=t.rfc,
        nombre_tercero=datos.nombre_receptor, ejercicio=ejercicio, mes_ini=mes_ini,
        mes_fin=mes_fin, cve_retenc=datos.cve_retenc, monto_operacion=t.monto_operacion,
        isr_retenido=t.isr_retenido, iva_retenido=t.iva_retenido, estado="timbrado",
        pac=getattr(pac, "nombre", ""), es_prueba=getattr(pac, "nombre", "") == "falso",
        fecha_timbrado=fecha, ruta_xml=ruta,
        sha256=hashlib.sha256(timbre.xml_timbrado).hexdigest(), creado_por=usuario,
        datos={"uuids_origen": t.uuids, "cantidad_cfdi": t.cantidad_cfdi},
    )
    db.add(registro)
    db.flush()
    return registro


def obtener(db: Session, cliente: Cliente, uuid: str) -> CfdiRetencion:
    fila = db.scalar(select(CfdiRetencion).where(
        CfdiRetencion.cliente_id == cliente.id, CfdiRetencion.uuid == uuid.upper()))
    if fila is None:
        raise FiscalAgentError("No existe ese CFDI de retenciones en este cliente.", 404)
    return fila


def listar(db: Session, cliente: Cliente, ejercicio: int | None = None) -> list[CfdiRetencion]:
    q = select(CfdiRetencion).where(CfdiRetencion.cliente_id == cliente.id)
    if ejercicio is not None:
        q = q.where(CfdiRetencion.ejercicio == ejercicio)
    return list(db.scalars(q.order_by(CfdiRetencion.ejercicio.desc(),
                                      CfdiRetencion.mes_ini.desc(), CfdiRetencion.rfc_tercero)))


def cancelar(
    db: Session, cliente: Cliente, uuid: str, motivo: str, folio_sustitucion: str | None,
    pac: Pac | None = None, almacen: Almacenamiento | None = None,
) -> CfdiRetencion:
    """Cancela con el PAC y guarda el acuse. 409 si ya estaba cancelado."""
    fila = obtener(db, cliente, uuid)
    if fila.estado == "cancelado":
        raise FiscalAgentError("Ese CFDI de retenciones ya está cancelado.", 409)
    pac = pac or obtener_pac()
    firmante = obtener_firmante(db, cliente, "csd") if pac.nombre == "finkok" else None
    try:
        acuse = pac.cancelar(fila.uuid, rfc_del_cliente(cliente), motivo, folio_sustitucion,
                             tipo="retenciones", firmante=firmante)
    except ValueError as e:
        raise FiscalAgentError(str(e), 422) from e
    if acuse.estatus == "rechazado":
        raise FiscalAgentError(f"El PAC rechazó la cancelación: {acuse.codigo} {acuse.mensaje}",
                               422)
    if acuse.acuse_xml:
        almacen = almacen or obtener_almacenamiento()
        fila.ruta_acuse = almacen.guardar(acuse.acuse_xml, ruta_xml(cliente, fila.uuid, "-acuse"))
    fila.estado = "cancelado" if acuse.estatus == "cancelado" else "cancelacion_en_proceso"
    fila.motivo_cancelacion = motivo
    db.flush()
    return fila


def fila_json(f: CfdiRetencion) -> dict[str, Any]:
    return {
        "uuid": f.uuid, "rfc_tercero": f.rfc_tercero, "nombre_tercero": f.nombre_tercero,
        "ejercicio": f.ejercicio, "mes_ini": f.mes_ini, "mes_fin": f.mes_fin,
        "cve_retenc": f.cve_retenc, "monto_operacion": str(f.monto_operacion),
        "isr_retenido": str(f.isr_retenido), "iva_retenido": str(f.iva_retenido),
        "estado": f.estado, "pac": f.pac, "es_prueba": f.es_prueba,
        "fecha_timbrado": f.fecha_timbrado.isoformat(), "motivo_cancelacion":
        f.motivo_cancelacion,
    }
