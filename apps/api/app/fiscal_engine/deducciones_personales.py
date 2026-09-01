"""
Calculo de deducciones personales para declaracion anual.

Aplica principalmente a asalariados (regimen 605) pero cualquier persona
fisica puede usarlas en su declaracion anual.
Fuente: Art. 151 LISR.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.constants import EJERCICIO_DEFAULT, uma_anual_vigente

# Topes de colegiaturas por nivel educativo (Art. 1.8 Decreto)
TOPES_COLEGIATURAS: dict[str, float] = {
    "preescolar": 14_200.00,
    "primaria": 12_900.00,
    "secundaria": 19_900.00,
    "profesional_tecnico": 17_100.00,
    "bachillerato": 24_500.00,
}

# Numero de UMA anuales del tope global (Art. 151 ultimo parrafo LISR)
UMAS_TOPE_GLOBAL: int = 5

# Tope de donativos: 7% de ingresos acumulables del ejercicio anterior
TASA_TOPE_DONATIVOS: float = 0.07

# Tope aportaciones voluntarias retiro: 10% de ingresos o 5 UMAs anuales
TASA_TOPE_APORTACIONES_RETIRO: float = 0.10


def _uma_anual_del_ejercicio(ejercicio: int) -> float:
    """
    Valor anual de la UMA del ejercicio, como float.

    El motor fiscal viejo trabaja en float; `app.constants` es Decimal. La
    coercion se hace aqui, explicita y en un solo lugar. `nomina_engine`
    (PLAN_NOMINA §3.1) consume el Decimal directo, sin pasar por aqui.

    El 31 de diciembre resuelve siempre a la UMA del propio ejercicio: la
    UMA de un año rige hasta el 31 de enero del siguiente.
    """
    return float(uma_anual_vigente(date(ejercicio, 12, 31)))


def tope_global_deducciones(ejercicio: int = EJERCICIO_DEFAULT) -> float:
    """
    Tope global de deducciones personales: 5 veces el valor ANUAL de la UMA.

    Art. 151 ultimo parrafo LISR ("cinco veces el valor anual de la Unidad de
    Medida y Actualizacion"). El valor anual es la magnitud que publica el
    INEGI (Art. 4 fr. III de la Ley para Determinar el Valor de la UMA), NO
    `UMA diaria x 365`: esa formula es una herencia del viejo "salario minimo
    elevado al año" y da $214,090.75 en vez de los $213,973.20 correctos.
    """
    return round(UMAS_TOPE_GLOBAL * _uma_anual_del_ejercicio(ejercicio), 2)


def tope_gastos_funerarios(ejercicio: int = EJERCICIO_DEFAULT) -> float:
    """
    Tope de gastos funerarios: 1 UMA anual (Art. 151 fr. II LISR).

    DECISIÓN PROVISIONAL (nocturno): la fraccion II dice "elevado al año", no
    "el valor anual de la UMA" como el ultimo parrafo. Las dos lecturas son
    defendibles: el valor anual publicado por el INEGI ($42,794.64 en 2026) o
    `diaria x 365` ($42,818.15). Se toma la primera porque es la mas
    conservadora — tope menor, deduccion menor — y porque es la que ya usa
    `knowledge_base/11_deducciones_personales.md`. Diferencia: $23.51.
    Pendiente de confirmar con la contadora.
    """
    return round(_uma_anual_del_ejercicio(ejercicio), 2)

# NO se exponen los topes como constantes de modulo. Una constante evaluada al
# import congela el ejercicio por defecto, y el siguiente que la importe para
# otro ejercicio obtiene un numero mal en silencio — que es exactamente el bug
# que esta tarea vino a matar. Pide el tope por ejercicio:
#   tope_global_deducciones(ejercicio) / tope_gastos_funerarios(ejercicio)


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
    ejercicio: int = EJERCICIO_DEFAULT,
) -> ResultadoDeduccionesPersonales:
    """
    Calcula deducciones personales aplicando topes individuales y el tope global.

    El tope global es el MENOR entre:
    - 5 veces el valor anual de la UMA del ejercicio ($213,973.20 en 2026)
    - 15% de los ingresos totales del contribuyente

    Args:
        ejercicio: año fiscal al que corresponden las deducciones. Determina
            que UMA se usa: el ejercicio 2025 se topa con la UMA 2025 y el
            2026 con la UMA 2026. Un ejercicio sin fuente oficial cargada
            levanta FiscalValidationError.
    """
    tope_5_umas = tope_global_deducciones(ejercicio)
    tope_funeral = tope_gastos_funerarios(ejercicio)
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
    tope_colegiatura = (
        TOPES_COLEGIATURAS.get(nivel_educativo.lower(), 0.0) if nivel_educativo else None
    )
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
    tope_retiro = min(ingresos_anuales * TASA_TOPE_APORTACIONES_RETIRO, tope_5_umas)
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
    fun_aceptado = min(max(funeral, 0.0), tope_funeral)
    desglose.append(DesgloseDeduccion(
        concepto="Gastos funerarios",
        monto_solicitado=funeral,
        tope_aplicable=tope_funeral,
        monto_aceptado=fun_aceptado,
    ))

    # Suma antes de tope global
    total_solicitado = sum(d.monto_solicitado for d in desglose)
    total_antes_tope = sum(d.monto_aceptado for d in desglose)

    # Tope global: el MENOR entre 5 UMAs anuales y 15% de ingresos
    tope_15_porciento = ingresos_anuales * 0.15
    if tope_15_porciento < tope_5_umas:
        tope_global = tope_15_porciento
        tope_tipo = "15_porciento"
    else:
        tope_global = tope_5_umas
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
