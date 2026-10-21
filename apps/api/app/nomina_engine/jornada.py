"""
Topes de horas extra: semanal por fecha y diario por día capturado. (P4-05 B2, P6-07)

FUENTES
-------
- **LFT Art. 66, reformado por el Decreto de reducción de la jornada a 40 horas
  (DOF 01-05-2026):** el trabajo extraordinario no excederá de 12 horas en una semana.
- **Transitorio Cuarto de ese Decreto:** el tope sube gradualmente — 9 horas por semana
  en 2026 y 2027, 10 en 2028, 11 en 2029 y 12 a partir de 2030.
- **Antes de la reforma** (texto anterior del Art. 66): "sin exceder nunca de tres horas
  diarias ni de tres veces en una semana" — 9 horas. Por eso cualquier fecha anterior a
  2028 da 9.
- **LFT Art. 68, segundo párrafo:** la prolongación del tiempo extraordinario que exceda de
  nueve horas a la semana (o de los límites del Art. 66) se paga con 200 % más (triples) y,
  por estar fuera del límite de la ley, no tiene la exención del Art. 93 fr. I LISR (100 %
  gravado).

TOPE DIARIO (P6-07)
-------------------
Con las horas extra capturadas **por día** (`horas_extra_por_dia`), cada semana del periodo
(bloques de 7 días desde el inicio) se clasifica así: de cada día, hasta 3 horas son dobles;
lo que pasa de 3 horas ese día, las horas de un día con tiempo extra más allá de las
`veces_por_semana` permitidas, y lo que pasa del tope semanal, son triples (Art. 68) y se
avisa. Sin desglose diario sólo se aplica el tope semanal proporcional y se avisa que el
diario no se verificó.

# FUENTE POR CONFIRMAR: el texto reformado del Art. 66 (DOF 01-05-2026) sobre el límite
# diario y el número de veces por semana. Se conserva el de 3 horas diarias del texto
# anterior para todas las fechas, y 3 veces por semana mientras el tope semanal es 9; desde
# 2028 se admiten las veces necesarias para alcanzar el tope semanal con 3 h diarias (4).
# Es lo conservador para el patrón: clasifica como triples de más, nunca de menos.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

HORAS_EXTRA_ANTES_DE_2028 = Decimal("9")
HORAS_EXTRA_POR_ANIO: dict[int, Decimal] = {
    2028: Decimal("10"),
    2029: Decimal("11"),
}
HORAS_EXTRA_PLENO = Decimal("12")  # Art. 66 LFT a partir de 2030
ANIO_PLENO = 2030
HORAS_EXTRA_DIARIAS = Decimal("3")  # Art. 66 LFT: "sin exceder nunca de tres horas diarias"
VECES_POR_SEMANA_ANTES_DE_2028 = 3  # Art. 66 LFT: "ni de tres veces en una semana"
CERO = Decimal("0")


def tope_horas_extra_semanal(fecha: date) -> Decimal:
    """Horas extra dobles permitidas por semana en `fecha` (Art. 66 + Transitorio Cuarto)."""
    if fecha.year >= ANIO_PLENO:
        return HORAS_EXTRA_PLENO
    return HORAS_EXTRA_POR_ANIO.get(fecha.year, HORAS_EXTRA_ANTES_DE_2028)


def tope_horas_extra_periodo(fecha: date, dias_periodo: int) -> Decimal:
    """El tope semanal proporcional a los días naturales del periodo."""
    return tope_horas_extra_semanal(fecha) * Decimal(dias_periodo) / Decimal("7")


def veces_por_semana(fecha: date) -> int:
    """Días con tiempo extra admitidos por semana (ver FUENTE POR CONFIRMAR arriba)."""
    tope = tope_horas_extra_semanal(fecha)
    if tope <= HORAS_EXTRA_ANTES_DE_2028:
        return VECES_POR_SEMANA_ANTES_DE_2028
    return math.ceil(tope / HORAS_EXTRA_DIARIAS)


@dataclass(frozen=True)
class HorasExtraClasificadas:
    """Resultado de clasificar las horas extra capturadas por día."""

    dobles: Decimal
    triples: Decimal
    exceso_diario: Decimal
    exceso_veces: Decimal
    exceso_semanal: Decimal

    def avisos(self, empleado_no: str) -> list[str]:
        salida = []
        if self.exceso_diario:
            salida.append(
                f"{empleado_no}: {self.exceso_diario} horas extra pasan de 3 diarias (Art. 66 "
                "LFT): se pagan triples (Art. 68 segundo párrafo) y van 100 % gravadas."
            )
        if self.exceso_veces:
            salida.append(
                f"{empleado_no}: {self.exceso_veces} horas extra caen en días que pasan de las "
                "veces por semana del Art. 66 LFT: se pagan triples (Art. 68 segundo párrafo)."
            )
        if self.exceso_semanal:
            salida.append(
                f"{empleado_no}: {self.exceso_semanal} horas extra pasan del tope semanal "
                "(Art. 66 LFT): se pagan triples (Art. 68 segundo párrafo)."
            )
        return salida


def clasificar_horas_por_dia(horas: Sequence[Decimal], fecha: date) -> HorasExtraClasificadas:
    """Dobles y triples respetando el tope diario, las veces y el tope semanal (Art. 66)."""
    tope_semana = tope_horas_extra_semanal(fecha)
    veces = veces_por_semana(fecha)
    dobles = triples = ex_dia = ex_veces = ex_semana = CERO
    for i in range(0, len(horas), 7):
        usadas = CERO
        dias = 0
        for h in horas[i : i + 7]:
            if h <= 0:
                continue
            dias += 1
            if dias > veces:
                triples += h
                ex_veces += h
                continue
            en_dia = min(h, HORAS_EXTRA_DIARIAS)
            ex_dia += h - en_dia
            permitidas = min(en_dia, max(tope_semana - usadas, CERO))
            ex_semana += en_dia - permitidas
            usadas += permitidas
            dobles += permitidas
            triples += h - permitidas
    return HorasExtraClasificadas(dobles, triples, ex_dia, ex_veces, ex_semana)
