"""
Servicio LLM — genera explicaciones en lenguaje natural de los calculos fiscales.
Configurable entre OpenAI y Anthropic via variable de entorno LLM_PROVIDER.
"""

from __future__ import annotations

import logging

from app.config import settings
from app.schemas.declaraciones import DesgloseFiscal

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """Eres un asesor fiscal mexicano experto que explica calculos de impuestos
en lenguaje simple y amigable. Tu trabajo es tomar los resultados numericos de una
declaracion fiscal y explicarle al contribuyente:

1. De donde salen los numeros (que facturas sumaron, que se dedujo)
2. Que tasa se aplico y por que (segun su regimen y nivel de ingresos)
3. Si hay algo que pueda optimizar (deducciones faltantes, cambio de regimen, etc.)

Tipos de contribuyente que manejas:
- asalariado: Solo declara anual, su patron retiene ISR mensualmente. Enfocate en deducciones personales.
- independiente: Freelancer o profesionista. RESICO (626) con tasas fijas o Act. Empresarial (612) con deducciones.
- arrendamiento: Renta de inmuebles. Puede usar deduccion ciega del 35% o gastos reales.
- plataformas: Uber, Rappi, etc. Si gana <$300k anuales, retenciones pueden ser pago definitivo.
- pyme: Empresa con empleados. Tiene obligaciones adicionales como DIOT y retenciones de nomina.

Reglas:
- Usa lenguaje claro, evita jerga innecesaria
- Cuando menciones montos, usa formato $X,XXX.XX
- Se conciso: 3-5 parrafos maximo
- NO des asesoria legal, solo explica los calculos
- Si el resultado tiene saldo a favor, explicalo con entusiasmo
- Siempre menciona que es una PRE-declaracion y que deben verificar con el SAT
"""


def _build_user_prompt(
    desglose: DesgloseFiscal,
    regimen: str,
    periodo: str,
    tipo_declaracion: str,
    contributor_type: str | None = None,
) -> str:
    tipo_info = f"\nTipo de contribuyente: {contributor_type}" if contributor_type else ""
    return f"""Explica esta pre-declaracion {tipo_declaracion} del periodo {periodo}
para un contribuyente en regimen {regimen}.{tipo_info}

INGRESOS:
- Total ingresos facturados: ${desglose.total_ingresos_facturados:,.2f}
- Ingresos gravados (netos): ${desglose.total_ingresos_gravados:,.2f}
- Facturas de ingreso: {desglose.cantidad_facturas_ingreso}

DEDUCCIONES:
- Total egresos: ${desglose.total_egresos:,.2f}
- Deducciones autorizadas: ${desglose.total_deducciones_autorizadas:,.2f}
- Facturas de egreso: {desglose.cantidad_facturas_egreso}

ISR:
- Base gravable ISR: ${desglose.base_isr:,.2f}
- Tasa ISR aplicada: {desglose.tasa_isr:.2%}
- ISR causado: ${desglose.isr_causado:,.2f}
- ISR retenido por terceros: ${desglose.isr_retenido:,.2f}
- ISR a pagar: ${desglose.isr_a_pagar:,.2f}

IVA:
- IVA cobrado (trasladado): ${desglose.iva_trasladado_cobrado:,.2f}
- IVA pagado (acreditable): ${desglose.iva_trasladado_pagado:,.2f}
- IVA retenido: ${desglose.iva_retenido:,.2f}
- IVA a pagar: ${desglose.iva_a_pagar:,.2f}

TOTAL A PAGAR: ${desglose.total_a_pagar:,.2f}

Explicale al contribuyente estos numeros de forma clara y amigable."""


async def generar_explicacion(
    desglose: DesgloseFiscal,
    regimen: str,
    periodo: str,
    tipo_declaracion: str,
    contributor_type: str | None = None,
) -> str:
    """Genera explicacion en lenguaje natural usando el LLM configurado."""

    user_prompt = _build_user_prompt(desglose, regimen, periodo, tipo_declaracion, contributor_type)

    try:
        if settings.LLM_PROVIDER == "anthropic":
            return await _call_anthropic(user_prompt)
        else:
            return await _call_openai(user_prompt)
    except Exception as e:
        # Si el LLM falla, devolvemos un resumen basico en vez de crashear
        logger.exception("LLM call failed para generar_explicacion: %s", e)
        return _fallback_explicacion(desglose, regimen, periodo, tipo_declaracion)


