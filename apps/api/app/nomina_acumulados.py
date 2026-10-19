"""
Acumulados del ejercicio a partir del historial de nóminas guardadas. (P4-02, P4-08, O3)

Los usan el ajuste anual (Art. 97 LISR) y los topes de exención anuales del Art. 93
fr. XIV (prima vacacional). Salieron de `nomina_servicio.py` por el tope de 300 líneas.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modelos.nomina import NominaPeriodo
from app.modelos.nucleo import Cliente
from app.nomina_servicio import _dec, recibos_de

CERO = Decimal("0.00")


def acumulados_del_ejercicio(
    db: Session, cliente: Cliente, ejercicio: int
) -> dict[str, dict[str, Decimal]]:
    """Gravado, exento, ISR y subsidio por empleado de los periodos guardados del año."""
    periodos = list(
        db.scalars(
            select(NominaPeriodo).where(
                NominaPeriodo.cliente_id == cliente.id,
                NominaPeriodo.fecha_pago >= date(ejercicio, 1, 1),
                NominaPeriodo.fecha_pago <= date(ejercicio, 12, 31),
            )
        )
    )
    acc: dict[str, dict[str, Decimal]] = {}
    for p in periodos:
        for r in recibos_de(db, p):
            a = acc.setdefault(
                r.empleado_no, {k: CERO for k in ("gravado", "exento", "isr", "subsidio")}
            )
            a["gravado"] += sum((_dec(x.get("gravado")) for x in r.percepciones), start=CERO)
            a["exento"] += sum((_dec(x.get("exento")) for x in r.percepciones), start=CERO)
            a["isr"] += r.isr
            a["subsidio"] += r.subsidio
    return acc


def exento_en_el_anio(
    db: Session, cliente: Cliente, anio: int, clave: str, excluir: tuple[str, date, date]
) -> dict[str, Decimal]:
    """
    Exento ya aplicado en el año por empleado para una clave de percepción (O3).

    Suma el `exento` de esa clave en los periodos guardados con fecha de pago en `anio`,
    salvo el periodo que se está recalculando (`excluir` = tipo, inicio, fin).
    """
    tipo, inicio, fin = excluir
    periodos = list(
        db.scalars(
            select(NominaPeriodo).where(
                NominaPeriodo.cliente_id == cliente.id,
                NominaPeriodo.fecha_pago >= date(anio, 1, 1),
                NominaPeriodo.fecha_pago <= date(anio, 12, 31),
            )
        )
    )
    acc: dict[str, Decimal] = {}
    for p in periodos:
        if (p.tipo, p.inicio, p.fin) == (tipo, inicio, fin):
            continue
        for r in recibos_de(db, p):
            exento = sum(
                (_dec(x.get("exento")) for x in r.percepciones if x.get("tipo") == clave),
                start=CERO,
            )
            if exento:
                acc[r.empleado_no] = acc.get(r.empleado_no, CERO) + exento
    return acc
