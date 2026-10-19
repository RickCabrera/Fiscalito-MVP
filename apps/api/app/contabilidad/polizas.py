"""
Pólizas persistentes (P2-03): folios, captura manual, edición, cancelación y periodos cerrados.

FOLIO
-----
Consecutivo por cliente, tipo (ingreso, egreso, diario) y mes: `I-2026-03-0007`. Se calcula
como el máximo + 1 dentro de un savepoint y la llave única `uq_poliza_folio` lo respalda; si
dos capturas chocan, se reintenta con el siguiente.

CANCELAR NO ES BORRAR
---------------------
Una póliza cancelada se queda (con su motivo y su fecha) y deja de contar en la balanza. Las
automáticas se cancelan solas cuando su CFDI se cancela ante el SAT (`cancelar_por_cfdi`): si
su mes sigue abierto se marca cancelada; si el mes ya se cerró, se genera una póliza de
reversa (movimientos invertidos) con fecha del día de la cancelación, para no mover un
periodo cerrado.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.contabilidad.asientos import CERO, Asiento, Renglon
from app.exceptions import FiscalAgentError
from app.modelos.cfdi import Comprobante
from app.modelos.contabilidad import CuentaContable, MovimientoPoliza, PeriodoCerrado, Poliza
from app.modelos.nucleo import Cliente

TIPOS = ("ingreso", "egreso", "diario")
LETRA = {"ingreso": "I", "egreso": "E", "diario": "D"}


def folio(p: Poliza) -> str:
    return f"{LETRA.get(p.tipo, '?')}-{p.anio:04d}-{p.mes:02d}-{p.numero:04d}"


# ── periodos ──


def periodo_cerrado(db: Session, cliente_id: int, fecha: date) -> bool:
    return db.get(PeriodoCerrado, (cliente_id, fecha.year, fecha.month)) is not None


def exigir_abierto(db: Session, cliente_id: int, fecha: date) -> None:
    if periodo_cerrado(db, cliente_id, fecha):
        raise FiscalAgentError(
            f"El periodo {fecha.year}-{fecha.month:02d} está cerrado: no acepta pólizas "
            "nuevas, ediciones ni cancelaciones.", 409)


def cerrar_periodo(db: Session, cliente: Cliente, anio: int, mes: int, uid: str) -> None:
    if db.get(PeriodoCerrado, (cliente.id, anio, mes)) is None:
        db.add(PeriodoCerrado(cliente_id=cliente.id, anio=anio, mes=mes,
                              cerrado_en=datetime.now(UTC), cerrado_por=uid))
        db.flush()


def abrir_periodo(db: Session, cliente: Cliente, anio: int, mes: int) -> None:
    previo = db.get(PeriodoCerrado, (cliente.id, anio, mes))
    if previo is not None:
        db.delete(previo)
        db.flush()


def periodos_cerrados(db: Session, cliente: Cliente) -> list[dict[str, Any]]:
    filas = db.scalars(select(PeriodoCerrado).where(PeriodoCerrado.cliente_id == cliente.id)
                       .order_by(PeriodoCerrado.anio, PeriodoCerrado.mes))
    return [{"anio": p.anio, "mes": p.mes, "cerrado_en": p.cerrado_en.isoformat(),
             "cerrado_por": p.cerrado_por} for p in filas]


# ── guardar ──


def _siguiente_numero(db: Session, cliente_id: int, tipo: str, fecha: date) -> int:
    actual = db.scalar(select(func.max(Poliza.numero)).where(
        Poliza.cliente_id == cliente_id, Poliza.tipo == tipo,
        Poliza.anio == fecha.year, Poliza.mes == fecha.month))
    return int(actual or 0) + 1


def guardar(db: Session, poliza: Poliza, movimientos: list[MovimientoPoliza]) -> Poliza:
    """Asigna folio y guarda la póliza con sus movimientos (reintenta si el folio choca)."""
    poliza.anio, poliza.mes = poliza.fecha.year, poliza.fecha.month
    for _intento in range(5):
        poliza.numero = _siguiente_numero(db, poliza.cliente_id, poliza.tipo, poliza.fecha)
        try:
            with db.begin_nested():
                db.add(poliza)
                db.flush()
                for i, m in enumerate(movimientos):
                    m.poliza_id = poliza.id
                    m.orden = i
                    db.add(m)
                db.flush()
            return poliza
        except IntegrityError as e:
            if "uq_poliza_origen" in str(e.orig) or "clave_origen" in str(e.orig):
                raise
            # El savepoint revertido ya sacó la póliza de la sesión: se reintenta con el
            # siguiente número.
            continue
    raise FiscalAgentError("No se pudo asignar folio a la póliza; intenta de nuevo.", 409)


def movimientos_de_asiento(
    asiento: Asiento, cuentas: dict[str, CuentaContable]
) -> list[MovimientoPoliza]:
    """Traduce renglones (por número) a movimientos (por id). Valida cuentas afectables."""
    salida = []
    for r in asiento.renglones:
        cuenta = cuentas.get(r.cuenta)
        if cuenta is None:
            raise FiscalAgentError(f"La cuenta {r.cuenta} no existe en el catálogo.", 422)
        if not cuenta.afectable:
            raise FiscalAgentError(f"La cuenta {r.cuenta} tiene subcuentas (no es afectable).",
                                   422)
        salida.append(_movimiento(cuenta.id, r))
    return salida


def _movimiento(cuenta_id: int, r: Renglon) -> MovimientoPoliza:
    return MovimientoPoliza(cuenta_id=cuenta_id, cargo=r.cargo, abono=r.abono,
                            concepto=r.concepto[:300], uuid_cfdi=r.uuid, rfc_tercero=r.rfc)


# ── captura manual y edición ──


@dataclass
class MovimientoEntrada:
    cuenta_id: int
    cargo: Decimal = CERO
    abono: Decimal = CERO
    concepto: str = ""
    uuid: str = ""
    rfc: str = ""


def _validar_movimientos(db: Session, cliente: Cliente,
                         movs: list[MovimientoEntrada]) -> list[MovimientoPoliza]:
    if len(movs) < 2:
        raise FiscalAgentError("Una póliza lleva al menos dos movimientos.", 422)
    ids = {m.cuenta_id for m in movs}
    cuentas = {c.id: c for c in db.scalars(select(CuentaContable).where(
        CuentaContable.cliente_id == cliente.id, CuentaContable.id.in_(ids)))}
    cargos = abonos = CERO
    salida = []
    for i, m in enumerate(movs, start=1):
        cuenta = cuentas.get(m.cuenta_id)
        if cuenta is None:
            raise FiscalAgentError(f"Movimiento {i}: la cuenta no existe en este catálogo.", 422)
        if not cuenta.afectable:
            raise FiscalAgentError(
                f"Movimiento {i}: la cuenta {cuenta.numero} tiene subcuentas; usa una afectable.",
                422)
        if m.cargo < 0 or m.abono < 0:
            raise FiscalAgentError(f"Movimiento {i}: los importes no pueden ser negativos.", 422)
        if (m.cargo > 0) == (m.abono > 0):
            raise FiscalAgentError(f"Movimiento {i}: lleva cargo o abono, uno de los dos.", 422)
        if m.cargo != m.cargo.quantize(Decimal("0.01")) or \
                m.abono != m.abono.quantize(Decimal("0.01")):
            raise FiscalAgentError(f"Movimiento {i}: los importes van a centavos.", 422)
        cargos += m.cargo
        abonos += m.abono
        salida.append(_movimiento(cuenta.id, Renglon(
            cuenta.numero, m.cargo, m.abono, m.concepto, m.uuid.strip().upper(),
            m.rfc.strip().upper()[:13])))
    if cargos != abonos:
        raise FiscalAgentError(
            f"La póliza no cuadra: cargos {cargos:.2f} ≠ abonos {abonos:.2f}.", 422)
    return salida


def crear_manual(db: Session, cliente: Cliente, *, tipo: str, fecha: date, concepto: str,
                 movimientos: list[MovimientoEntrada], uid: str) -> Poliza:
    if tipo not in TIPOS:
        raise FiscalAgentError("Tipo de póliza inválido (ingreso, egreso o diario).", 422)
    exigir_abierto(db, cliente.id, fecha)
    movs = _validar_movimientos(db, cliente, movimientos)
    uuids = sorted({m.uuid_cfdi for m in movs if m.uuid_cfdi})
    poliza = Poliza(cliente_id=cliente.id, tipo=tipo, fecha=fecha, concepto=concepto[:500],
                    origen="manual", estado="activa", uuid_cfdi=uuids[0] if len(uuids) == 1
                    else None, diferencia=CERO, advertencias=[], creado_por=uid)
    return guardar(db, poliza, movs)


def _exigir_no_de_cierre(p: Poliza) -> None:
    if p.origen in ("cierre", "apertura"):
        raise FiscalAgentError(
            "Las pólizas de cierre y apertura no se editan ni se cancelan a mano: deshaz el "
            "cierre anual desde la pantalla de periodos.", 409)


def obtener(db: Session, cliente: Cliente, poliza_id: int) -> Poliza:
    p = db.scalar(select(Poliza).where(Poliza.id == poliza_id, Poliza.cliente_id == cliente.id))
    if p is None:
        raise FiscalAgentError("No existe esa póliza en este cliente.", 404)
    return p


def editar(db: Session, cliente: Cliente, poliza_id: int, *, fecha: date | None,
           concepto: str | None, movimientos: list[MovimientoEntrada] | None) -> Poliza:
    """Edita una póliza activa. Cambiar de mes o de tipo no renumera: se conserva el folio."""
    p = obtener(db, cliente, poliza_id)
    if p.estado != "activa":
        raise FiscalAgentError("Una póliza cancelada no se edita.", 409)
    _exigir_no_de_cierre(p)
    exigir_abierto(db, cliente.id, p.fecha)
    if fecha is not None and fecha != p.fecha:
        if (fecha.year, fecha.month) != (p.anio, p.mes):
            raise FiscalAgentError(
                "La fecha nueva cae en otro mes: cancela la póliza y captúrala en ese mes.", 422)
        p.fecha = fecha
    if concepto is not None:
        p.concepto = concepto[:500]
    if movimientos is not None:
        nuevos = _validar_movimientos(db, cliente, movimientos)
        for viejo in db.scalars(select(MovimientoPoliza)
                                .where(MovimientoPoliza.poliza_id == p.id)):
            db.delete(viejo)
        db.flush()
        for i, m in enumerate(nuevos):
            m.poliza_id, m.orden = p.id, i
            db.add(m)
    p.editada = True
    db.flush()
    return p


def cancelar(db: Session, cliente: Cliente, poliza_id: int, motivo: str) -> Poliza:
    p = obtener(db, cliente, poliza_id)
    if p.estado == "cancelada":
        return p
    _exigir_no_de_cierre(p)
    exigir_abierto(db, cliente.id, p.fecha)
    p.estado, p.cancelada_en = "cancelada", datetime.now(UTC)
    p.motivo_cancelacion = (motivo or "Cancelada por el usuario.")[:300]
    db.flush()
    return p


def cancelar_por_cfdi(db: Session, comp: Comprobante, cuando: date | None = None) -> str:
    """
    El CFDI se canceló ante el SAT: su póliza automática deja de contar.

    Devuelve qué pasó: `sin_poliza`, `ya_cancelada`, `cancelada` o `reversa`. Idempotente.
    """
    p = db.scalar(select(Poliza).where(Poliza.cliente_id == comp.cliente_id,
                                       Poliza.clave_origen == f"cfdi:{comp.uuid}"))
    if p is None:
        return "sin_poliza"
    if p.estado == "cancelada":
        return "ya_cancelada"
    if not periodo_cerrado(db, comp.cliente_id, p.fecha):
        p.estado, p.cancelada_en = "cancelada", datetime.now(UTC)
        p.motivo_cancelacion = "CFDI cancelado ante el SAT."
        db.flush()
        return "cancelada"
    clave = f"reversa:{comp.uuid}"
    if db.scalar(select(Poliza.id).where(Poliza.cliente_id == comp.cliente_id,
                                         Poliza.clave_origen == clave)):
        return "reversa"
    fecha = cuando or datetime.now(UTC).date()
    exigir_abierto(db, comp.cliente_id, fecha)
    originales = list(db.scalars(select(MovimientoPoliza).where(
        MovimientoPoliza.poliza_id == p.id).order_by(MovimientoPoliza.orden)))
    reversa = Poliza(
        cliente_id=comp.cliente_id, tipo=p.tipo, fecha=fecha, origen="automatica",
        estado="activa", uuid_cfdi=comp.uuid, tipo_cfdi=p.tipo_cfdi, clave_origen=clave,
        reversa_de_id=p.id, concepto=f"Reversa por cancelación del CFDI {comp.uuid}"[:500],
        diferencia=CERO, advertencias=[f"Reversa de la póliza {folio(p)} (periodo cerrado)."],
    )
    movs = [MovimientoPoliza(cuenta_id=m.cuenta_id, cargo=m.abono, abono=m.cargo,
                             concepto=f"Reversa: {m.concepto}"[:300], uuid_cfdi=m.uuid_cfdi,
                             rfc_tercero=m.rfc_tercero) for m in originales]
    guardar(db, reversa, movs)
    return "reversa"


# ── consulta ──


def movimientos(db: Session, poliza_id: int) -> list[tuple[MovimientoPoliza, CuentaContable]]:
    return list(db.execute(
        select(MovimientoPoliza, CuentaContable)
        .join(CuentaContable, CuentaContable.id == MovimientoPoliza.cuenta_id)
        .where(MovimientoPoliza.poliza_id == poliza_id).order_by(MovimientoPoliza.orden)
    ).all())


def como_dict(db: Session, p: Poliza, *, detalle: bool = False) -> dict[str, Any]:
    totales = db.execute(select(func.coalesce(func.sum(MovimientoPoliza.cargo), 0),
                                func.coalesce(func.sum(MovimientoPoliza.abono), 0))
                         .where(MovimientoPoliza.poliza_id == p.id)).one()
    salida: dict[str, Any] = {
        "id": p.id, "folio": folio(p), "tipo": p.tipo, "numero": p.numero,
        "fecha": p.fecha.isoformat(), "concepto": p.concepto, "origen": p.origen,
        "estado": p.estado, "uuid_cfdi": p.uuid_cfdi, "tipo_cfdi": p.tipo_cfdi,
        "total_cargos": f"{Decimal(totales[0]):.2f}", "total_abonos": f"{Decimal(totales[1]):.2f}",
        "diferencia": f"{p.diferencia:.2f}", "advertencias": list(p.advertencias or []),
        "editada": p.editada, "reversa_de_id": p.reversa_de_id,
        "motivo_cancelacion": p.motivo_cancelacion,
        "cancelada_en": p.cancelada_en.isoformat() if p.cancelada_en else None,
    }
    if detalle:
        salida["movimientos"] = [{
            "id": m.id, "cuenta_id": c.id, "cuenta": c.numero, "nombre_cuenta": c.nombre,
            "concepto": m.concepto, "cargo": f"{m.cargo:.2f}", "abono": f"{m.abono:.2f}",
            "uuid": m.uuid_cfdi, "rfc": m.rfc_tercero,
        } for m, c in movimientos(db, p.id)]
    return salida


@dataclass
class FiltrosPolizas:
    desde: date | None = None
    hasta: date | None = None
    tipo: str | None = None
    origen: str | None = None
    estado: str | None = None
    uuid: str | None = None
    texto: str | None = None


def listar(db: Session, cliente: Cliente, f: FiltrosPolizas, pagina: int,
           por_pagina: int) -> tuple[list[Poliza], int]:
    cond: list[Any] = [Poliza.cliente_id == cliente.id]
    if f.desde:
        cond.append(Poliza.fecha >= f.desde)
    if f.hasta:
        cond.append(Poliza.fecha <= f.hasta)
    if f.tipo:
        cond.append(Poliza.tipo == f.tipo)
    if f.origen:
        cond.append(Poliza.origen == f.origen)
    if f.estado:
        cond.append(Poliza.estado == f.estado)
    if f.uuid:
        cond.append(Poliza.uuid_cfdi == f.uuid.strip().upper())
    if f.texto:
        cond.append(Poliza.concepto.ilike(f"%{f.texto.strip()}%"))
    total = db.scalar(select(func.count(Poliza.id)).where(*cond)) or 0
    filas = db.scalars(select(Poliza).where(*cond)
                       .order_by(Poliza.fecha, Poliza.tipo, Poliza.numero)
                       .offset((pagina - 1) * por_pagina).limit(por_pagina))
    return list(filas), int(total)