async def _call_openai(user_prompt: str) -> str:
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    response = await client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=800,
        temperature=0.3,
    )
    return response.choices[0].message.content or ""


async def _call_anthropic(user_prompt: str) -> str:
    from anthropic import AsyncAnthropic

    client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    response = await client.messages.create(
        model=settings.ANTHROPIC_MODEL,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
        max_tokens=800,
        temperature=0.3,
    )
    return response.content[0].text if response.content else ""


async def generar_explicacion_deducciones(
    resultado,
    saldo_a_favor: float,
    ingresos_anuales: float,
) -> str:
    """Genera explicacion de deducciones personales usando LLM."""
    deducciones_texto = "\n".join(
        f"- {d.concepto}: solicitado ${d.monto_solicitado:,.2f}, aceptado ${d.monto_aceptado:,.2f}"
        for d in resultado.desglose
        if d.monto_solicitado > 0
    )
    user_prompt = f"""Explica estas deducciones personales para la declaracion anual:

Ingresos anuales: ${ingresos_anuales:,.2f}

DEDUCCIONES:
{deducciones_texto}

Total deducible: ${resultado.total_deducible:,.2f}
Tope global aplicado: ${resultado.tope_global:,.2f} ({resultado.tope_tipo})
Excedente no aprovechado: ${resultado.excedente_no_aprovechado:,.2f}
Saldo a favor estimado de ISR: ${saldo_a_favor:,.2f}

Explicale al contribuyente que deducciones aprovecho, cuales le faltan, y cuanto podria recuperar."""

    try:
        if settings.LLM_PROVIDER == "anthropic":
            return await _call_anthropic(user_prompt)
        else:
            return await _call_openai(user_prompt)
    except Exception as e:
        logger.exception("LLM call failed para generar_explicacion_deducciones: %s", e)
        partes = [
            f"Tus deducciones personales suman ${resultado.total_antes_tope:,.2f} antes del tope global.",
            f"El tope global aplicado es ${resultado.tope_global:,.2f} ({resultado.tope_tipo}).",
            f"Total efectivamente deducible: ${resultado.total_deducible:,.2f}.",
            f"Saldo a favor estimado de ISR: ${saldo_a_favor:,.2f}.",
        ]
        if resultado.excedente_no_aprovechado > 0:
            partes.append(
                f"No pudiste aprovechar ${resultado.excedente_no_aprovechado:,.2f} por exceder el tope."
            )
        partes.append(
            "IMPORTANTE: Esta es una estimacion. Verifica con el portal del SAT."
        )
        return "\n\n".join(partes)


async def generar_explicacion_comparacion(
    ingresos_mensuales: float,
    gastos_mensuales: float,
    resultados: list,
    regimen_recomendado: str,
    recomendacion: str,
) -> str:
    """Genera explicacion de comparacion de todos los regimenes usando LLM."""
    tabla = "\n".join(
        f"- {r.nombre} ({r.regimen}): ISR anual ${r.isr_anual:,.2f}"
        + (" [NO DISPONIBLE]" if not r.disponible else "")
        + (f" — {r.notas[0]}" if r.notas else "")
        for r in resultados
    )

    user_prompt = f"""Analisis comparativo de regimenes fiscales:

Ingresos mensuales estimados: ${ingresos_mensuales:,.2f}
Gastos mensuales estimados: ${gastos_mensuales:,.2f}
Ingresos anuales: ${ingresos_mensuales * 12:,.2f}

ISR anual estimado por regimen (de menor a mayor):
{tabla}

Regimen recomendado: {regimen_recomendado}

Con base en estos numeros, explica:
1. Por que el regimen recomendado es el mas conveniente
2. Cuando cambiaria la recomendacion (ej. si los gastos aumentan)
3. Que factores mas alla del ISR deberian considerar (carga administrativa, IVA, DIOT)
Sé directo y practico. No repitas los numeros de la tabla — ya los ve el usuario."""

    try:
        if settings.LLM_PROVIDER == "anthropic":
            return await _call_anthropic(user_prompt)
        else:
            return await _call_openai(user_prompt)
    except Exception as e:
        logger.exception("LLM call failed para generar_explicacion_comparacion: %s", e)
        lines = [f"{r.nombre}: ${r.isr_anual:,.2f}/año" for r in resultados if r.disponible]
        return (
            f"Comparacion de regimenes:\n\n"
            + "\n".join(lines)
            + f"\n\n{recomendacion}\n\n"
            "IMPORTANTE: Esta es una estimacion. Consulta con un contador."
        )


