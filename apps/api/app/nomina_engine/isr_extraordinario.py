"""
ISR de pagos extraordinarios: aguinaldo, PTU, primas y pagos por separación.

Funciones puras compartidas por `aguinaldo.py`, `ptu.py` y `finiquito.py`.

FUENTES
-------
- **Art. 96 LISR**: la remuneración gravada se suma al ingreso del mes y se
  retiene la diferencia de la tarifa mensual (Anexo 8 RMF 2026, rubro B).
- **Art. 174 RLISR** (opción del retenedor para gratificación anual, PTU, primas
  dominicales y vacacionales):
    I.   remuneración ÷ 365 × 30.4
    II.  + ingreso ordinario mensual → tarifa del Art. 96
    III. − impuesto del ingreso ordinario sólo
    V.   tasa = III ÷ I
    IV.  retención = remuneración gravada × tasa
- **Arts. 95 y 96 LISR** (pagos por separación): se aplica a lo gravado la tasa
  que resulta de dividir el impuesto del último sueldo mensual ordinario entre
  ese sueldo. Si el pago es menor que el último sueldo mensual ordinario, se suma
  a los demás ingresos y se aplica la tarifa del Art. 96.

REDONDEO
--------
La tasa del Art. 174 y la del Art. 96 (separación) se usan con precisión
completa y sólo el impuesto se redondea a 2 decimales (§D2).
# DECISIÓN PROVISIONAL (nocturno): hay software que redondea la tasa a 4
# decimales de porcentaje; la diferencia es de centavos.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.constants import DIAS_MES_FISCAL
from app.exceptions import FiscalValidationError
from app.nomina_engine.tablas_isr_periodicas import isr_periodo
from app.redondeo import redondear

CERO = Decimal("0.00")
DIAS_ANIO = Decimal("365")
CLAVE_MENSUAL = "05"


def isr_mensual(base: Decimal, fecha: date) -> Decimal:
    """Tarifa mensual del Art. 96 LISR (sin subsidio)."""
    return isr_periodo(max(base, CERO), CLAVE_MENSUAL, fecha)


@dataclass(frozen=True)
class ISRExtraordinario:
    """El ISR de una remuneración extraordinaria, con su rastro."""

    metodo: str
    gravado: Decimal
    isr: Decimal
    tasa: Decimal | None
    fundamento: str


def isr_art_96(gravado: Decimal, ordinario_mensual: Decimal, fecha: date) -> ISRExtraordinario:
    """ISR(ordinario + gravado) − ISR(ordinario), tarifa mensual del Art. 96."""
    isr = isr_mensual(ordinario_mensual + gravado, fecha) - isr_mensual(ordinario_mensual, fecha)
    return ISRExtraordinario(
        "art_96",
        gravado,
        isr,
        None,
        "Art. 96 LISR: se suma al ingreso del mes y se aplica la tarifa mensual",
    )


def isr_art_174(gravado: Decimal, ordinario_mensual: Decimal, fecha: date) -> ISRExtraordinario:
    """Procedimiento del Art. 174 RLISR (fracciones I a V)."""
    if gravado <= 0:
        return ISRExtraordinario("art_174", gravado, CERO, CERO, "Art. 174 RLISR (nada gravado)")
    mensualizado = gravado / DIAS_ANIO * DIAS_MES_FISCAL  # fr. I
    con_ordinario = isr_mensual(redondear(ordinario_mensual + mensualizado), fecha)  # fr. II
    diferencia = con_ordinario - isr_mensual(ordinario_mensual, fecha)  # fr. III
    tasa = diferencia / mensualizado  # fr. V
    return ISRExtraordinario(
        "art_174",
        gravado,
        redondear(gravado * tasa),
        tasa,
        "Art. 174 RLISR: remuneración ÷ 365 × 30.4, tasa efectiva sobre lo gravado",
    )


def isr_extraordinario(
    gravado: Decimal, ordinario_mensual: Decimal, fecha: date, metodo: str
) -> ISRExtraordinario:
    """Despacha por el criterio del cliente (`isr_extraordinario` de `criterios.py`)."""
    if gravado < 0 or ordinario_mensual < 0:
        raise FiscalValidationError("Ni lo gravado ni el ingreso ordinario pueden ser negativos.")
    if metodo == "art_174":
        return isr_art_174(gravado, ordinario_mensual, fecha)
    if metodo == "art_96":
        return isr_art_96(gravado, ordinario_mensual, fecha)
    raise FiscalValidationError(f"Método de ISR extraordinario inválido: {metodo!r}.")


def isr_separacion(
    gravado: Decimal,
    ultimo_sueldo_mensual: Decimal,
    fecha: date,
    ordinario_mensual: Decimal = CERO,
) -> ISRExtraordinario:
    """
    ISR de la parte gravada de prima de antigüedad e indemnizaciones (Arts. 95 y 96).

    Con `gravado >= último sueldo mensual ordinario`: tasa = ISR(USMO) ÷ USMO.
    Si es menor: se suma a los demás ingresos del mes (`ordinario_mensual`) y se
    aplica la tarifa del Art. 96.
    """
    if gravado <= 0:
        return ISRExtraordinario("art_95", CERO, CERO, None, "Art. 93 fr. XIII: todo exento")
    if ultimo_sueldo_mensual <= 0:
        raise FiscalValidationError("El último sueldo mensual ordinario debe ser positivo.")
    if gravado < ultimo_sueldo_mensual:
        r = isr_art_96(gravado, ordinario_mensual, fecha)
        return ISRExtraordinario(
            "art_96",
            gravado,
            r.isr,
            None,
            "Art. 96 LISR: el pago es menor al último sueldo mensual ordinario, se suma "
            "a los demás ingresos del mes",
        )
    tasa = isr_mensual(ultimo_sueldo_mensual, fecha) / ultimo_sueldo_mensual
    return ISRExtraordinario(
        "art_95",
        gravado,
        redondear(gravado * tasa),
        tasa,
        "Arts. 95 y 96 LISR: tasa del último sueldo mensual ordinario",
    )
