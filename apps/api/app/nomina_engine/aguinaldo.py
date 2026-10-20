"""
Aguinaldo: importe, exención e ISR. (P4-08) — funciones puras.

FUENTES
-------
- **LFT Art. 87**: aguinaldo anual de por lo menos 15 días de salario, pagadero
  antes del 20 de diciembre; quien no cumplió el año tiene derecho a la parte
  proporcional "conforme al tiempo que hubieren trabajado".
- **LISR Art. 93 fr. XIV**: la gratificación anual está exenta hasta el salario
  mínimo elevado a 30 días, leído en **UMA** por el Decreto de desindexación
  (DOF 27-01-2016). La exención es **por año calendario**: si ya se pagó una
  parte exenta (anticipo), se descuenta.
- ISR: Art. 96 LISR o Art. 174 RLISR, a elección del retenedor
  (`isr_extraordinario.py`, criterio `isr_extraordinario` del cliente).

# DECISIÓN PROVISIONAL (nocturno): la proporción es días trabajados ÷ 365 aun en
# año bisiesto, que es la práctica de la mayoría del software de nómina. La LFT
# no fija el divisor.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.constants import uma_vigente
from app.exceptions import FiscalValidationError
from app.nomina_engine.integracion import DIAS_AGUINALDO_DE_LEY
from app.nomina_engine.isr_extraordinario import ISRExtraordinario, isr_extraordinario
from app.redondeo import redondear

CERO = Decimal("0.00")
DIAS_ANIO = Decimal("365")
UMAS_EXENCION_AGUINALDO = 30  # Art. 93 fr. XIV LISR


def dias_trabajados_en_el_anio(
    fecha_alta: date | None, anio: int, hasta: date | None = None
) -> int:
    """Días naturales del año calendario con relación laboral (inclusivo)."""
    inicio = date(anio, 1, 1)
    fin = hasta or date(anio, 12, 31)
    if fecha_alta and fecha_alta > inicio:
        inicio = fecha_alta
    if fin < inicio:
        return 0
    return (fin - inicio).days + 1


def aguinaldo_proporcional(
    salario_diario: Decimal, dias_aguinaldo: int, dias_trabajados: int
) -> Decimal:
    """
    Aguinaldo = salario diario × días de aguinaldo × días trabajados ÷ 365.

    Con el año completo (365 o más días) es el aguinaldo entero.
    """
    if dias_aguinaldo < DIAS_AGUINALDO_DE_LEY:
        raise FiscalValidationError(
            f"El aguinaldo no puede ser menor a {DIAS_AGUINALDO_DE_LEY} días (Art. 87 LFT)."
        )
    if salario_diario <= 0 or dias_trabajados < 0:
        raise FiscalValidationError("Salario y días trabajados deben ser positivos.")
    proporcion = min(Decimal(dias_trabajados), DIAS_ANIO) / DIAS_ANIO
    return redondear(salario_diario * dias_aguinaldo * proporcion)


def exencion_aguinaldo(fecha_pago: date, exento_ya_aplicado: Decimal = CERO) -> Decimal:
    """Tope exento disponible: 30 UMA del año menos lo ya exentado en el año."""
    tope = redondear(uma_vigente(fecha_pago) * UMAS_EXENCION_AGUINALDO)
    return max(tope - exento_ya_aplicado, CERO)


@dataclass(frozen=True)
class ResultadoAguinaldo:
    """El aguinaldo de un trabajador, partido y con su ISR."""

    dias_trabajados: int
    importe: Decimal
    exento: Decimal
    gravado: Decimal
    isr: ISRExtraordinario
    neto: Decimal
    fundamento: str


def calcular_aguinaldo(
    salario_diario: Decimal,
    dias_aguinaldo: int,
    dias_trabajados: int,
    fecha_pago: date,
    ingreso_ordinario_mensual: Decimal,
    metodo_isr: str = "art_96",
    exento_ya_aplicado: Decimal = CERO,
) -> ResultadoAguinaldo:
    """
    Aguinaldo proporcional, exención del Art. 93 fr. XIV e ISR.

    `ingreso_ordinario_mensual`: sueldo gravado del mes (lo usan los dos métodos).
    """
    importe = aguinaldo_proporcional(salario_diario, dias_aguinaldo, dias_trabajados)
    exento = min(importe, exencion_aguinaldo(fecha_pago, exento_ya_aplicado))
    gravado = importe - exento
    isr = isr_extraordinario(gravado, ingreso_ordinario_mensual, fecha_pago, metodo_isr)
    return ResultadoAguinaldo(
        dias_trabajados=dias_trabajados,
        importe=importe,
        exento=exento,
        gravado=gravado,
        isr=isr,
        neto=importe - isr.isr,
        fundamento="Art. 87 LFT; Art. 93 fr. XIV LISR (30 UMA); " + isr.fundamento,
    )