async def generar_explicacion_diot(
    resultado_diot: dict,
) -> str:
    """Genera explicacion de la DIOT usando LLM."""
    proveedores_texto = "\n".join(
        f"- {p['rfc']}: {p['cantidad_facturas']} facturas, "
        f"operaciones ${p['total_operaciones']:,.2f}, IVA pagado ${p['iva_pagado']:,.2f}"
        for p in resultado_diot.get("proveedores", [])
    )
    user_prompt = f"""Genera una explicacion clara de esta DIOT (Declaracion Informativa de Operaciones con Terceros):

Periodo: {resultado_diot.get("periodo", "N/A")}
Total de proveedores: {resultado_diot.get("total_proveedores", 0)}
Total de operaciones: ${resultado_diot.get("total_operaciones", 0):,.2f}
Total de IVA pagado a proveedores: ${resultado_diot.get("total_iva", 0):,.2f}

Detalle por proveedor:
{proveedores_texto}

Explica:
1. Que es la DIOT y por que se presenta
2. Que proveedores tuvo el contribuyente este periodo y cuanto IVA les pago
3. Que debe hacer con esta informacion (presentarla ante el SAT antes de la fecha limite)
Se directo, no uses frases conversacionales."""

    try:
        if settings.LLM_PROVIDER == "anthropic":
            return await _call_anthropic(user_prompt)
        else:
            return await _call_openai(user_prompt)
    except Exception as e:
        logger.exception("LLM call failed para generar_explicacion_diot: %s", e)
        partes = [
            f"DIOT del periodo {resultado_diot.get('periodo', 'N/A')}.",
            f"Registraste operaciones con {resultado_diot.get('total_proveedores', 0)} proveedores "
            f"por un total de ${resultado_diot.get('total_operaciones', 0):,.2f}.",
            f"El IVA total pagado a proveedores fue de ${resultado_diot.get('total_iva', 0):,.2f}.",
            "La DIOT es una declaracion informativa obligatoria que reporta al SAT "
            "las operaciones con tus proveedores y el IVA que les pagaste.",
            "Debes presentarla antes del dia 17 del mes siguiente al periodo declarado.",
            "IMPORTANTE: Esta es una estimacion. Verifica con el portal del SAT.",
        ]
        return "\n\n".join(partes)


