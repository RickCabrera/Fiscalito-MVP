"""Motor de generacion de estado de cuenta fiscal."""

from __future__ import annotations
from app.schemas.fiscal import CFDI, PerfilContribuyente, TipoFactura
from app.fiscal_engine.calculadora import calcular_isr_resico, calcular_isr_general, clasificar_facturas
from app.constants import NOMBRES_MESES, TOPE_RESICO_ANUAL


def generar_estado_cuenta(
    contribuyente: PerfilContribuyente,
    facturas: list[CFDI],
    year: int,
) -> dict:
    """
    Genera estado de cuenta fiscal acumulado del ejercicio.

    Calcula totales, estima ISR anual, proyecta ingresos
    y genera advertencias relevantes.
    """
    # Usar clasificar_facturas para respetar flujo de efectivo (PUE/PPD)
    ingresos, egresos = clasificar_facturas(facturas, contribuyente.rfc)

    # Filtrar solo facturas del anio solicitado
    ingresos = [f for f in ingresos if f.fecha.year == year]
    egresos = [f for f in egresos if f.fecha.year == year]

    # Totales acumulados (solo facturas tipo I para ingresos)
    total_ingresos = sum(f.base_gravable for f in ingresos if f.es_ingreso)
    total_egresos = sum(f.base_gravable for f in egresos)
    isr_retenido = sum(f.isr_retenido for f in ingresos)
    iva_cobrado = sum(f.iva_trasladado for f in ingresos if f.es_ingreso)
    iva_pagado = sum(f.iva_trasladado for f in egresos)
    iva_retenido = sum(f.iva_retenido for f in ingresos)

    # Meses con actividad para proyeccion
    meses_con_facturas = set(f.fecha.month for f in facturas if f.fecha.year == year)
    n_meses = len(meses_con_facturas) if meses_con_facturas else 1

    # Proyeccion anual
    proyeccion_anual = (total_ingresos / n_meses) * 12

    # ISR anual estimado
    regimen = contribuyente.regimen
    if regimen == "626":
        # RESICO: tasa fija sobre ingresos brutos mensuales x12
        isr_mensual_estimado, _ = calcular_isr_resico(proyeccion_anual / 12)
        isr_anual_estimado = isr_mensual_estimado * 12
    else:
        # Tabla progresiva anual Art. 152
        base_anual = max(proyeccion_anual - (total_egresos / n_meses * 12), 0)
        isr_anual_estimado, _ = calcular_isr_general(base_anual, es_anual=True)

    isr_faltante = max(isr_anual_estimado - isr_retenido, 0)

    # Proporcion gastos/ingresos
    proporcion = round(total_egresos / total_ingresos, 4) if total_ingresos > 0 else 0.0

    # Mes con mayor ingreso y mayor gasto
    ingresos_por_mes: dict[int, float] = {}
    gastos_por_mes: dict[int, float] = {}
    for f in ingresos:
        if f.es_ingreso:
            ingresos_por_mes[f.fecha.month] = ingresos_por_mes.get(f.fecha.month, 0) + f.base_gravable
    for f in egresos:
        gastos_por_mes[f.fecha.month] = gastos_por_mes.get(f.fecha.month, 0) + f.base_gravable

    mes_mayor_ingreso = NOMBRES_MESES.get(
        max(ingresos_por_mes, key=ingresos_por_mes.get) if ingresos_por_mes else 0, "N/A"
    )
    mes_mayor_gasto = NOMBRES_MESES.get(
        max(gastos_por_mes, key=gastos_por_mes.get) if gastos_por_mes else 0, "N/A"
    )

    # Advertencias
    advertencias: list[str] = []
    if regimen == "626" and proyeccion_anual > TOPE_RESICO_ANUAL * 0.80:
        porcentaje = round(proyeccion_anual / TOPE_RESICO_ANUAL * 100, 1)
        advertencias.append(
            f"Tus ingresos proyectados representan el {porcentaje}% del tope RESICO "
            f"($3,500,000). Si lo excedes, el SAT te cambiara de regimen."
        )
    if regimen == "626" and proyeccion_anual > TOPE_RESICO_ANUAL:
        advertencias.append(
            "Tus ingresos proyectados EXCEDEN el tope de $3,500,000 para RESICO. "
            "Debes considerar cambiar a regimen de Actividad Empresarial (612)."
        )
    if proporcion < 0.10 and regimen not in ("626", "605"):
        advertencias.append(
            "Tu proporcion de gastos es menor al 10% de tus ingresos. "
            "Revisa si hay gastos deducibles que no estes facturando."
        )

    return {
        "exito": True,
        "year": year,
        "ingresos_acumulados": round(total_ingresos, 2),
        "egresos_acumulados": round(total_egresos, 2),
        "isr_retenido_acumulado": round(isr_retenido, 2),
        "isr_anual_estimado": round(isr_anual_estimado, 2),
        "isr_faltante": round(isr_faltante, 2),
        "iva_cobrado_acumulado": round(iva_cobrado, 2),
        "iva_pagado_acumulado": round(iva_pagado, 2),
        "iva_retenido_acumulado": round(iva_retenido, 2),
        "proyeccion_ingresos_anuales": round(proyeccion_anual, 2),
        "proporcion_gastos_ingresos": proporcion,
        "mes_mayor_ingreso": mes_mayor_ingreso,
        "mes_mayor_gasto": mes_mayor_gasto,
        "advertencias": advertencias,
    }
