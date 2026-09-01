"""
Orquestador de nomina de un periodo. **No es motor.**

Toma la plantilla y las incidencias que devolvio el checador (D-04) y llama,
por empleado, a `clamp_sbc` -> `armar_recibo` -> `cuotas_empleado`, y al final
a `consolidado_mensual` / `consolidado_bimestral`. **No reimplementa una sola
formula fiscal.** La unica aritmetica propia es `sueldo = salario_diario x
dias_pagados`, y pasa por `redondear`. La unica **decision** propia es la de
abajo, y esta declarada.

Si algun dia aparece un `if` fiscal en este archivo, esta en el archivo
equivocado: el motor vive en `cuotas.py`, `isr_nomina.py` y `armado.py`.

LA EXCEPCION, Y ESTA DECLARADA
------------------------------
`ingreso_gravado_mensual = SBC x 30.4` **si es una decision fiscal tomada
aqui**, no una traduccion: es la linea que decide quien tiene derecho a
subsidio. §D11 la dejo abierta a proposito —`isr_nomina` no la toma— y alguien
tiene que tomarla para que el endpoint responda. Va marcada como DECISION
PROVISIONAL en el codigo y documentada en §D19. No se cuenta como "traduccion".

LO QUE EL CONSOLIDADO DE ESTE PERIODO **NO** ES
-----------------------------------------------
`porcion_mensual` y `porcion_bimestral` clasifican los ramos por su
periodicidad de entero (Art. 39 LSS) pero suman **lo devengado en este
periodo**. Una quincena trae **media** mensualidad de EyM/IyV y **un doceavo**
de bimestre de Retiro/CEAV/Infonavit. Presentarlo como "lo que se paga al mes"
seria afirmar un numero legal falso; por eso los campos no se llaman
`consolidado_*` y por eso la respuesta lleva `advertencias`.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.constants import DIAS_MES_FISCAL
from app.exceptions import FiscalValidationError
from app.nomina_engine.armado import armar_recibo
from app.nomina_engine.ceav import es_trabajador_de_salario_minimo
from app.nomina_engine.cuotas import (
    DiasDelPeriodo,
    consolidado_bimestral,
    consolidado_mensual,
    cuotas_empleado,
)
from app.nomina_engine.integracion import clamp_sbc
from app.nomina_engine.isr_nomina import Percepcion

# Re-exportados a proposito: `calcular_periodo` es la puerta de entrada del
# modulo y quien la usa espera encontrar aqui sus tipos.
from app.nomina_engine.periodo_tipos import (  # noqa: F401
    EmpleadoPeriodo,
    IncidenciasPeriodo,
    ReciboPeriodo,
    ResultadoPeriodo,
)
from app.redondeo import redondear

# Clave de `c_TipoPercepcion` del sueldo, y clave interna que usa el patron del
# caso real. La interna NO se deriva del tipo: en las fixtures conviven
# `Clave="P019"` con `TipoPercepcion="020"`.
CLAVE_PERCEPCION_SUELDO = "001"
CLAVE_INTERNA_SUELDO = "P001"

# Umbral a partir del cual el ausentismo prolongado deja de ser rutina y hay
# que mirarlo a mano.
#
# NO SE AFIRMA QUE CONCEDE EL ART. 31 LSS, a proposito. El tratamiento del
# ausentismo por ramo esta marcado **PROVISIONAL** en
# `knowledge_base/nomina/22_cuotas_imss_infonavit_2026.md` y en §D3 —pendiente
# de confirmar con la contadora—, y no hay en el repo ninguna transcripcion del
# articulo contra el DOF. Una advertencia que le dijera al patron que "queda
# liberado de todas las cuotas" seria una afirmacion legal sin fuente dirigida
# a quien entera, y ademas contradiria al propio motor: §D3 mantiene
# Enfermedades y Maternidad a cargo del patron aun con ausentismo, asi que
# "todas" no puede ser cierto en la lectura que este codigo implementa.
DIAS_AUSENTISMO_REVISION_MANUAL = 7




def _emparejar(
    empleados: tuple[EmpleadoPeriodo, ...], incidencias: tuple[IncidenciasPeriodo, ...]
) -> dict[str, IncidenciasPeriodo]:
    """
    Cruza plantilla contra incidencias. Un descuadre **levanta**.

    Saltarse un empleado sin incidencias produciria una nomina que se ve
    completa y le falta gente; saltarse una incidencia huerfana esconderia un
    alta con el numero equivocado en el checador.
    """
    por_numero = {i.empleado_no: i for i in incidencias}
    de_plantilla = {e.empleado_no for e in empleados}
    sin_incidencias = sorted(de_plantilla - set(por_numero))
    if sin_incidencias:
        raise FiscalValidationError(
            f"Estos empleados no traen incidencias del periodo: "
            f"{', '.join(sin_incidencias)}. Cierra el periodo antes de calcular."
        )
    huerfanas = sorted(set(por_numero) - de_plantilla)
    if huerfanas:
        raise FiscalValidationError(
            f"Hay incidencias de empleados que no están en la plantilla: "
            f"{', '.join(huerfanas)}. Suele ser un alta con el employeeNo "
            f"equivocado en el checador."
        )
    return por_numero


def _advertencias(
    resultados: tuple[ReciboPeriodo, ...], dias_periodo_nomina: int
) -> tuple[str, ...]:
    avisos = [
        f"Las cuotas son la porción devengada en este periodo de "
        f"{dias_periodo_nomina} días naturales, NO el entero mensual ni el "
        f"bimestral del Art. 39 LSS.",
    ]
    pasados = sorted(
        r.empleado_no
        for r in resultados
        if r.dias.dias_ausentismo > DIAS_AUSENTISMO_REVISION_MANUAL
    )
    if pasados:
        avisos.append(
            f"Estos empleados superan {DIAS_AUSENTISMO_REVISION_MANUAL} días de "
            f"ausentismo en el periodo: {', '.join(pasados)}. El ausentismo prolongado "
            f"puede tener un tratamiento distinto que el motor NO aplica: aquí se cobran "
            f"las cuotas completas de cada ramo, que es la dirección conservadora (cobra "
            f"de más, nunca de menos). Requiere revisión manual."
        )
    return tuple(avisos)


def calcular_periodo(
    empleados: tuple[EmpleadoPeriodo, ...],
    incidencias: tuple[IncidenciasPeriodo, ...],
    fecha_pago: date,
    prima_riesgo: Decimal,
    clave_periodicidad: str,
    dias_pagados_override: int | None = None,
) -> ResultadoPeriodo:
    """
    Calcula la nomina del periodo delegando todo al motor.

    Args:
        fecha_pago: **fecha de pago**, no fin de periodo. Es la que decide la
            vigencia de UMA, salario minimo, tarifa del Anexo 8 y el
            transitorio de enero del subsidio. Una quincena que cierra el
            31-ene y se paga el 5-feb se calcula con los valores de febrero.
        prima_riesgo: prima de Riesgos de Trabajo de la empresa. No es tasa de
            ley: se autodetermina cada febrero (Art. 74 LSS), y por eso no
            tiene default.
        dias_pagados_override: fuerza los dias pagados de todos los empleados.
            Sin el, `dias_pagados = dias_periodo - faltas`.

    Raises:
        FiscalValidationError: si plantilla e incidencias no cuadran, o si el
            motor rechaza algun parametro.
    """
    if not empleados:
        raise FiscalValidationError("La plantilla del periodo no puede estar vacía.")
    por_numero = _emparejar(empleados, incidencias)
    # Es UN periodo: todos comparten sus dias naturales. Si no, alguien mezcló
    # dos cierres y el consolidado sumaría cosas de periodos distintos.
    dias_distintos = sorted({i.dias_periodo for i in incidencias})
    if len(dias_distintos) > 1:
        raise FiscalValidationError(
            f"Las incidencias traen periodos de distinta duración: {dias_distintos} días. "
            f"Un solo cierre no puede mezclar periodos."
        )
    dias_del_periodo = dias_distintos[0]

    resultados: list[ReciboPeriodo] = []
    for empleado in empleados:
        inc = por_numero[empleado.empleado_no]
        sbc = clamp_sbc(empleado.salario_diario_integrado, fecha_pago, empleado.zona)
        dias = DiasDelPeriodo(
            dias_periodo=inc.dias_periodo,
            dias_ausentismo=inc.dias_ausentismo,
            dias_incapacidad=inc.dias_incapacidad,
        )
        # DECISIÓN PROVISIONAL (nocturno): ante una falta injustificada se
        # descuenta el dia y NO la parte proporcional del septimo (Art. 69
        # LFT). Hay despachos que descuentan las dos cosas. Se toma la que
        # favorece al trabajador y es la mas simple de explicar en la demo.
        # Decision abierta para la contadora.
        dias_pagados = (
            dias_pagados_override
            if dias_pagados_override is not None
            else inc.dias_periodo - inc.faltas
        )
        if dias_pagados < 0:
            raise FiscalValidationError(
                f"{empleado.empleado_no}: {inc.faltas} faltas en un periodo de "
                f"{inc.dias_periodo} días naturales dan {dias_pagados} días pagados."
            )
        salario_minimo = es_trabajador_de_salario_minimo(
            sbc.valor, fecha_pago, empleado.zona
        )
        percepcion = Percepcion(
            CLAVE_PERCEPCION_SUELDO,
            "SUELDO",
            redondear(empleado.salario_diario * dias_pagados),
        )
        recibo = armar_recibo(
            percepciones=((percepcion, CLAVE_INTERNA_SUELDO),),
            sbc=sbc,
            dias=dias,
            fecha=fecha_pago,
            zona=empleado.zona,
            prima_riesgo=prima_riesgo,
            # DECISIÓN PROVISIONAL (nocturno, §D11): el ingreso mensual contra
            # el que se compara el tope del subsidio es `SBC x 30.4`. Es la
            # unica de las tres lecturas de D11 que el caso real no refuta, y
            # la unica que **no depende de la periodicidad**, asi que pasarla
            # de semanal a quincenal no agrega un supuesto nuevo.
            #
            # Se usa el SBC **acotado**; la evidencia de §D11 se construyo con
            # el timbrado. Coinciden en los 9 de la demo y divergen en un
            # trabajador al piso. Decision abierta.
            ingreso_gravado_mensual=redondear(sbc.valor * DIAS_MES_FISCAL),
            clave_periodicidad=clave_periodicidad,
            # Sin esto, `armar_recibo` toma el default False y le retiene ISR a
            # un trabajador de salario minimo (Art. 96 ultimo parrafo). Con los
            # SDI de la demo nadie cae en el supuesto, asi que el defecto
            # cruzaria la demo entera sin verse.
            es_trabajador_de_salario_minimo=salario_minimo,
        )
        resultados.append(
            ReciboPeriodo(
                empleado_no=empleado.empleado_no,
                nombre=empleado.nombre,
                sbc=sbc,
                dias=dias,
                dias_pagados=dias_pagados,
                es_salario_minimo=salario_minimo,
                recibo=recibo,
                cuotas=cuotas_empleado(
                    sbc, dias, fecha_pago, empleado.zona, prima_riesgo
                ),
            )
        )

    todas = tuple(r.cuotas for r in resultados)
    congelados = tuple(resultados)
    return ResultadoPeriodo(
        recibos=congelados,
        porcion_mensual=consolidado_mensual(todas),
        porcion_bimestral=consolidado_bimestral(todas),
        advertencias=_advertencias(congelados, dias_del_periodo),
    )