async def generar_explicacion_retenciones(
    resultado_ret: dict,
) -> str:
    """Genera explicacion del resumen de retenciones a terceros usando LLM."""
    terceros_texto = "\n".join(
        f"- {t['rfc']} ({t['nombre']}): ISR retenido ${t['isr_retenido']:,.2f}, "
        f"IVA retenido ${t['iva_retenido']:,.2f}"
        for t in resultado_ret.get("terceros", [])
    )
    user_prompt = f"""Genera una explicacion clara de este resumen de retenciones a terceros:

Periodo: {resultado_ret.get("periodo", "N/A")}
Total ISR retenido: ${resultado_ret.get("total_isr_retenido", 0):,.2f}
Total IVA retenido: ${resultado_ret.get("total_iva_retenido", 0):,.2f}

Detalle por tercero:
{terceros_texto}

Explica:
1. Que son las retenciones de ISR e IVA y por que se hacen
2. A quienes se les retuvo y los montos correspondientes
3. La obligacion de enterar (pagar) estas retenciones al SAT antes de la fecha limite
Se directo, no uses frases conversacionales."""

    try:
        if settings.LLM_PROVIDER == "anthropic":
            return await _call_anthropic(user_prompt)
        else:
            return await _call_openai(user_prompt)
    except Exception as e:
        logger.exception("LLM call failed para generar_explicacion_retenciones: %s", e)
        partes = [
            f"Resumen de retenciones del periodo {resultado_ret.get('periodo', 'N/A')}.",
            f"Total ISR retenido a terceros: ${resultado_ret.get('total_isr_retenido', 0):,.2f}.",
            f"Total IVA retenido a terceros: ${resultado_ret.get('total_iva_retenido', 0):,.2f}.",
            "Las retenciones son impuestos que descontaste a tus proveedores al pagarles. "
            "Tienes la obligacion de enterarlas (pagarlas) al SAT a mas tardar el dia 17 "
            "del mes siguiente al periodo en que las retuviste.",
            "IMPORTANTE: Esta es una estimacion. Verifica con el portal del SAT.",
        ]
        return "\n\n".join(partes)


async def generar_explicacion_multi_periodo(
    acumulado: dict,
    year: int,
    n_periodos: int,
) -> str:
    """Genera explicacion del resumen multi-periodo usando LLM."""
    user_prompt = f"""Analisis del resumen fiscal acumulado del ejercicio {year} ({n_periodos} periodos calculados):

- Total ISR pagado: ${acumulado.get("total_isr_pagado", 0):,.2f}
- Total IVA pagado: ${acumulado.get("total_iva_pagado", 0):,.2f}
- Total general pagado: ${acumulado.get("total_general_pagado", 0):,.2f}
- Promedio por periodo: ${acumulado.get("promedio_mensual", 0):,.2f}
- Tendencia de pago: {acumulado.get("tendencia", "estable")}

Explica:
1. Cuanto ha pagado el contribuyente en total de impuestos en estos periodos
2. Que significa la tendencia ({acumulado.get("tendencia", "estable")}) y que implica para los siguientes periodos
3. Si el promedio por periodo es alto o bajo en relacion al total
Se directo, no uses frases conversacionales."""

    try:
        if settings.LLM_PROVIDER == "anthropic":
            return await _call_anthropic(user_prompt)
        else:
            return await _call_openai(user_prompt)
    except Exception as e:
        logger.exception("LLM call failed para generar_explicacion_multi_periodo: %s", e)
        tendencia = acumulado.get("tendencia", "estable")
        tendencia_texto = {
            "creciente": "Tus pagos de impuestos van en aumento periodo con periodo.",
            "decreciente": "Tus pagos de impuestos han ido disminuyendo.",
            "estable": "Tus pagos de impuestos se han mantenido estables.",
        }.get(tendencia, "")
        partes = [
            f"Resumen fiscal del ejercicio {year} ({n_periodos} periodos).",
            f"Total de ISR pagado: ${acumulado.get('total_isr_pagado', 0):,.2f}.",
            f"Total de IVA pagado: ${acumulado.get('total_iva_pagado', 0):,.2f}.",
            f"Total general: ${acumulado.get('total_general_pagado', 0):,.2f}.",
            f"Promedio por periodo: ${acumulado.get('promedio_mensual', 0):,.2f}.",
            tendencia_texto,
            "IMPORTANTE: Esta es una estimacion. Verifica con el portal del SAT.",
        ]
        return "\n\n".join(partes)


