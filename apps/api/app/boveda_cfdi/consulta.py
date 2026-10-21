"""
Consulta de la bóveda de CFDI (plan P, P0-03): listar, obtener, descargar, borrar y
resumir. Salió de `servicio.py` en P6-05 (tope de 300 líneas) sin cambiar comportamiento;
`servicio` la reexporta.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any

from sqlalchemy import and_, extract, func, or_, select
from sqlalchemy.orm import Session

from app.boveda_cfdi.parser import CfdiLeido
from app.exceptions import FiscalAgentError
from app.integraciones.almacenamiento import Almacenamiento, obtener_almacenamiento
from app.modelos.cfdi import Comprobante
from app.modelos.nucleo import Cliente


def comprobantes_vigentes(consulta: Any) -> Any:
    """
    La consulta sin los CFDI cancelados ante el SAT (P1-03).

    Es el filtro que usan los cálculos (Fiscalito, Contabilito, la anual, P1-06): un CFDI
    cancelado sigue en la bóveda —se ve, se descarga— pero deja de contar. Los que todavía no
    se verifican (`desconocido`) SÍ cuentan: no verificar no es motivo para excluir.

        servicio.comprobantes_vigentes(select(Comprobante).where(...))
    """
    return consulta.where(Comprobante.estatus_sat != "cancelado")


@dataclass
class Filtros:
    """Filtros de la lista de la bóveda. Todo opcional."""

    desde: date | None = None
    hasta: date | None = None
    tipo: str | None = None
    direccion: str | None = None
    rfc: str | None = None
    estatus: str | None = None


def _condiciones(cliente: Cliente, f: Filtros) -> list[Any]:
    cond: list[Any] = [Comprobante.cliente_id == cliente.id]
    if f.desde:
        cond.append(Comprobante.fecha >= datetime.combine(f.desde, time.min))
    if f.hasta:
        # Inclusivo: todo el día `hasta`.
        cond.append(Comprobante.fecha < datetime.combine(f.hasta + timedelta(days=1), time.min))
    if f.tipo:
        cond.append(Comprobante.tipo == f.tipo.upper())
    if f.direccion:
        cond.append(Comprobante.direccion == f.direccion)
    if f.estatus:
        cond.append(Comprobante.estatus_sat == f.estatus)
    if f.rfc:
        rfc = f.rfc.strip().upper()
        # La contraparte: el receptor de lo emitido, el emisor de lo recibido.
        cond.append(or_(
            and_(Comprobante.direccion == "emitido", Comprobante.rfc_receptor == rfc),
            and_(Comprobante.direccion == "recibido", Comprobante.rfc_emisor == rfc),
        ))
    return cond


def listar(
    db: Session, cliente: Cliente, filtros: Filtros, pagina: int = 1, por_pagina: int = 50
) -> tuple[list[Comprobante], int]:
    """Una página de comprobantes (más recientes primero) y el total que cumple el filtro."""
    cond = _condiciones(cliente, filtros)
    total = db.scalar(select(func.count(Comprobante.id)).where(*cond)) or 0
    filas = db.scalars(
        select(Comprobante).where(*cond)
        .order_by(Comprobante.fecha.desc(), Comprobante.id.desc())
        .offset((pagina - 1) * por_pagina).limit(por_pagina)
    )
    return list(filas), int(total)


def obtener(db: Session, cliente: Cliente, uuid: str) -> Comprobante:
    """El comprobante `uuid` del cliente, o 404."""
    comp = db.scalar(select(Comprobante).where(
        Comprobante.cliente_id == cliente.id, Comprobante.uuid == uuid.strip().upper()
    ))
    if comp is None:
        raise FiscalAgentError(f"No existe el CFDI {uuid} en la bóveda de este cliente.", 404)
    return comp


def leer_xml_original(comp: Comprobante, almacen: Almacenamiento | None = None) -> bytes:
    """Los bytes tal como se subieron. 500 si el almacén devolvió otra cosa."""
    datos = (almacen or obtener_almacenamiento()).leer(comp.ruta_xml)
    if hashlib.sha256(datos).hexdigest() != comp.sha256:
        raise FiscalAgentError(
            f"El XML guardado de {comp.uuid} no coincide con su huella; no se entrega.", 500
        )
    return datos


def borrar(
    db: Session, cliente: Cliente, uuid: str, almacen: Almacenamiento | None = None
) -> None:
    """Quita el comprobante de la bóveda y su XML del almacén."""
    comp = obtener(db, cliente, uuid)
    db.delete(comp)
    db.flush()
    (almacen or obtener_almacenamiento()).borrar(comp.ruta_xml)


def resumen(db: Session, cliente: Cliente, filtros: Filtros) -> list[dict[str, Any]]:
    """Conteos y totales por mes, tipo y dirección."""
    anio = extract("year", Comprobante.fecha)
    mes = extract("month", Comprobante.fecha)
    filas = db.execute(
        select(anio, mes, Comprobante.tipo, Comprobante.direccion,
               func.count(Comprobante.id), func.sum(Comprobante.total))
        .where(*_condiciones(cliente, filtros))
        .group_by(anio, mes, Comprobante.tipo, Comprobante.direccion)
        .order_by(anio, mes, Comprobante.tipo, Comprobante.direccion)
    )
    return [
        {"periodo": f"{int(a):04d}-{int(m):02d}", "tipo": t, "direccion": d,
         "cantidad": int(c), "total": f"{(s or 0):.2f}"}
        for a, m, t, d, c, s in filas
    ]


# ── renglones (los usa `servicio.importar`) ──


def _existe(db: Session, cliente_id: int, uuid: str) -> bool:
    return db.scalar(
        select(Comprobante.id).where(
            Comprobante.cliente_id == cliente_id, Comprobante.uuid == uuid
        )
    ) is not None


def _comprobante(
    cliente: Cliente, cfdi: CfdiLeido, direccion: str, origen: str, ruta: str, datos: bytes
) -> Comprobante:
    return Comprobante(
        cliente_id=cliente.id, uuid=cfdi.uuid, version=cfdi.version, tipo=cfdi.tipo,
        fecha=cfdi.fecha, fecha_timbrado=cfdi.fecha_timbrado, serie=cfdi.serie,
        folio=cfdi.folio, rfc_emisor=cfdi.rfc_emisor, nombre_emisor=cfdi.nombre_emisor,
        rfc_receptor=cfdi.rfc_receptor, nombre_receptor=cfdi.nombre_receptor,
        direccion=direccion, subtotal=cfdi.subtotal, descuento=cfdi.descuento,
        total=cfdi.total, moneda=cfdi.moneda, tipo_cambio=cfdi.tipo_cambio,
        metodo_pago=cfdi.metodo_pago, forma_pago=cfdi.forma_pago, uso_cfdi=cfdi.uso_cfdi,
        iva_trasladado=cfdi.iva_trasladado, iva_retenido=cfdi.iva_retenido,
        isr_retenido=cfdi.isr_retenido, ieps=cfdi.ieps, estatus_sat="desconocido",
        origen=origen, ruta_xml=ruta, sha256=hashlib.sha256(datos).hexdigest(),
        datos=cfdi.datos,
    )
