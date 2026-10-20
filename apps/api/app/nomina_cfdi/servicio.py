"""
Timbrado y cancelación del CFDI de nómina por el adaptador de PAC (P4-11).

FLUJO DE UN RECIBO
------------------
1. `armado.armar`: datos del CFDI desde el recibo guardado (422 con lo que falte capturar).
2. `cfdi_nomina_xml.generar_cfdi_nomina` (el generador existente, extendido) → XML.
3. Sellado: `NoCertificado`, `Certificado` y `Sello` = SHA256withRSA sobre la cadena original
   del XSLT oficial con el CSD del cliente (`obtener_firmante(db, cliente, "csd")`, Anexo 20).
4. Validación contra los XSD oficiales: si no valida NO se manda al PAC.
5. `pac.timbrar` (FISCALITO_PAC; el falso devuelve un TFD sintético marcado NO FISCAL).
6. El XML timbrado entra a la bóveda del cliente (`boveda_cfdi.servicio.importar`, origen
   `nomina`) y su UUID a `ReciboNomina.uuid_cfdi`.

NÓMINA COMPLETA EN SEGUNDO PLANO
--------------------------------
`solicitar` deja un `CfdiNomina` pendiente por recibo y encola `nomina.timbrar_periodo`
(clave única por periodo). El manejador es idempotente: salta lo ya timbrado. Un rechazo del
PAC o un dato faltante es PERMANENTE (estado `error`, no se reintenta solo: hay que corregir y
volver a pedir); una caída de red es TRANSITORIA (`reintento`): el trabajo levanta al final y
la cola lo reintenta con backoff. Cada recibo se confirma en la base al terminar, así que un
reintento no vuelve a timbrar lo que ya quedó.
"""

from __future__ import annotations

import hashlib
import io
import zipfile
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app import nomina_servicio as srv
from app.boveda_cfdi import servicio as boveda
from app.credenciales.servicio import obtener_firmante
from app.exceptions import FiscalAgentError
from app.integraciones.almacenamiento import obtener_almacenamiento
from app.integraciones.comun import ErrorServicioExterno
from app.integraciones.pac import ErrorTimbrado, Pac, obtener_pac
from app.modelos.cfdi import Comprobante
from app.modelos.imss import CfdiNomina
from app.modelos.nomina import NominaPeriodo, ReciboNomina
from app.modelos.nucleo import Cliente
from app.modelos.trabajos import Trabajo
from app.nomina_cfdi import armado, esquemas
from app.nomina_engine.cfdi_nomina_xml import generar_cfdi_nomina
from app.trabajos.cola import encolar, manejador

ZONA = ZoneInfo("America/Mexico_City")
SERIE = "NOM"
TIPO_TRABAJO = "nomina.timbrar_periodo"
VIGENTES = ("timbrado", "cancelacion_en_proceso")


def generar_xml(datos: armado.DatosCfdi, folio: str, fecha: datetime | None = None) -> bytes:
    """El XML SIN sellar (los centinelas del generador se sustituyen al sellar)."""
    texto = generar_cfdi_nomina(
        recibo=datos.recibo, patron=datos.patron, trabajador=datos.trabajador,
        fecha_emision=fecha or datetime.now(ZONA).replace(tzinfo=None, microsecond=0),
        fecha_inicial_pago=datos.inicio, fecha_final_pago=datos.fin, fecha_pago=datos.pago,
        dias_pagados=datos.dias_pagados, tipo_nomina=datos.tipo_nomina, serie=SERIE,
        folio=folio, extras=datos.extras,
    )
    return texto.encode("utf-8")


def sellar(xml: bytes, firmante: Any) -> tuple[bytes, str]:
    """XML sellado con el CSD y su cadena original."""
    doc = esquemas.parsear(xml)
    doc.set("NoCertificado", firmante.numero_certificado)
    doc.set("Certificado", firmante.certificado_base64)
    cadena = esquemas.cadena_original(doc)
    doc.set("Sello", firmante.firmar_base64(cadena.encode("utf-8"), "sha256"))
    from lxml import etree

    return etree.tostring(doc, xml_declaration=True, encoding="UTF-8"), cadena


def periodo_de(db: Session, cliente: Cliente, periodo_id: int) -> NominaPeriodo:
    return srv.periodo_o_404(db, cliente, periodo_id)


def cfdi_de(db: Session, periodo: NominaPeriodo) -> list[CfdiNomina]:
    return list(db.scalars(select(CfdiNomina).where(CfdiNomina.periodo_id == periodo.id)
                           .order_by(CfdiNomina.empleado_no, CfdiNomina.id)))


