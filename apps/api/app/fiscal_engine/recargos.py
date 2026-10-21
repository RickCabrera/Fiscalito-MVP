"""
Recargos de contribuciones pagadas fuera de plazo (P3-02). Separado de `actualizacion.py` (O11).

FUENTES
-------
- **Art. 21 CFF** — los recargos "se causarán por cada mes o fracción que transcurra a partir
  del día en que debió hacerse el pago", sobre "el monto de las contribuciones ...
  actualizados", "hasta por cinco años" (salvo Art. 67), y "la tasa de recargos para cada uno
  de los meses de mora será la que resulte de incrementar en 50%" la que fije la Ley de
  Ingresos de la Federación para la prórroga.
- **Ley de Ingresos de la Federación** — tasa mensual de prórroga y de pago a plazos, por año,
  en `datos/recargos.csv` (2026: LIF 2026 art. 11 → prórroga 1.38%, mora 2.07%).

VERIFICACIÓN (O12)
------------------
La columna `verificacion` del CSV marca `ley` cuando se consultó el artículo de la LIF del
año; cualquier otro valor (`secundaria`) es FUENTE POR CONFIRMAR y el resultado lo propaga en
`fuentes_por_confirmar` (`TasasRecargoAnio.aviso_por_confirmar`).
"""

from __future__ import annotations

import csv
from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Literal

from app.exceptions import FiscalValidationError
from app.redondeo import redondear

TipoRecargo = Literal[
    "mora", "prorroga", "parcialidades_12", "parcialidades_24", "parcialidades_mas_24"
]

# Art. 21 CFF: "Los recargos se causarán hasta por cinco años". Diez en los casos del Art. 67.
TOPE_MESES_RECARGOS_DEFAULT = 60
INCREMENTO_MORA = Decimal("1.5")  # Art. 21 CFF: la de prórroga incrementada en 50 %.
VERIFICADO = "ley"  # única marca de `verificacion` que cuenta como verificada.

ARCHIVO_RECARGOS = Path(__file__).parent / "datos" / "recargos.csv"


@dataclass(frozen=True)
class TasasRecargoAnio:
    """Tasas mensuales de un año de la LIF (fracciones, no porcentajes)."""

    anio: int
    prorroga: Decimal
    parcialidades_12: Decimal | None
    parcialidades_24: Decimal | None
    parcialidades_mas_24: Decimal | None
    verificacion: str
    fuente: str

    @property
    def verificado(self) -> bool:
        return self.verificacion == VERIFICADO

    @property
    def aviso_por_confirmar(self) -> str | None:
        """Texto para la respuesta cuando la tasa viene de fuente secundaria; None si no."""
        if self.verificado:
            return None
        return (f"Tasa de recargos {self.anio}: fuente secundaria, texto de la LIF {self.anio} "
                f"no consultado")


def _dec(v: str) -> Decimal | None:
    return Decimal(v) if v.strip() else None


@lru_cache(maxsize=1)
def tasas_recargos() -> dict[int, TasasRecargoAnio]:
    """Tasas de la LIF por año, leídas de `datos/recargos.csv`."""
    salida: dict[int, TasasRecargoAnio] = {}
    with ARCHIVO_RECARGOS.open(encoding="utf-8") as f:
        for fila in csv.DictReader(f):
            anio = int(fila["anio"])
            salida[anio] = TasasRecargoAnio(
                anio=anio,
                prorroga=Decimal(fila["prorroga"]),
                parcialidades_12=_dec(fila["parcialidades_12"]),
                parcialidades_24=_dec(fila["parcialidades_24"]),
                parcialidades_mas_24=_dec(fila["parcialidades_mas_24"]),
                verificacion=fila["verificacion"],
                fuente=fila["fuente"],
            )
    return salida


def tasa_mensual(anio: int, tipo: TipoRecargo) -> Decimal:
    """Tasa mensual de recargos de un año. Mora = prórroga × 1.5 (Art. 21 CFF)."""
    tasas = tasas_recargos().get(anio)
    if tasas is None:
        disponibles = ", ".join(str(a) for a in sorted(tasas_recargos()))
        raise FiscalValidationError(
            f"No hay tasa de recargos cargada para {anio}. Años: {disponibles}. Para agregar uno "
            f"hay que citar la Ley de Ingresos de la Federación de ese año."
        )
    if tipo == "mora":
        return tasas.prorroga * INCREMENTO_MORA
    if tipo == "prorroga":
        return tasas.prorroga
    valor = getattr(tasas, tipo)
    if valor is None:
        raise FiscalValidationError(
            f"No hay tasa de {tipo.replace('_', ' ')} cargada para {anio} (FUENTE POR CONFIRMAR)."
        )
    return valor


def sumar_meses(fecha: date, meses: int) -> date:
    """La misma fecha `meses` después; el día se recorta al último del mes si no existe."""
    total = fecha.month - 1 + meses
    anio, mes = fecha.year + total // 12, total % 12 + 1
    return date(anio, mes, min(fecha.day, monthrange(anio, mes)[1]))


def meses_de_mora(fecha_debio_pagarse: date, fecha_pago: date) -> int:
    """
    Meses o fracción transcurridos desde el día en que debió pagarse (Art. 21 CFF).

    Pagar el mismo día del vencimiento = 0. Un día después = 1. Exactamente un mes después
    (17-feb → 17-mar) = 1; un día más = 2.
    """
    if fecha_pago <= fecha_debio_pagarse:
        return 0
    completos = 0
    while sumar_meses(fecha_debio_pagarse, completos + 1) <= fecha_pago:
        completos += 1
    return completos + (1 if sumar_meses(fecha_debio_pagarse, completos) < fecha_pago else 0)


@dataclass(frozen=True)
class MesDeRecargo:
    """Un mes de mora con la tasa que le tocó."""

    numero: int
    inicia: date
    tasa: Decimal


def calcular_recargos(
    monto_actualizado: Decimal, fecha_debio_pagarse: date, meses: int, tipo: TipoRecargo
) -> tuple[tuple[MesDeRecargo, ...], Decimal, Decimal]:
    """
    Recargos de `meses` meses sobre el monto ya actualizado (Art. 21 CFF).

    Cada mes de mora toma la tasa de la LIF del año en que ese mes empieza a correr, así un
    adeudo que cruza el 1 de enero paga cada tramo con su tasa. La tasa acumulada es la suma
    exacta de las mensuales; los recargos se redondean a centavos (ROUND_HALF_UP).
    """
    detalle = []
    for n in range(1, meses + 1):
        inicia = sumar_meses(fecha_debio_pagarse, n - 1) + timedelta(days=1)
        detalle.append(MesDeRecargo(n, inicia, tasa_mensual(inicia.year, tipo)))
    tasa_acumulada = sum((m.tasa for m in detalle), Decimal("0"))
    return tuple(detalle), tasa_acumulada, redondear(monto_actualizado * tasa_acumulada)


def avisos_tasas(detalle: tuple[MesDeRecargo, ...]) -> tuple[str, ...]:
    """Las tasas de recargos usadas que vienen de fuente secundaria (una por año)."""
    avisos = []
    for anio in sorted({m.inicia.year for m in detalle}):
        aviso = tasas_recargos()[anio].aviso_por_confirmar
        if aviso:
            avisos.append(aviso)
    return tuple(avisos)
