"""
Comparador de regimenes fiscales.

Simula ISR anual estimado para los 5 regimenes de personas fisicas
(626, 612, 606, 625, 605) y los ordena de menor a mayor costo fiscal.
Permite al contribuyente elegir el regimen que mas le conviene.
"""

from __future__ import annotations
from app.fiscal_engine.calculadora import calcular_isr_resico, calcular_isr_general
from app.schemas.comparador import ResultadoRegimen
from app.constants import TOPE_RESICO_ANUAL

# Umbral ingresos anuales para pago definitivo en plataformas (Art. 113-B LISR)
TOPE_PLATAFORMAS_DEFINITIVO: float = 300_000.00

NOMBRES_REGIMEN: dict[str, str] = {
    "626": "RESICO",
    "612": "Act. Empresarial",
    "606": "Arrendamiento",
    "625": "Plataformas Digitales",
    "605": "Sueldos y Salarios",
}


def _calcular_626(ingresos_m: float, ingresos_a: float) -> ResultadoRegimen:
    """RESICO: tasa fija mensual sobre ingresos brutos (Art. 113-E LISR)."""
    disponible = ingresos_a <= TOPE_RESICO_ANUAL
    notas: list[str] = ["Sin deducciones operativas para ISR"]

    if disponible:
        isr_mensual, _ = calcular_isr_resico(ingresos_m)
        isr_anual = round(isr_mensual * 12, 2)
    else:
        # Fuera de rango: referencia con tasa maxima
        isr_anual = round(ingresos_a * 0.025, 2)
        isr_mensual = round(isr_anual / 12, 2)
        notas.append(f"No disponible: ingresos anuales (${ingresos_a:,.0f}) superan el tope de $3,500,000")

    return ResultadoRegimen(
        regimen="626", nombre=NOMBRES_REGIMEN["626"],
        isr_anual=isr_anual, isr_mensual=isr_mensual,
        disponible=disponible, notas=notas,
    )


def _calcular_612(ingresos_a: float, gastos_a: float) -> ResultadoRegimen:
    """Actividad Empresarial / Honorarios: tabla progresiva sobre ingresos - gastos (Art. 152 LISR)."""
    base = max(ingresos_a - gastos_a, 0)
    isr_anual, _ = calcular_isr_general(base, es_anual=True)
    isr_anual = round(isr_anual, 2)
    notas = [f"Base gravable: ${base:,.2f} (ingresos - gastos deducibles)"]
    if gastos_a == 0:
        notas.append("Sin gastos declarados: misma base que Sueldos")
    return ResultadoRegimen(
        regimen="612", nombre=NOMBRES_REGIMEN["612"],
        isr_anual=isr_anual, isr_mensual=round(isr_anual / 12, 2),
        disponible=True, notas=notas,
    )


def _calcular_606(ingresos_a: float, gastos_a: float, predial_a: float) -> ResultadoRegimen:
    """
    Arrendamiento: tabla progresiva con mejor entre deduccion ciega (35%) y gastos reales.
    Art. 115 y 116 LISR.
    """
    ded_ciega = round(ingresos_a * 0.35 + predial_a, 2)
    ded_real = round(gastos_a + predial_a, 2)

    base_ciega = max(ingresos_a - ded_ciega, 0)
    base_real = max(ingresos_a - ded_real, 0)
    isr_ciega, _ = calcular_isr_general(base_ciega, es_anual=True)
    isr_real, _ = calcular_isr_general(base_real, es_anual=True)

    if isr_ciega <= isr_real:
        isr_anual = round(isr_ciega, 2)
        notas = [
            f"Deduccion ciega 35% = ${ded_ciega:,.2f} (conviene mas que gastos reales ${ded_real:,.2f})",
        ]
    else:
        isr_anual = round(isr_real, 2)
        notas = [
            f"Gastos reales = ${ded_real:,.2f} (convienen mas que deduccion ciega ${ded_ciega:,.2f})",
        ]
    if predial_a > 0:
        notas.append(f"Predial incluido: ${predial_a:,.2f} al ano")
    notas.append("Solo aplica a ingresos por renta de inmuebles")

    return ResultadoRegimen(
        regimen="606", nombre=NOMBRES_REGIMEN["606"],
        isr_anual=isr_anual, isr_mensual=round(isr_anual / 12, 2),
        disponible=True, notas=notas,
    )


