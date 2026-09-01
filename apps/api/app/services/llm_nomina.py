"""
Explicación en lenguaje natural de la nómina de un periodo (D-06).

Módulo aparte de `llm_service.py` a propósito: ese archivo ya está en 462
líneas y meterle una octava explicación profundiza una violación existente del
límite de 300. Reusa sus clientes (`_call_anthropic` / `_call_openai`) y su
patrón de fallback estático.

LO QUE SE HEREDA SIN PEDIRLO
----------------------------
Esos clientes inyectan el `SYSTEM_PROMPT` de `llm_service.py`, que está escrito
para pre-declaraciones ("Siempre menciona que es una PRE-declaración y que
deben verificar con el SAT"). O sea que la explicación de una nómina puede
salir etiquetada como pre-declaración. **No toca ningún número** —el user
prompt y el fallback son de aquí— pero es una rareza de redacción conocida, no
un descuido. Separar el system prompt por dominio es de F1-07.

LA REGLA DE ORO
---------------
**El LLM no calcula.** Recibe los números que el motor determinístico ya
produjo y sólo los redacta. Si esta función tuviera que sumar algo, estaría
mal escrita.
"""

from __future__ import annotations

import logging

from app.config import settings
from app.services.llm_service import _call_anthropic, _call_openai

logger = logging.getLogger(__name__)


def _fallback(resumen: dict) -> str:
    """Resumen estático cuando el LLM no está disponible. Mismos números."""
    partes = [
        f"Nómina del periodo {resumen['periodo']}, pagada el {resumen['fecha_pago']}, "
        f"para {resumen['empleados']} empleados.",
        f"Percepciones totales: ${resumen['total_percepciones']:,.2f}. "
        f"Neto a pagar: ${resumen['total_neto']:,.2f}.",
        f"ISR retenido: ${resumen['total_isr']:,.2f}. "
        f"Cuota obrera IMSS: ${resumen['cuota_obrera']:,.2f}.",
        f"Cuota patronal IMSS e Infonavit devengada en el periodo: "
        f"${resumen['cuota_patronal']:,.2f}.",
    ]
    partes.extend(resumen.get("advertencias", []))
    return " ".join(partes)


async def generar_explicacion_nomina_periodo(resumen: dict) -> str:
    """
    Redacta la nómina del periodo. Los números vienen dados.

    `resumen` trae totales ya calculados y el desglose por ramo. La advertencia
    de que las cuotas son la **porción devengada** y no el entero del Art. 39
    va en el prompt: es lo que evita que el texto prometa un pago mensual que
    no es.
    """
    ramos_mensual = ", ".join(
        f"{clave}: ${monto:,.2f}" for clave, monto in resumen["porcion_mensual"].items()
    )
    ramos_bimestral = ", ".join(
        f"{clave}: ${monto:,.2f}" for clave, monto in resumen["porcion_bimestral"].items()
    )
    avisos = "\n".join(f"- {a}" for a in resumen.get("advertencias", []))
    user_prompt = f"""\
Explica esta nomina ya calculada. NO recalcules ni sumes nada: usa exactamente \
los numeros que te doy.

Periodo: {resumen["periodo"]} (pagada el {resumen["fecha_pago"]})
Empleados: {resumen["empleados"]}
Percepciones totales: ${resumen["total_percepciones"]:,.2f}
Neto a pagar: ${resumen["total_neto"]:,.2f}
ISR retenido: ${resumen["total_isr"]:,.2f}
Cuota obrera IMSS: ${resumen["cuota_obrera"]:,.2f}
Cuota patronal IMSS e Infonavit: ${resumen["cuota_patronal"]:,.2f}

Ramos de entero mensual devengados en el periodo: {ramos_mensual}
Ramos de entero bimestral devengados en el periodo: {ramos_bimestral}

Advertencias que DEBES incluir tal cual:
{avisos}

Explica:
1. Cuanto se paga en total a los trabajadores y cuanto retiene el patron
2. Cuanto le cuesta al patron en cuotas, y que los importes por ramo son lo \
DEVENGADO en este periodo, no el entero mensual ni el bimestral del Art. 39 LSS
3. Que sigue: para enterar al IMSS hay que sumar los periodos del mes o del bimestre
Se directo, no uses frases conversacionales."""

    try:
        if settings.LLM_PROVIDER == "anthropic":
            return await _call_anthropic(user_prompt)
        return await _call_openai(user_prompt)
    except Exception as e:
        logger.exception("LLM call failed para generar_explicacion_nomina_periodo: %s", e)
        return _fallback(resumen)
