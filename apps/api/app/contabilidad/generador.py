"""
Generador de pólizas automáticas desde la bóveda (P2-03).

QUÉ GENERA
----------
Para un cliente y un rango de fechas, una póliza por CFDI **vigente** (`comprobantes_vigentes`:
los no cancelados) que todavía no tenga póliza, con el esquema de `asientos.py`:

| CFDI                    | Dirección | Póliza                          | Interruptor          |
|-------------------------|-----------|---------------------------------|----------------------|
| I (ingreso)             | emitido   | venta (diario o ingreso si PUE) | automatica_ingresos  |
| E (nota de crédito)     | emitido   | venta invertida                 | automatica_ingresos  |
| I                       | recibido  | gasto (diario o egreso si PUE)  | automatica_egresos   |
| E                       | recibido  | gasto invertido                 | automatica_egresos   |
| P (complemento de pago) | ambos     | cobro / pago + IVA efectivo     | automatica_pagos     |
| N (nómina)              | emitido   | nómina (egreso)                 | automatica_nomina    |

Los traslados (T) y la nómina recibida (el cliente como trabajador) no generan póliza.

IDEMPOTENTE POR UUID
--------------------
La póliza lleva `clave_origen = "cfdi:<UUID>"`, única por cliente: correr dos veces el mismo
mes (o un trabajo que se reintenta) no duplica. Un CFDI cuya póliza se canceló a mano NO se
vuelve a generar: la decisión del contador manda.

CANCELADOS
----------
Antes de generar, los CFDI ya cancelados ante el SAT que tienen póliza activa la cancelan (o
la revierten si su mes está cerrado). P1-03 además lo hace en el momento en que detecta la
cancelación (`app/sat_verificacion/estatus.py`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any

from sqlalchemy import literal, select
from sqlalchemy.orm import Session

from app.boveda_cfdi.servicio import comprobantes_vigentes
from app.contabilidad import asientos, catalogo, polizas
from app.contabilidad.asientos import CERO, DocumentoPagado, NoContabilizable, d
from app.contabilidad.config import ConfigEfectiva, efectiva
from app.exceptions import FiscalAgentError
from app.modelos.cfdi import Comprobante
from app.modelos.contabilidad import CuentaContable, MovimientoPoliza, Poliza
from app.modelos.nucleo import Cliente

LOTE = 200
CONCEPTOS = {
    ("I", "emitido"): "Venta", ("I", "recibido"): "Compra/gasto",
    ("E", "emitido"): "Nota de crédito a cliente",
    ("E", "recibido"): "Nota de crédito de proveedor",
    ("P", "emitido"): "Cobro de cliente", ("P", "recibido"): "Pago a proveedor",
    ("N", "emitido"): "Nómina",
}


@dataclass
class ResultadoGeneracion:
    generadas: int = 0
    ya_existian: int = 0
    omitidas: int = 0
    canceladas: int = 0
    revertidas: int = 0
    errores: list[dict[str, str]] = field(default_factory=list)
    omitidas_detalle: list[dict[str, str]] = field(default_factory=list)

    def como_dict(self) -> dict[str, Any]:
        return {"generadas": self.generadas, "ya_existian": self.ya_existian,
                "omitidas": self.omitidas, "canceladas": self.canceladas,
                "revertidas": self.revertidas, "errores": self.errores[:100],
                "omitidas_detalle": self.omitidas_detalle[:100]}


def _rango(desde: date, hasta: date) -> list[Any]:
    return [Comprobante.fecha >= datetime.combine(desde, time.min),
            Comprobante.fecha < datetime.combine(hasta + timedelta(days=1), time.min)]


def _habilitado(ef: ConfigEfectiva, comp: Comprobante) -> str | None:
    """None si se contabiliza; si no, la razón."""
    cfg = ef.config
    if comp.tipo == "T":
        return "Traslado: no mueve cuentas."
    if comp.tipo == "N":
        if comp.direccion != "emitido":
            return "Nómina recibida (el cliente es el trabajador)."
        return None if cfg.automatica_nomina else "Contabilidad automática de nómina apagada."
    if comp.tipo == "P":
        return None if cfg.automatica_pagos else "Contabilidad automática de pagos apagada."
    if comp.direccion == "emitido":
        return None if cfg.automatica_ingresos else "Contabilidad automática de ingresos apagada."
    return None if cfg.automatica_egresos else "Contabilidad automática de egresos apagada."


def _concepto(ef: ConfigEfectiva, comp: Comprobante) -> str:
    contraparte = comp.nombre_receptor if comp.direccion == "emitido" else comp.nombre_emisor
    rfc = comp.rfc_receptor if comp.direccion == "emitido" else comp.rfc_emisor
    etiqueta = CONCEPTOS.get((comp.tipo, comp.direccion), comp.tipo)
    folio = f"{comp.serie}{comp.folio}".strip()
    plantilla = ef.config.plantilla_concepto or "{etiqueta} {folio} {contraparte}"
    try:
        texto = plantilla.format(etiqueta=etiqueta, folio=folio, contraparte=contraparte or rfc,
                                 rfc=rfc, uuid=comp.uuid, tipo=comp.tipo)
    except (KeyError, IndexError, ValueError):
        texto = f"{etiqueta} {folio} {contraparte or rfc}"
    return " ".join(texto.split())[:500]


def _documentos_pagados(db: Session, cliente: Cliente, comps: list[Comprobante],
                        ef: ConfigEfectiva) -> dict[str, DocumentoPagado]:
    """Lo pendiente de IVA/IEPS de cada factura pagada en los complementos del lote."""
    uuids = {str(doc.get("IdDocumento") or "").upper()
             for comp in comps if comp.tipo == "P"
             for p in ((comp.datos or {}).get("pagos") or {}).get("pagos") or []
             for doc in p.get("documentos") or []}
    uuids.discard("")
    if not uuids:
        return {}
    salida: dict[str, DocumentoPagado] = {}
    facturas = {c.uuid: c for c in db.scalars(select(Comprobante).where(
        Comprobante.cliente_id == cliente.id, Comprobante.uuid.in_(uuids)))}
    # Lo pendiente que realmente quedó en la póliza de la factura (respeta reglas: el IVA de
    # un gasto no deducible no se fue a 119).
    pendientes: dict[tuple[str, str], Any] = {}
    roles = {ef.cuenta("iva_trasladado_no_cobrado"): "iva", ef.cuenta("iva_acreditable_pendiente"):
             "iva", ef.cuenta("ieps_trasladado_no_cobrado"): "ieps"}
    filas = db.execute(
        select(Poliza.uuid_cfdi, CuentaContable.numero, MovimientoPoliza.cargo,
               MovimientoPoliza.abono)
        .join(MovimientoPoliza, MovimientoPoliza.poliza_id == Poliza.id)
        .join(CuentaContable, CuentaContable.id == MovimientoPoliza.cuenta_id)
        .where(Poliza.cliente_id == cliente.id, Poliza.estado == "activa",
               Poliza.clave_origen.in_([f"cfdi:{u}" for u in uuids]),
               CuentaContable.numero.in_(list(roles)))
    )
    for uuid, numero, cargo, abono in filas:
        clave = (uuid, roles[numero])
        pendientes[clave] = pendientes.get(clave, CERO) + abs(cargo - abono)
    for uuid in uuids:
        f = facturas.get(uuid)
        if f is None:
            salida[uuid] = DocumentoPagado(CERO, CERO, CERO, conocido=False)
            continue
        tiene_poliza = any(k[0] == uuid for k in pendientes) or db.scalar(
            select(Poliza.id).where(Poliza.cliente_id == cliente.id,
                                    Poliza.clave_origen == f"cfdi:{uuid}",
                                    Poliza.estado == "activa")) is not None
        if tiene_poliza:
            iva = pendientes.get((uuid, "iva"), CERO)
            ieps = pendientes.get((uuid, "ieps"), CERO)
        elif f.metodo_pago == "PPD":
            factor = asientos.factor_moneda(f.moneda, f.tipo_cambio)
            iva, ieps = asientos.c(f.iva_trasladado * factor), asientos.c(f.ieps * factor)
        else:
            iva = ieps = CERO
        salida[uuid] = DocumentoPagado(d(f.total), iva, ieps, conocido=True)
    return salida


def _asiento(comp: Comprobante, ef: ConfigEfectiva, existentes: set[str],
             docs: dict[str, DocumentoPagado]) -> asientos.Asiento:
    if comp.tipo == "N":
        return asientos.nomina(comp, ef)
    if comp.tipo == "P":
        return asientos.pago(comp, ef, docs)
    nota = comp.tipo == "E"
    if comp.direccion == "emitido":
        return asientos.factura_emitida(comp, ef, nota=nota)
    return asientos.factura_recibida(comp, ef, existentes, nota=nota)


def revertir_cancelados(db: Session, cliente: Cliente, desde: date | None = None,
                        hasta: date | None = None) -> tuple[int, int]:
    """Cancela (o revierte) las pólizas activas de CFDI que ya están cancelados ante el SAT."""
    db.flush()  # la sesión no tiene autoflush: un estatus recién cambiado debe verse
    cond = [Comprobante.cliente_id == cliente.id, Comprobante.estatus_sat == "cancelado",
            Poliza.estado == "activa", Poliza.reversa_de_id.is_(None)]
    if desde and hasta:
        cond += _rango(desde, hasta)
    clave = literal("cfdi:").concat(Comprobante.uuid)
    comps = db.scalars(
        select(Comprobante).join(Poliza, (Poliza.cliente_id == Comprobante.cliente_id)
                                 & (Poliza.clave_origen == clave))
        .where(*cond))
    canceladas = revertidas = 0
    for comp in comps:
        r = polizas.cancelar_por_cfdi(db, comp)
        canceladas += r == "cancelada"
        revertidas += r == "reversa"
    return canceladas, revertidas


def generar(db: Session, cliente: Cliente, desde: date, hasta: date,
            uid: str = "") -> ResultadoGeneracion:
    """Genera las pólizas automáticas del rango. Idempotente. No hace commit."""
    if desde > hasta:
        raise FiscalAgentError("'desde' no puede ser posterior a 'hasta'.", 422)
    if not catalogo.cuentas(db, cliente):
        raise FiscalAgentError(
            "El cliente no tiene catálogo de cuentas: siembra el catálogo base primero.", 409)
    r = ResultadoGeneracion()
    r.canceladas, r.revertidas = revertir_cancelados(db, cliente, desde, hasta)
    ef = efectiva(db, cliente)
    cuentas = catalogo.por_numero(db, cliente)
    existentes = set(cuentas)

    ya = set(db.scalars(select(Poliza.clave_origen).where(
        Poliza.cliente_id == cliente.id, Poliza.clave_origen.is_not(None))))
    consulta = comprobantes_vigentes(
        select(Comprobante).where(Comprobante.cliente_id == cliente.id, *_rango(desde, hasta))
    ).order_by(Comprobante.fecha, Comprobante.id)
    # Facturas antes que pagos: un pago del mismo lote encuentra la póliza de su factura.
    comps = sorted(db.scalars(consulta), key=lambda c: (c.tipo == "P", c.fecha, c.id))
    # Se calcula al llegar al primer pago, cuando las facturas del lote ya tienen póliza.
    docs: dict[str, DocumentoPagado] | None = None
    for comp in comps:
        if f"cfdi:{comp.uuid}" in ya:
            r.ya_existian += 1
            continue
        razon = _habilitado(ef, comp)
        if razon is not None:
            r.omitidas += 1
            r.omitidas_detalle.append({"uuid": comp.uuid, "razon": razon})
            continue
        if comp.tipo == "P" and docs is None:
            docs = _documentos_pagados(db, cliente, comps, ef)
        try:
            asiento = _asiento(comp, ef, existentes, docs or {})
            if not asiento.renglones:
                raise NoContabilizable("El CFDI no tiene importes que contabilizar.")
            if asiento.total_cargos != asiento.total_abonos:  # defensa: nunca debe pasar
                raise NoContabilizable(
                    f"Asiento descuadrado ({asiento.total_cargos} ≠ {asiento.total_abonos}).")
            fecha = comp.fecha.date()
            polizas.exigir_abierto(db, cliente.id, fecha)
            movs = polizas.movimientos_de_asiento(asiento, cuentas)
        except (NoContabilizable, FiscalAgentError) as e:
            r.errores.append({"uuid": comp.uuid, "error": str(e)})
            continue
        advertencias = list(asiento.advertencias)
        if asiento.diferencia:
            advertencias.append(
                f"Diferencia de {asiento.diferencia:.2f} contra el total del CFDI (impuestos "
                "que no se leen, p. ej. locales).")
        poliza = Poliza(
            cliente_id=cliente.id, tipo=asiento.tipo, fecha=fecha, concepto=_concepto(ef, comp),
            origen="automatica", estado="activa", uuid_cfdi=comp.uuid, tipo_cfdi=comp.tipo,
            clave_origen=f"cfdi:{comp.uuid}", diferencia=asiento.diferencia,
            advertencias=advertencias, creado_por=uid,
        )
        polizas.guardar(db, poliza, movs)
        ya.add(poliza.clave_origen or "")
        r.generadas += 1
        if r.generadas % LOTE == 0:
            db.flush()
    db.flush()
    return r