def _ultimo_por_recibo(db: Session, periodo: NominaPeriodo) -> dict[int, CfdiNomina]:
    salida: dict[int, CfdiNomina] = {}
    for c in cfdi_de(db, periodo):
        salida[c.recibo_id] = c  # el de id mayor gana
    return salida


def solicitar(db: Session, cliente: Cliente, periodo: NominaPeriodo, uid: str) -> Trabajo:
    """Deja pendiente cada recibo sin CFDI vigente y encola el trabajo del periodo."""
    if periodo.estado not in ("cerrada", "timbrada"):
        raise FiscalAgentError("Cierra la nómina antes de timbrarla.", status_code=409)
    ultimos = _ultimo_por_recibo(db, periodo)
    for rec in srv.recibos_de(db, periodo):
        previo = ultimos.get(rec.id)
        if previo is not None and previo.estado in (*VIGENTES, "pendiente", "reintento"):
            continue
        if previo is not None and previo.estado == "error":
            previo.estado, previo.error = "pendiente", ""
            continue
        db.add(CfdiNomina(cliente_id=cliente.id, periodo_id=periodo.id, recibo_id=rec.id,
                          empleado_no=rec.empleado_no, estado="pendiente", serie=SERIE,
                          folio=f"{periodo.id}-{rec.id}", total=rec.neto, creado_por=uid))
    db.flush()
    return encolar(db, TIPO_TRABAJO, {"periodo_id": periodo.id}, despacho_id=cliente.despacho_id,
                   cliente_id=cliente.id, clave_unica=f"nomina-timbrar-{periodo.id}",
                   max_intentos=5)


def timbrar_uno(
    db: Session, cliente: Cliente, periodo: NominaPeriodo, c: CfdiNomina,
    fichas: dict[str, Any], pac: Pac,
) -> None:
    """Timbra un recibo. Deja el estado en `c` (timbrado | error | reintento)."""
    rec = db.get(ReciboNomina, c.recibo_id)
    assert rec is not None
    c.intentos += 1
    try:
        datos = armado.armar(cliente, periodo, rec, fichas.get(rec.empleado_no))
        xml, _ = sellar(generar_xml(datos, c.folio), obtener_firmante(db, cliente, "csd"))
        errores = esquemas.validar(esquemas.parsear(xml))
        if errores:
            raise FiscalAgentError(
                "No valida contra el XSD del SAT: " + "; ".join(errores[:3]), 422)
        timbre = pac.timbrar(xml, "cfdi")
    except ErrorTimbrado as e:
        c.estado, c.error = "error", f"El PAC rechazó el comprobante: {e}"
        return
    except ErrorServicioExterno as e:
        c.estado, c.error = "reintento", f"PAC no disponible: {e}"
        return
    except FiscalAgentError as e:
        c.estado, c.error = "error", e.message
        return
    almacen = obtener_almacenamiento()
    nombre = f"nomina-{timbre.uuid}.xml"
    boveda.importar(db, cliente, [(nombre, io.BytesIO(timbre.xml_timbrado))], almacen,
                    origen="nomina", rfc=datos.patron.rfc, detalle=False)
    fecha = timbre.fecha if timbre.fecha.tzinfo else timbre.fecha.replace(tzinfo=ZONA)
    c.estado, c.error, c.uuid = "timbrado", "", timbre.uuid
    c.pac, c.es_prueba = getattr(pac, "nombre", ""), getattr(pac, "nombre", "") == "falso"
    c.fecha_timbrado, c.total = fecha, datos.recibo.total
    c.ruta_xml = boveda.ruta_del_xml(cliente, timbre.uuid)
    c.sha256 = hashlib.sha256(timbre.xml_timbrado).hexdigest()
    rec.uuid_cfdi = timbre.uuid


def resumen(db: Session, periodo: NominaPeriodo) -> dict[str, int]:
    cuenta: dict[str, int] = {}
    for c in _ultimo_por_recibo(db, periodo).values():
        cuenta[c.estado] = cuenta.get(c.estado, 0) + 1
    return cuenta


def _actualizar_estado_periodo(db: Session, periodo: NominaPeriodo) -> None:
    recibos = srv.recibos_de(db, periodo)
    ultimos = _ultimo_por_recibo(db, periodo)
    completos = recibos and all(
        ultimos.get(r.id) is not None and ultimos[r.id].estado in VIGENTES for r in recibos)
    if completos:
        periodo.estado = "timbrada"
    elif periodo.estado == "timbrada":
        periodo.estado = "cerrada"


