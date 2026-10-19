"""
Tope semanal de horas extra (dobles) por fecha. (P4-05, revisor de motor B2)

FUENTES
-------
- **LFT Art. 66, reformado por el Decreto de reducción de la jornada a 40 horas
  (DOF 01-05-2026):** el trabajo extraordinario no excederá de 12 horas en una semana.
- **Transitorio Cuarto de ese Decreto:** el tope sube gradualmente — 9 horas por semana
  en 2026 y 2027, 10 en 2028, 11 en 2029 y 12 a partir de 2030.
- **Antes de la reforma** (texto anterior del Art. 66): no más de tres horas diarias ni
  tres veces en una semana — 9 horas. Por eso cualquier fecha anterior a 2028 da 9.
- **LFT Art. 68:** lo que excede el tope se paga con 200 % más (triples) y, por estar
  fuera del límite de la ley, no tiene la exención del Art. 93 fr. I LISR (100 % gravado).

La vigencia se lee por año calendario de la fecha del trabajo (fin del periodo).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

HORAS_EXTRA_ANTES_DE_2028 = Decimal("9")
HORAS_EXTRA_POR_ANIO: dict[int, Decimal] = {
    2028: Decimal("10"),
    2029: Decimal("11"),
}
HORAS_EXTRA_PLENO = Decimal("12")  # Art. 66 LFT a partir de 2030
ANIO_PLENO = 2030


def tope_horas_extra_semanal(fecha: date) -> Decimal:
    """Horas extra dobles permitidas por semana en `fecha` (Art. 66 + Transitorio Cuarto)."""
    if fecha.year >= ANIO_PLENO:
        return HORAS_EXTRA_PLENO
    return HORAS_EXTRA_POR_ANIO.get(fecha.year, HORAS_EXTRA_ANTES_DE_2028)


def tope_horas_extra_periodo(fecha: date, dias_periodo: int) -> Decimal:
    """El tope semanal proporcional a los días naturales del periodo."""
    return tope_horas_extra_semanal(fecha) * Decimal(dias_periodo) / Decimal("7")