async def generar_explicacion_estado_cuenta(
    resultado: dict,
) -> str:
    """Genera explicacion del estado de cuenta fiscal usando LLM."""
    iva_neto = (
        resultado.get("iva_cobrado_acumulado", 0)
        - resultado.get("iva_pagado_acumulado", 0)
        - resultado.get("iva_retenido_acumulado", 0)
    )
    advertencias_texto = "\n".join(
        f"- {a}" for a in resultado.get("advertencias", [])
    ) or "Ninguna"

    user_prompt = f"""Analisis del estado de cuenta fiscal del ejercicio {resultado.get("year", "")}:

Ingresos acumulados: ${resultado.get("ingresos_acumulados", 0):,.2f}
Egresos acumulados: ${resultado.get("egresos_acumulados", 0):,.2f}
Proporcion gastos/ingresos: {resultado.get("proporcion_gastos_ingresos", 0):.1%}

ISR:
- ISR anual estimado: ${resultado.get("isr_anual_estimado", 0):,.2f}
- ISR retenido acumulado: ${resultado.get("isr_retenido_acumulado", 0):,.2f}
- ISR faltante por pagar: ${resultado.get("isr_faltante", 0):,.2f}

IVA neto estimado: ${iva_neto:,.2f}

Proyeccion de ingresos anuales: ${resultado.get("proyeccion_ingresos_anuales", 0):,.2f}
Mes con mayor ingreso: {resultado.get("mes_mayor_ingreso", "N/A")}
Mes con mayor gasto: {resultado.get("mes_mayor_gasto", "N/A")}

Advertencias del sistema:
{advertencias_texto}

Explica la salud fiscal del contribuyente: si va bien o debe preocuparse.
Menciona cuanto ISR le falta por cubrir y que significa la proyeccion anual.
Se directo, no uses frases conversacionales."""

    try:
        if settings.LLM_PROVIDER == "anthropic":
            return await _call_anthropic(user_prompt)
        else:
            return await _call_openai(user_prompt)
    except Exception as e:
        logger.exception("LLM call failed para generar_explicacion_estado_cuenta: %s", e)
        partes = [
            f"Estado de cuenta fiscal del ejercicio {resultado.get('year', '')}.",
            f"Ingresos acumulados: ${resultado.get('ingresos_acumulados', 0):,.2f}. "
            f"Egresos acumulados: ${resultado.get('egresos_acumulados', 0):,.2f}.",
            f"ISR anual estimado: ${resultado.get('isr_anual_estimado', 0):,.2f}. "
            f"ISR retenido hasta ahora: ${resultado.get('isr_retenido_acumulado', 0):,.2f}. "
            f"ISR faltante: ${resultado.get('isr_faltante', 0):,.2f}.",
            f"Proyeccion de ingresos anuales: ${resultado.get('proyeccion_ingresos_anuales', 0):,.2f}.",
        ]
        if resultado.get("advertencias"):
            partes.append("Advertencias: " + "; ".join(resultado["advertencias"]))
        partes.append(
            "IMPORTANTE: Esta es una estimacion. Verifica con el portal del SAT."
        )
        return "\n\n".join(partes)


def _fallback_explicacion(
    desglose: DesgloseFiscal,
    regimen: str,
    periodo: str,
    tipo_declaracion: str,
) -> str:
    """Explicacion basica cuando el LLM no esta disponible."""
    partes = [
        f"Pre-declaracion {tipo_declaracion} para el periodo {periodo} (regimen {regimen}).",
        f"Se registraron {desglose.cantidad_facturas_ingreso} facturas de ingreso "
        f"por un total de ${desglose.total_ingresos_gravados:,.2f}.",
    ]
    if desglose.cantidad_facturas_egreso > 0:
        partes.append(
            f"Se aplicaron {desglose.cantidad_facturas_egreso} facturas de egreso "
            f"como deducciones por ${desglose.total_deducciones_autorizadas:,.2f}."
        )
    partes.append(
        f"El ISR causado es ${desglose.isr_causado:,.2f} (tasa {desglose.tasa_isr:.2%}), "
        f"menos retenciones de ${desglose.isr_retenido:,.2f}, "
        f"resulta en ISR a pagar de ${desglose.isr_a_pagar:,.2f}."
    )
    partes.append(f"IVA a pagar: ${desglose.iva_a_pagar:,.2f}.")
    partes.append(f"Total estimado a pagar: ${desglose.total_a_pagar:,.2f}.")
    partes.append(
        "IMPORTANTE: Esta es una pre-declaracion estimada. "
        "Verifica los montos en el portal del SAT antes de presentar."
    )
    return "\n\n".join(partes)
