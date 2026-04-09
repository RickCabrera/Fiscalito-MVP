"""Motor de calculo multi-periodo."""

from __future__ import annotations
from app.schemas.fiscal import CFDI, PerfilContribuyente
from app.schemas.multi_periodo import PeriodoResultado, AcumuladoMultiPeriodo
from app.fiscal_engine.calculadora import calcular_declaracion
from app.constants import NOMBRES_MESES, REGIMENES_ACUMULATIVOS


def _determinar_tendencia(pagos: list[float]) -> str:
    """Determina tendencia comparando los ultimos 3 periodos."""
    if len(pagos) < 3:
        return "estable"
    ultimos = pagos[-3:]
    if ultimos[0] < ultimos[1] < ultimos[2]:
        return "creciente"
    if ultimos[0] > ultimos[1] > ultimos[2]:
        return "decreciente"
    return "estable"


def calcular_multi_periodo(
    contribuyente: PerfilContribuyente,
    facturas: list[CFDI],
    year: int,
    periodos: list[int],
) -> tuple[list[PeriodoResultado], AcumuladoMultiPeriodo]:
    """
    Calcula declaraciones para multiples periodos y genera resumen acumulado.

    Para regimenes 612 (Act. Empresarial) y 606 (Arrendamiento), los pagos
    provisionales son ACUMULATIVOS (Art. 106/116 LISR): cada mes se calcula
    sobre la base acumulada desde enero hasta el mes en cuestion, usando
    tabla x N meses, y se restan los ISR causados en meses anteriores.

    Para otros regimenes (626 RESICO, 625 Plataformas, 605 Sueldos), cada
    periodo se calcula de forma aislada con solo las facturas del mes.

    Los periodos se interpretan como meses (1-12).
    """
    es_acumulativo = contribuyente.regimen in REGIMENES_ACUMULATIVOS

    # Procesar en orden cronologico para que el acumulado funcione bien.
    # Se devuelven en el mismo orden que el usuario los pidio.
    periodos_ordenados = sorted(set(periodos))

    resultados_por_mes: dict[int, PeriodoResultado] = {}

    # Acumuladores Art. 106 (solo para 612/606). Se construyen mes a mes
    # con los totales mes-only que devuelve calcular_declaracion.
    ingresos_acum = 0.0
    deducciones_acum = 0.0
    isr_acumulado_previo = 0.0  # Suma del ISR causado de meses anteriores

    for periodo in periodos_ordenados:
        nombre_periodo = f"{NOMBRES_MESES.get(periodo, str(periodo))} {year}"

        # Para todos los regimenes pasamos solo las facturas del mes en cuestion.
        # Para 612/606 los totales acumulados se pasan explicitamente como
        # parametros (Art. 106), evitando duplicar facturas y manteniendo los
        # campos total_ingresos_gravados / total_deducciones_autorizadas con
        # semantica mes-only.
        facturas_mes = [
            f for f in facturas
            if f.fecha.year == year and f.fecha.month == periodo
        ]

        if es_acumulativo and periodo > 1:
            desglose = calcular_declaracion(
                contribuyente=contribuyente,
                facturas=facturas_mes,
                es_anual=False,
                periodo_month=periodo,
                pagos_provisionales_anteriores=isr_acumulado_previo,
                ingresos_acumulados_anteriores=ingresos_acum,
                deducciones_acumuladas_anteriores=deducciones_acum,
            )
        else:
            desglose = calcular_declaracion(
                contribuyente=contribuyente,
                facturas=facturas_mes,
                es_anual=False,
                periodo_month=periodo,
            )

        if es_acumulativo:
            # Acumular ingresos y deducciones del mes (mes-only) para
            # el siguiente periodo.
            ingresos_acum += desglose.total_ingresos_gravados
            deducciones_acum += desglose.total_deducciones_autorizadas
            # desglose.isr_causado ya viene neto (despues de restar
            # isr_acumulado_previo). Para el siguiente mes necesitamos el
            # ISR total causado hasta el actual, asi que sumamos lo nuevo.
            isr_acumulado_previo += desglose.isr_causado

        resultados_por_mes[periodo] = PeriodoResultado(
            periodo=nombre_periodo,
            desglose=desglose,
        )

    # Devolver en el orden solicitado por el usuario, no el cronologico.
    resultados = [
        resultados_por_mes[p] for p in periodos if p in resultados_por_mes
    ]
    pagos_por_periodo = [r.desglose.total_a_pagar for r in resultados]

    # El total acumulado usa isr_a_pagar (despues de retenciones), que
    # representa lo efectivamente pagado al SAT en cada periodo.
    total_isr = sum(r.desglose.isr_a_pagar for r in resultados)
    total_iva = sum(max(r.desglose.iva_a_pagar, 0) for r in resultados)
    total_general = total_isr + total_iva
    n_periodos = len(periodos) if periodos else 1

    acumulado = AcumuladoMultiPeriodo(
        total_isr_pagado=round(total_isr, 2),
        total_iva_pagado=round(total_iva, 2),
        total_general_pagado=round(total_general, 2),
        promedio_mensual=round(total_general / n_periodos, 2),
        tendencia=_determinar_tendencia(pagos_por_periodo),
    )

    return resultados, acumulado
