"""
Constantes compartidas del sistema fiscal.

Centraliza diccionarios y valores que se usan en multiples modulos
para evitar duplicacion (principio DRY).

Los valores que cambian cada año (UMA, salario minimo) NO viven aqui como
constantes sueltas: se resuelven por fecha con `uma_vigente(fecha)` y
`salario_minimo_vigente(fecha, zona)`. La referencia documental con fuentes
esta en `knowledge_base/nomina/20_valores_referencia_2026.md`.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import Enum

from app.exceptions import FiscalValidationError
from app.redondeo import redondear as _redondear

# Nombres de meses del calendario fiscal
NOMBRES_MESES: dict[int, str] = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}

# Nombres de bimestres (formato completo)
NOMBRES_BIMESTRES: dict[int, str] = {
    1: "Enero-Febrero", 2: "Marzo-Abril", 3: "Mayo-Junio",
    4: "Julio-Agosto", 5: "Septiembre-Octubre", 6: "Noviembre-Diciembre",
}

# Nombres descriptivos de regimenes fiscales SAT
NOMBRES_REGIMEN: dict[str, str] = {
    "626": "RESICO (Regimen Simplificado de Confianza)",
    "612": "Actividad Empresarial y Profesional",
    "605": "Sueldos y Salarios",
    "606": "Arrendamiento",
    "625": "Plataformas Tecnologicas",
    "621": "Incorporacion Fiscal (RIF)",
}

# Tope de ingresos anuales para permanecer en RESICO ($3.5M)
TOPE_RESICO_ANUAL: float = 3_500_000.00

# Regimenes con pagos provisionales acumulativos (Art. 106/116 LISR).
# En estos regimenes cada mes se calcula sobre la base acumulada desde
# enero y se restan los ISR ya causados en meses anteriores.
REGIMENES_ACUMULATIVOS: set[str] = {"612", "606"}


# ============================================================
# Valores por vigencia: UMA y salario minimo
# ============================================================
#
# Las dos magnitudes cambian cada año, pero NO en la misma fecha, y esa
# asimetria es la fuente de error mas comun en enero:
#
#   UMA:            del 1-feb-N al 31-ene-(N+1)   (Art. 5 Ley UMA)
#   Salario minimo: del 1-ene-N al 31-dic-N       (Resolucion CONASAMI)
#
# En enero de 2026 conviven la UMA 2025 y el salario minimo 2026. Por eso
# ningun modulo debe capturar "la UMA" en una constante: siempre se pide
# por fecha.
#
# Los valores se declaran como Decimal DESDE CADENA. `Decimal(117.31)`
# arrastraria el ruido binario del float a cada tope derivado.

# Ejercicio que el sistema calcula por defecto cuando el llamador no
# especifica uno. MANTENIMIENTO: se actualiza cada enero junto con las
# tablas del ejercicio nuevo. No se deriva de date.today() a proposito:
# un motor fiscal no debe cambiar de resultado segun el dia en que corre.
EJERCICIO_DEFAULT: int = 2026


class ZonaSalarioMinimo(str, Enum):
    """Zona geografica que determina el salario minimo aplicable."""

    GENERAL = "general"
    ZLFN = "zlfn"  # Zona Libre de la Frontera Norte


# UMA diaria por año de vigencia.
# Fuente: INEGI, Comunicado de prensa 1/25 (DOF 09-01-2025) y 1/26
# (DOF 09-01-2026). Ver knowledge_base/nomina/20_valores_referencia_2026.md.
# Agregar un año requiere fuente oficial: no se extrapola.
UMA_DIARIA_POR_ANIO: dict[int, Decimal] = {
    2025: Decimal("113.14"),
    2026: Decimal("117.31"),
}

# Salario minimo general diario por año y zona.
# Fuente: Resolucion CONASAMI publicada en el DOF (09-12-2024 para 2025,
# 09-12-2025 para 2026).
SALARIO_MINIMO_POR_ANIO: dict[int, dict[ZonaSalarioMinimo, Decimal]] = {
    2025: {
        ZonaSalarioMinimo.GENERAL: Decimal("278.80"),
        ZonaSalarioMinimo.ZLFN: Decimal("419.88"),
    },
    2026: {
        ZonaSalarioMinimo.GENERAL: Decimal("315.04"),
        ZonaSalarioMinimo.ZLFN: Decimal("440.87"),
    },
}

def _anio_uma_vigente(fecha: date) -> int:
    """
    Año de la UMA que rige en `fecha`.

    La UMA del año N entra en vigor el 1 de febrero de N y rige hasta el
    31 de enero de N+1 (Art. 5 de la Ley para Determinar el Valor de la UMA).
    Por eso enero pertenece a la UMA del año anterior.
    """
    return fecha.year - 1 if fecha.month == 1 else fecha.year


def uma_vigente(fecha: date) -> Decimal:
    """
    UMA diaria vigente en `fecha`.

    Enero de 2026 devuelve la UMA 2025 ($113.14); del 1 de febrero de 2026
    en adelante, la UMA 2026 ($117.31).

    Raises:
        FiscalValidationError: si la fecha cae fuera de los años con fuente
            oficial cargada.
    """
    anio = _anio_uma_vigente(fecha)
    valor = UMA_DIARIA_POR_ANIO.get(anio)
    if valor is None:
        disponibles = ", ".join(str(a) for a in sorted(UMA_DIARIA_POR_ANIO))
        raise FiscalValidationError(
            f"No hay UMA cargada para la fecha {fecha.isoformat()} (correspondería a la "
            f"UMA {anio}). Años disponibles: {disponibles}. Para agregar un año hay que "
            f"citar el comunicado del INEGI y su publicación en el DOF."
        )
    return valor


def uma_mensual_vigente(fecha: date) -> Decimal:
    """
    UMA mensual vigente en `fecha` = diaria x 30.4, redondeada a 2 decimales.

    Art. 4 fr. II de la Ley para Determinar el Valor de la UMA. El redondeo
    va AQUI, antes de cualquier multiplicacion posterior: es lo que hace que
    el valor anual coincida con el que publica el INEGI.
    """
    return _redondear(uma_vigente(fecha) * Decimal("30.4"))


def uma_anual_vigente(fecha: date) -> Decimal:
    """
    UMA anual vigente en `fecha` = mensual (ya redondeada) x 12.

    Art. 4 fr. III de la Ley para Determinar el Valor de la UMA. Da
    $42,794.64 para 2026 y $41,273.52 para 2025, que son exactamente los
    valores publicados por el INEGI.

    OJO con el orden: redondear al final en vez de al mensual daria
    $42,794.69 para 2026 — cinco centavos de diferencia que se multiplican
    por cinco en el tope de deducciones personales.
    """
    return _redondear(uma_mensual_vigente(fecha) * 12)


def salario_minimo_vigente(fecha: date, zona: ZonaSalarioMinimo | str) -> Decimal:
    """
    Salario minimo general diario vigente en `fecha` para `zona`.

    A diferencia de la UMA, el salario minimo entra en vigor el 1 de enero.
    La zona es OBLIGATORIA: un default silencioso daria el piso de SBC
    equivocado a los patrones de la Zona Libre de la Frontera Norte.

    Raises:
        FiscalValidationError: si el año no tiene fuente oficial cargada o
            la zona no es valida.
    """
    del_anio = SALARIO_MINIMO_POR_ANIO.get(fecha.year)
    if del_anio is None:
        disponibles = ", ".join(str(a) for a in sorted(SALARIO_MINIMO_POR_ANIO))
        raise FiscalValidationError(
            f"No hay salario mínimo cargado para {fecha.year}. Años disponibles: "
            f"{disponibles}. Para agregar un año hay que citar la resolución de la "
            f"CONASAMI publicada en el DOF."
        )
    try:
        zona_valida = ZonaSalarioMinimo(zona)
    except ValueError as exc:
        validas = ", ".join(z.value for z in ZonaSalarioMinimo)
        raise FiscalValidationError(
            f"Zona de salario mínimo inválida: {zona!r}. Válidas: {validas}."
        ) from exc
    return del_anio[zona_valida]
