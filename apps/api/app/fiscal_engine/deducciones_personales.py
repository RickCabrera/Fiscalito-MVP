"""
Calculo de deducciones personales para declaracion anual.

Aplica principalmente a asalariados (regimen 605) pero cualquier persona
fisica puede usarlas en su declaracion anual.
Fuente: Art. 151 LISR.
"""

from __future__ import annotations
from dataclasses import dataclass
from app.fiscal_engine.tablas_isr import UMA_DIARIA_2026


# Topes de colegiaturas por nivel educativo (Art. 1.8 Decreto)
TOPES_COLEGIATURAS: dict[str, float] = {
    "preescolar": 14_200.00,
    "primaria": 12_900.00,
    "secundaria": 19_900.00,
    "profesional_tecnico": 17_100.00,
    "bachillerato": 24_500.00,
}

# Tope global: 5 UMAs anuales
TOPE_5_UMAS_ANUALES: float = 5 * UMA_DIARIA_2026 * 365  # $213,926.50

# Tope de donativos: 7% de ingresos acumulables del ejercicio anterior
TASA_TOPE_DONATIVOS: float = 0.07

# Tope aportaciones voluntarias retiro: 10% de ingresos o 5 UMAs anuales
TASA_TOPE_APORTACIONES_RETIRO: float = 0.10

# Tope gastos funerarios: 1 UMA anual
TOPE_FUNERAL: float = UMA_DIARIA_2026 * 365


@dataclass
class DesgloseDeduccion:
    """Desglose de una deduccion individual."""
    concepto: str
    monto_solicitado: float
    tope_aplicable: float | None
    monto_aceptado: float


@dataclass
class ResultadoDeduccionesPersonales:
    """Resultado del calculo de deducciones personales."""
    desglose: list[DesgloseDeduccion]
    total_solicitado: float
    total_antes_tope: float
    tope_global: float
    tope_tipo: str  # "5_umas" o "15_porciento"
    total_deducible: float
    excedente_no_aprovechado: float


def calcular_deducciones_personales(
    ingresos_anuales: float,
    gastos_medicos: float = 0.0,
    colegiaturas: float = 0.0,
    nivel_educativo: str = "",
    intereses_hipotecarios: float = 0.0,
    donativos: float = 0.0,
    aportaciones_voluntarias_retiro: float = 0.0,
    seguros_gastos_medicos: float = 0.0,
    transporte_escolar: float = 0.0,
    funeral: float = 0.0,
) -> ResultadoDeduccionesPersonales:
    """
    Calcula deducciones personales aplicando topes individuales y el tope global.

    El tope global es el MENOR entre:
    - 5 UMAs anuales ($213,926.50 en 2026)
    - 15% de los ingresos totales del contribuyente
    """
    desglose: list[DesgloseDeduccion] = []

    # 1. Gastos medicos (sin tope individual, solo tope global)
    med_aceptado = max(gastos_medicos, 0.0)
    desglose.append(DesgloseDeduccion(
        concepto="Gastos medicos",
        monto_solicitado=gastos_medicos,
        tope_aplicable=None,
        monto_aceptado=med_aceptado,
    ))

    # 2. Colegiaturas (con tope por nivel)
    tope_colegiatura = TOPES_COLEGIATURAS.get(nivel_educativo.lower(), 0.0) if nivel_educativo else None
    if tope_colegiatura is not None:
        col_aceptado = min(max(colegiaturas, 0.0), tope_colegiatura)
    else:
        col_aceptado = max(colegiaturas, 0.0)
    desglose.append(DesgloseDeduccion(
        concepto=f"Colegiaturas ({nivel_educativo or 'sin nivel'})",
        monto_solicitado=colegiaturas,
        tope_aplicable=tope_colegiatura,
        monto_aceptado=col_aceptado,
    ))

    # 3. Intereses hipotecarios (intereses reales, sin tope individual aparte del global)
    hip_aceptado = max(intereses_hipotecarios, 0.0)
    desglose.append(DesgloseDeduccion(
        concepto="Intereses hipotecarios reales",
        monto_solicitado=intereses_hipotecarios,
        tope_aplicable=None,
        monto_aceptado=hip_aceptado,
    ))

    # 4. Donativos (tope: 7% de ingresos acumulables)
    tope_donativos = ingresos_anuales * TASA_TOPE_DONATIVOS
    don_aceptado = min(max(donativos, 0.0), tope_donativos)
    desglose.append(DesgloseDeduccion(
        concepto="Donativos",
        monto_solicitado=donativos,
        tope_aplicable=tope_donativos,
        monto_aceptado=don_aceptado,
    ))

    # 5. Aportaciones voluntarias retiro (tope: 10% ingresos o 5 UMAs anuales)
    tope_retiro = min(ingresos_anuales * TASA_TOPE_APORTACIONES_RETIRO, TOPE_5_UMAS_ANUALES)
    ret_aceptado = min(max(aportaciones_voluntarias_retiro, 0.0), tope_retiro)
    desglose.append(DesgloseDeduccion(
        concepto="Aportaciones voluntarias retiro",
        monto_solicitado=aportaciones_voluntarias_retiro,
        tope_aplicable=tope_retiro,
        monto_aceptado=ret_aceptado,
    ))

    # 6. Seguros de gastos medicos (sin tope individual)
    seg_aceptado = max(seguros_gastos_medicos, 0.0)
    desglose.append(DesgloseDeduccion(
        concepto="Seguros de gastos medicos",
        monto_solicitado=seguros_gastos_medicos,
        tope_aplicable=None,
        monto_aceptado=seg_aceptado,
    ))

    # 7. Transporte escolar (cuando es obligatorio)
    trans_aceptado = max(transporte_escolar, 0.0)
    desglose.append(DesgloseDeduccion(
        concepto="Transporte escolar obligatorio",
        monto_solicitado=transporte_escolar,
        tope_aplicable=None,
        monto_aceptado=trans_aceptado,
    ))

    # 8. Gastos funerarios (tope: 1 UMA anual)
    fun_aceptado = min(max(funeral, 0.0), TOPE_FUNERAL)
    desglose.append(DesgloseDeduccion(
        concepto="Gastos funerarios",
        monto_solicitado=funeral,
        tope_aplicable=TOPE_FUNERAL,
        monto_aceptado=fun_aceptado,
    ))

    # Suma antes de tope global
    total_solicitado = sum(d.monto_solicitado for d in desglose)
    total_antes_tope = sum(d.monto_aceptado for d in desglose)

    # Tope global: el MENOR entre 5 UMAs anuales y 15% de ingresos
    tope_15_porciento = ingresos_anuales * 0.15
    if tope_15_porciento < TOPE_5_UMAS_ANUALES:
        tope_global = tope_15_porciento
        tope_tipo = "15_porciento"
    else:
        tope_global = TOPE_5_UMAS_ANUALES
        tope_tipo = "5_umas"

    total_deducible = min(total_antes_tope, tope_global)
    excedente = max(total_antes_tope - tope_global, 0.0)

    return ResultadoDeduccionesPersonales(
        desglose=desglose,
        total_solicitado=round(total_solicitado, 2),
        total_antes_tope=round(total_antes_tope, 2),
        tope_global=round(tope_global, 2),
        tope_tipo=tope_tipo,
        total_deducible=round(total_deducible, 2),
        excedente_no_aprovechado=round(excedente, 2),
    )