@manejador(TIPO_TRABAJO)
def timbrar_periodo(db: Session, trabajo: Trabajo) -> dict[str, Any]:
    """Timbra los recibos pendientes del periodo. Idempotente."""
    periodo = db.get(NominaPeriodo, int(trabajo.carga["periodo_id"]))
    if periodo is None:
        return {"omitido": "el periodo ya no existe"}
    cliente = db.get(Cliente, periodo.cliente_id)
    assert cliente is not None
    fichas = {f.empleado_no: f for f in srv.fichas_del_cliente(db, cliente)[0]}
    pac = obtener_pac()
    pendientes = [c for c in _ultimo_por_recibo(db, periodo).values()
                  if c.estado in ("pendiente", "reintento")]
    for c in pendientes:
        timbrar_uno(db, cliente, periodo, c, fichas, pac)
        db.commit()  # cada recibo queda firme: un reintento no lo vuelve a timbrar
    _actualizar_estado_periodo(db, periodo)
    db.commit()
    estado = resumen(db, periodo)
    if estado.get("reintento"):
        raise RuntimeError(f"{estado['reintento']} recibo(s) sin timbrar por falla del PAC; "
                           "se reintenta.")
    return {"periodo_id": periodo.id, "por_estado": estado}


def obtener(db: Session, periodo: NominaPeriodo, cfdi_id: int) -> CfdiNomina:
    c = db.scalar(select(CfdiNomina).where(CfdiNomina.id == cfdi_id,
                                           CfdiNomina.periodo_id == periodo.id))
    if c is None:
        raise FiscalAgentError("No existe ese CFDI en este periodo.", status_code=404)
    return c


def leer_xml(c: CfdiNomina) -> bytes:
    if not c.ruta_xml:
        raise FiscalAgentError("Ese recibo no está timbrado.", status_code=409)
    return obtener_almacenamiento().leer(c.ruta_xml)


def cancelar(
    db: Session, cliente: Cliente, periodo: NominaPeriodo, c: CfdiNomina, motivo: str,
    folio_sustitucion: str | None, pac: Pac | None = None,
) -> CfdiNomina:
    """Cancela con el PAC; guarda el acuse y marca la bóveda."""
    if c.estado not in VIGENTES or not c.uuid:
        raise FiscalAgentError(f"Ese CFDI está {c.estado}: no se cancela.", status_code=409)
    pac = pac or obtener_pac()
    firmante = obtener_firmante(db, cliente, "csd") if pac.nombre == "finkok" else None
    try:
        acuse = pac.cancelar(c.uuid, boveda.rfc_del_cliente(cliente) or str(cliente.rfc), motivo,
                             folio_sustitucion, tipo="cfdi", firmante=firmante)
    except ValueError as e:
        raise FiscalAgentError(str(e), 422) from e
    if acuse.estatus == "rechazado":
        raise FiscalAgentError(f"El PAC rechazó la cancelación: {acuse.codigo} {acuse.mensaje}",
                               422)
    if acuse.acuse_xml:
        c.ruta_acuse = obtener_almacenamiento().guardar(
            acuse.acuse_xml, f"nomina/{cliente.despacho_id}/{cliente.id}/{c.uuid}-acuse.xml")
    c.estado = "cancelado" if acuse.estatus == "cancelado" else "cancelacion_en_proceso"
    c.motivo_cancelacion, c.folio_sustitucion = motivo, folio_sustitucion or ""
    if c.estado == "cancelado":
        rec = db.get(ReciboNomina, c.recibo_id)
        if rec is not None and rec.uuid_cfdi == c.uuid:
            rec.uuid_cfdi = None
        db.execute(update(Comprobante).where(
            Comprobante.cliente_id == cliente.id, Comprobante.uuid == c.uuid,
        ).values(estatus_sat="cancelado"))
    _actualizar_estado_periodo(db, periodo)
    db.flush()
    return c


def zip_del_periodo(db: Session, periodo: NominaPeriodo, pdf_de: Any) -> bytes:
    """XML y PDF de cada recibo timbrado vigente."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for c in _ultimo_por_recibo(db, periodo).values():
            if c.estado not in VIGENTES:
                continue
            xml = leer_xml(c)
            base = f"{c.empleado_no}_{c.uuid}"
            z.writestr(f"{base}.xml", xml)
            z.writestr(f"{base}.pdf", pdf_de(xml, c.es_prueba))
    return buf.getvalue()


def cfdi_json(c: CfdiNomina, nombre: str = "") -> dict[str, Any]:
    return {
        "id": c.id, "recibo_id": c.recibo_id, "empleado_no": c.empleado_no, "nombre": nombre,
        "estado": c.estado, "uuid": c.uuid, "serie": c.serie, "folio": c.folio,
        "intentos": c.intentos, "error": c.error, "pac": c.pac, "es_prueba": c.es_prueba,
        "total": str(c.total),
        "fecha_timbrado": c.fecha_timbrado.isoformat() if c.fecha_timbrado else None,
        "motivo_cancelacion": c.motivo_cancelacion,
    }
