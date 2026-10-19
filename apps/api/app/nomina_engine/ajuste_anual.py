"""
Cálculo anual del ISR de sueldos que hace el patrón. (P4-08, Art. 97 LISR)

FUENTES
-------
- **Art. 97 LISR**: el retenedor calcula el impuesto anual de cada trabajador.
  No lo hace cuando el trabajador (I) empezó después del 1 de enero o dejó de
  prestar servicios antes del 1 de diciembre, (II) obtuvo ingresos anuales que
  excedan $400,000.00, o (III) comunicó por escrito que presentará su declaración.
  La diferencia a cargo se entera a más tardar en febrero; la diferencia a favor
  se compensa contra la retención de diciembre y las siguientes.
- **Art. 152 LISR**: tarifa anual (Anexo 8 RMF 2026, rubro C fr. II), que ya
  vive transcrita en `fiscal_engine/tablas_isr.py:TABLA_ISR_ANUAL` y aquí se lee
  en Decimal desde esos mismos literales.
- **Decreto del subsidio para el empleo (DOF 01-05-2024, vigente con su reforma
  DOF 31-12-2025)**: el impuesto anual se disminuye con la suma del subsidio que
  correspondió en cada mes; si el subsidio es mayor, no hay impuesto ni se entrega
  cantidad alguna.

# DECISIÓN PROVISIONAL (nocturno): el tope de $400,000 se compara contra los
# ingresos TOTALES del capítulo (gravados + exentos). La lectura que sólo cuenta
# gravados haría el cálculo a más gente; ésta es la conservadora para el patrón.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.exceptions import FiscalValidationError
from app.fiscal_engine.tablas_isr import TABLA_ISR_ANUAL
from app.redondeo import redondear

CERO = Decimal("0.00")
TOPE_INGRESOS_ART_97 = Decimal("400000.00")  # Art. 97 fr. II LISR

# Tarifa anual del Art. 152 por ejercicio, en Decimal. Mismos literales de
# `TABLA_ISR_ANUAL` (Anexo 8 RMF 2026, DOF 28-12-2025), convertidos desde str.
TARIFA_ANUAL: dict[int, tuple[tuple[Decimal, Decimal, Decimal, Decimal], ...]] = {
    2026: tuple(
        tuple(Decimal("Infinity") if v == float("inf") else Decimal(str(v)) for v in r)
        for r in TABLA_ISR_ANUAL
    ),
}


def isr_anual(base: Decimal, ejercicio: int) -> Decimal:
    """Tarifa del Art. 152 LISR."""
    tarifa = TARIFA_ANUAL.get(ejercicio)
    if tarifa is None:
        raise FiscalValidationError(f"No hay tarifa anual del Art. 152 cargada para {ejercicio}.")
    if base <= 0:
        return CERO
    for inferior, superior, cuota, tasa in tarifa:
        if base <= superior:
            return redondear(cuota + (base - inferior) * tasa)
    raise FiscalValidationError("Base fuera de tarifa.")  # inalcanzable


@dataclass(frozen=True)
class DatosAnuales:
    """Lo que el patrón acumuló del trabajador en el ejercicio."""

    ejercicio: int
    fecha_alta: date | None
    fecha_baja: date | None
    ingresos_gravados: Decimal
    ingresos_exentos: Decimal
    isr_retenido: Decimal
    subsidio_correspondido: Decimal = CERO
    comunico_que_declara: bool = False


@dataclass(frozen=True)
class AjusteAnual:
    """Resultado del cálculo anual de un trabajador."""

    procede: bool
    motivo: str
    isr_tarifa: Decimal
    subsidio_aplicado: Decimal
    impuesto_anual: Decimal
    isr_retenido: Decimal
    saldo_a_cargo: Decimal
    saldo_a_favor: Decimal
    tratamiento: str


def motivo_no_procede(d: DatosAnuales) -> str | None:
    """La causal de exclusión del Art. 97, o `None` si procede."""
    if d.fecha_alta and d.fecha_alta > date(d.ejercicio, 1, 1):
        return "Empezó a prestar servicios después del 1 de enero (Art. 97 fr. I)."
    if d.fecha_baja and d.fecha_baja < date(d.ejercicio, 12, 1):
        return "Dejó de prestar servicios antes del 1 de diciembre (Art. 97 fr. I)."
    if d.ingresos_gravados + d.ingresos_exentos > TOPE_INGRESOS_ART_97:
        return "Sus ingresos anuales exceden $400,000.00 (Art. 97 fr. II)."
    if d.comunico_que_declara:
        return "Comunicó por escrito que presentará su declaración anual (Art. 97 fr. III)."
    return None


def ajuste_anual(d: DatosAnuales) -> AjusteAnual:
    """Calcula el impuesto anual y el saldo contra lo retenido."""
    if min(d.ingresos_gravados, d.ingresos_exentos, d.isr_retenido, d.subsidio_correspondido) < 0:
        raise FiscalValidationError("Los acumulados del año no pueden ser negativos.")
    tarifa = isr_anual(d.ingresos_gravados, d.ejercicio)
    subsidio = min(d.subsidio_correspondido, tarifa)
    impuesto = tarifa - subsidio
    diferencia = impuesto - d.isr_retenido
    motivo = motivo_no_procede(d)
    if motivo:
        return AjusteAnual(
            False,
            motivo,
            tarifa,
            subsidio,
            impuesto,
            d.isr_retenido,
            CERO,
            CERO,
            "El patrón no hace el cálculo anual; el trabajador presenta su declaración "
            "o no tiene obligación (Arts. 97 y 98 LISR). Las cifras son informativas.",
        )
    if diferencia > 0:
        return AjusteAnual(
            True,
            "Procede el cálculo anual.",
            tarifa,
            subsidio,
            impuesto,
            d.isr_retenido,
            diferencia,
            CERO,
            "Saldo a cargo: se retiene y entera a más tardar en febrero (Art. 97 LISR).",
        )
    return AjusteAnual(
        True,
        "Procede el cálculo anual.",
        tarifa,
        subsidio,
        impuesto,
        d.isr_retenido,
        CERO,
        -diferencia,
        "Saldo a favor: se compensa contra la retención de diciembre y las siguientes "
        "(Art. 97 LISR). En el CFDI va como OtroPago 004 (compensación de saldo a favor).",
    )