def _calcular_625(ingresos_m: float, ingresos_a: float, gastos_a: float) -> ResultadoRegimen:
    """
    Plataformas Digitales: retenciones definitivas si ingresos <= $300k anuales (Art. 113-B LISR).
    Si superan $300k, declaran normalmente con Art. 152.
    """
    notas: list[str] = []

    if ingresos_a <= TOPE_PLATAFORMAS_DEFINITIVO:
        # Pago definitivo: la plataforma ya retiene entre 1% y 4% segun el tipo de servicio.
        # Se estima con las tasas RESICO (1-2.5%) como aproximacion, ya que son similares.
        isr_mensual, _ = calcular_isr_resico(ingresos_m)
        isr_anual = round(isr_mensual * 12, 2)
        notas.append("Pago definitivo — la plataforma retiene ISR en la fuente (sin declaracion mensual)")
        notas.append("ISR estimado con tasas similares a las retenciones de plataformas (1-4%)")
    else:
        base = max(ingresos_a - gastos_a, 0)
        isr_anual, _ = calcular_isr_general(base, es_anual=True)
        isr_anual = round(isr_anual, 2)
        notas.append(f"Ingresos > $300,000: debes declarar normalmente (Art. 113-B LISR)")
        notas.append("Las retenciones de la plataforma se acreditan contra el ISR calculado")

    notas.append("Solo aplica si operas a traves de plataformas digitales (Uber, Rappi, Airbnb, etc.)")

    return ResultadoRegimen(
        regimen="625", nombre=NOMBRES_REGIMEN["625"],
        isr_anual=isr_anual, isr_mensual=round(isr_anual / 12, 2),
        disponible=True, notas=notas,
    )


def _calcular_605(ingresos_a: float) -> ResultadoRegimen:
    """
    Sueldos y Salarios: tabla progresiva sobre ingresos brutos (Art. 96/152 LISR).
    El patron retiene mensualmente; la declaracion anual puede generar saldo a favor.
    Sin deducciones operativas (solo personales en declaracion anual, no consideradas aqui).
    """
    isr_anual, _ = calcular_isr_general(ingresos_a, es_anual=True)
    isr_anual = round(isr_anual, 2)
    return ResultadoRegimen(
        regimen="605", nombre=NOMBRES_REGIMEN["605"],
        isr_anual=isr_anual, isr_mensual=round(isr_anual / 12, 2),
        disponible=True,
        notas=[
            "Solo aplica si eres empleado con relacion laboral formal",
            "El patron retiene y entera el ISR mensualmente",
            "Sin deducciones de gastos operativos (solo personales en declaracion anual)",
        ],
    )


def calcular_todos_regimenes(
    ingresos_mensuales: float,
    gastos_mensuales: float,
    predial_mensual: float = 0.0,
) -> tuple[list[ResultadoRegimen], str, float, str]:
    """
    Calcula ISR estimado anual para los 5 regimenes de personas fisicas y los ordena
    de menor a mayor costo. Retorna (resultados, regimen_recomendado, ahorro_maximo, recomendacion).

    Args:
        ingresos_mensuales: Ingresos mensuales promedio estimados.
        gastos_mensuales: Gastos mensuales deducibles estimados.
        predial_mensual: Impuesto predial mensual (para 606).

    Returns:
        Tuple con: lista de ResultadoRegimen ordenada, codigo del recomendado,
                   diferencia maxima entre disponibles, texto de recomendacion.
    """
    ingresos_a = ingresos_mensuales * 12
    gastos_a = gastos_mensuales * 12
    predial_a = predial_mensual * 12

    resultados = [
        _calcular_626(ingresos_mensuales, ingresos_a),
        _calcular_612(ingresos_a, gastos_a),
        _calcular_606(ingresos_a, gastos_a, predial_a),
        _calcular_625(ingresos_mensuales, ingresos_a, gastos_a),
        _calcular_605(ingresos_a),
    ]

    # Ordenar por ISR anual (menor primero), primero los disponibles
    resultados.sort(key=lambda r: (not r.disponible, r.isr_anual))

    # Recomendacion: regimen disponible con menor ISR
    disponibles = [r for r in resultados if r.disponible]
    if not disponibles:
        return resultados, "", 0.0, "No se encontro ningun regimen disponible."

    mejor = disponibles[0]
    peor = disponibles[-1]
    ahorro = round(peor.isr_anual - mejor.isr_anual, 2)

    if ahorro == 0:
        recomendacion = (
            f"Todos los regimenes disponibles resultan en ISR similar (${mejor.isr_anual:,.2f} anuales). "
            f"Considera la carga administrativa: RESICO es la mas simple si aplica."
        )
    else:
        recomendacion = (
            f"{mejor.nombre} es el regimen mas conveniente con ${mejor.isr_anual:,.2f} de ISR anual. "
            f"Ahorras ${ahorro:,.2f} al año vs {peor.nombre} (${peor.isr_anual:,.2f})."
        )

    return resultados, mejor.regimen, ahorro, recomendacion
