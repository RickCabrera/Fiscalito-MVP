"""
Subsidio para el empleo.

Fuente: Decreto que modifica el diverso que otorga el subsidio para el empleo,
DOF 31-12-2025 (nota 5777649), vigente desde el 1-ene-2026.

EL DECRETO FIJA EL PORCENTAJE, NO EL PESO
-----------------------------------------
El articulado manda "multiplicar el valor mensual de la UMA por 15.02%", y su
transitorio manda 15.59% para enero de 2026. El importe de $536.22 que circula
en fuentes secundarias viene de los CONSIDERANDOS del decreto y no reconcilia
con la formula: 15.02% x $3,566.22 = $535.65 (harian falta 15.036%). El
transitorio de enero, en cambio, cuadra al centavo: 15.59% x $3,439.46 =
$536.21.

Por eso este modulo CALCULA el subsidio desde el porcentaje y la UMA vigente,
y nunca hardcodea el peso. Ver knowledge_base/nomina/20_valores_referencia_2026.md §4.

DOS VIGENCIAS EN EL MISMO CALCULO
---------------------------------
El porcentaje depende del mes (enero tiene el suyo por transitorio) y la UMA
mensual depende de la fecha con su propia regla (la UMA de un año rige del
1-feb al 31-ene). En enero de 2026 se combinan el porcentaje transitorio y la
UMA 2025 — las dos excepciones a la vez.
"""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from app.constants import uma_mensual_vigente
from app.exceptions import FiscalValidationError

_DOS_DECIMALES = Decimal("0.01")
_DIAS_MES_FISCAL = Decimal("30.4")


def _redondear(valor: Decimal) -> Decimal:
    return valor.quantize(_DOS_DECIMALES, rounding=ROUND_HALF_UP)


# Porcentaje de la UMA mensual, por ejercicio. `enero` recoge el transitorio.
# Fuente: Decreto DOF 31-12-2025 y su articulo transitorio.
PORCENTAJE_SUBSIDIO_POR_EJERCICIO: dict[int, dict[str, Decimal]] = {
    2026: {"enero": Decimal("0.1559"), "resto": Decimal("0.1502")},
}

# Tope de ingresos gravados mensuales para tener derecho al subsidio.
# Es un monto fijo del decreto, no una cantidad de UMA.
TOPE_INGRESO_MENSUAL_POR_EJERCICIO: dict[int, Decimal] = {
    2026: Decimal("11492.66"),
}


def _del_ejercicio(tabla: dict, fecha: date, que: str):
    valor = tabla.get(fecha.year)
    if valor is None:
        disponibles = ", ".join(str(a) for a in sorted(tabla))
        raise FiscalValidationError(
            f"No hay {que} del subsidio para el empleo cargado para el ejercicio "
            f"{fecha.year}. Ejercicios disponibles: {disponibles}. Para agregar uno hay "
            f"que citar el decreto publicado en el DOF."
        )
    return valor


def porcentaje_subsidio_vigente(fecha: date) -> Decimal:
    """
    Porcentaje de la UMA mensual aplicable en `fecha`.

    Enero tiene su propio porcentaje por articulo transitorio: sube para
    compensar que en enero todavia rige la UMA del año anterior.
    """
    porcentajes = _del_ejercicio(PORCENTAJE_SUBSIDIO_POR_EJERCICIO, fecha, "porcentaje")
    return porcentajes["enero"] if fecha.month == 1 else porcentajes["resto"]


def tope_ingreso_subsidio(fecha: date) -> Decimal:
    """Tope de ingresos gravados MENSUALES para tener derecho al subsidio."""
    return _del_ejercicio(TOPE_INGRESO_MENSUAL_POR_EJERCICIO, fecha, "tope de ingresos")


def subsidio_mensual(fecha: date) -> Decimal:
    """
    Subsidio de un mes completo: porcentaje vigente x UMA mensual vigente.

    Da $536.21 en enero de 2026 (15.59% x UMA 2025) y $535.65 de febrero a
    diciembre (15.02% x UMA 2026).
    """
    return _redondear(porcentaje_subsidio_vigente(fecha) * uma_mensual_vigente(fecha))


def subsidio_empleo(
    fecha: date, ingreso_gravado_mensual: Decimal, dias_periodo: int = 30
) -> Decimal:
    """
    Subsidio para el empleo del periodo.

    Args:
        fecha: fecha de pago. Determina el porcentaje y la UMA.
        ingreso_gravado_mensual: ingreso gravado MENSUAL del trabajador. El
            tope del decreto es mensual, asi que en nominas semanales o
            quincenales el llamador (F1-04) es responsable de traer una cifra
            mensual. Si esa cifra se proyecta (semanal x 30.4/7) o se acumula
            por mes calendario es una decision abierta — ver
            docs/decisiones-nomina.md D11. Este modulo no la toma.
        dias_periodo: dias que cubre el pago. 30 = mes completo; para periodos
            menores se prorratea `subsidio_mensual / 30.4 x dias`.

    Returns:
        Subsidio del periodo, redondeado a 2 decimales. **Cero** si el ingreso
        excede el tope: es un corte duro, no una degradacion gradual.

    Nota: quien acredita el subsidio contra el ISR es F1-04. Desde 2024 el
    subsidio solo reduce el ISR hasta cero; el remanente no se entrega en
    efectivo.
    """
    if ingreso_gravado_mensual < 0:
        raise FiscalValidationError(
            f"El ingreso gravado no puede ser negativo: {ingreso_gravado_mensual}."
        )
    if dias_periodo <= 0:
        raise FiscalValidationError(
            f"Los días del periodo deben ser positivos: {dias_periodo}."
        )
    if ingreso_gravado_mensual > tope_ingreso_subsidio(fecha):
        return Decimal("0.00")

    mensual = subsidio_mensual(fecha)
    if dias_periodo >= 30:
        return mensual
    return _redondear(mensual / _DIAS_MES_FISCAL * dias_periodo)
