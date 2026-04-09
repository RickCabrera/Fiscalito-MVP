"""
Endpoint del agente conversacional de pre-declaraciones.

POST /api/v1/agente/predeclaracion

El agente recibe un mensaje del usuario + contexto fiscal completo y usa
tool use para:
  1. Leer el perfil del contribuyente
  2. Consultar el historial de declaraciones
  3. Calcular una nueva pre-declaracion si se necesita

Soporta Anthropic (claude-haiku) y OpenAI (gpt-4o-mini) via LLM_PROVIDER.
"""

from __future__ import annotations
import json
import logging

from fastapi import APIRouter

from app.config import settings
from app.schemas.agente import AgentePreDeclaracionRequest, AgentePreDeclaracionResponse
from app.schemas.declaraciones import DesgloseFiscal, PreDeclaracionResponse
from app.services.agent_tools import (
    TOOLS_ANTHROPIC,
    TOOLS_OPENAI,
    RequestContext,
    ejecutar_tool,
)
from app.constants import NOMBRES_REGIMEN

router = APIRouter(tags=["Agente"])
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# System prompts por proveedor
# ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT_OPENAI = """Eres Fiscalito, un asistente fiscal mexicano experto y amigable.
Tu trabajo es ayudar al contribuyente a entender su situación fiscal y calcular
sus pre-declaraciones de ISR e IVA.

Tienes acceso a las siguientes herramientas:

1. leer_perfil_contribuyente
   Úsala primero, siempre. Te da el RFC, régimen fiscal, tipo de contribuyente
   y sus obligaciones clave (periodicidad, si tiene empleados, etc.).

2. obtener_predeclaraciones
   Consulta el historial de declaraciones ya calculadas del contribuyente.
   Puedes filtrar por año y mes. Úsala cuando el usuario pregunte por
   declaraciones anteriores o quiera saber si ya calculó un periodo.

3. crear_predeclaracion
   Calcula una nueva pre-declaración ISR/IVA con el motor fiscal determinístico.
   Úsala cuando el usuario quiera saber cuánto tiene que pagar o necesite
   un cálculo nuevo para un periodo específico.

Proceso recomendado:
1. Lee el perfil para conocer el régimen y tipo del contribuyente.
2. Si pregunta por algo ya declarado, consulta el historial.
3. Si necesita un cálculo nuevo, llama a crear_predeclaracion.
4. Explica el resultado: qué se calculó, por qué y cuánto paga.

Reglas de respuesta:
- Usa lenguaje claro y amigable, sin jerga innecesaria
- Siempre menciona que es una PRE-declaración (estimación, no oficial)
- Cuando cites montos usa formato $X,XXX.XX
- Máximo 3-4 párrafos en tu respuesta final
- No des asesoría legal ni garantices resultados ante el SAT
"""

SYSTEM_PROMPT_ANTHROPIC = """Eres Fiscalito, un asistente fiscal mexicano experto.
Ayuda al contribuyente con sus pre-declaraciones de ISR e IVA usando las herramientas disponibles.
Lee siempre el perfil primero, consulta el historial si aplica, y calcula cuando sea necesario.
Responde de forma clara y concisa. Menciona siempre que es una PRE-declaración estimada.
"""


@router.post(
    "/agente/predeclaracion",
    response_model=AgentePreDeclaracionResponse,
    summary="Agente conversacional de pre-declaraciones",
    description=(
        "Agente con tool use que lee el perfil, consulta historial y calcula "
        "pre-declaraciones según el mensaje del usuario."
    ),
)
async def agente_predeclaracion(req: AgentePreDeclaracionRequest) -> AgentePreDeclaracionResponse:
    ctx = RequestContext(
        contribuyente=req.contribuyente,
        facturas=req.facturas,
        historial=req.historial,
        periodo_year=req.periodo_year,
        periodo_month=req.periodo_month,
    )

    if settings.LLM_PROVIDER == "anthropic":
        return await _run_anthropic_agent(req.mensaje, ctx)
    else:
        return await _run_openai_agent(req.mensaje, ctx)


# ─────────────────────────────────────────────────────────────
# Agentic loop — Anthropic
# ─────────────────────────────────────────────────────────────

async def _run_anthropic_agent(
    mensaje: str,
    ctx: RequestContext,
) -> AgentePreDeclaracionResponse:
    from anthropic import AsyncAnthropic

    client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    messages = [{"role": "user", "content": mensaje}]
    herramientas_usadas: list[str] = []
    predeclaracion_result: dict | None = None

    for _ in range(10):  # max 10 iteraciones para prevenir loops infinitos
        response = await client.messages.create(
            model=settings.ANTHROPIC_MODEL,
            system=SYSTEM_PROMPT_ANTHROPIC,
            tools=TOOLS_ANTHROPIC,
            messages=messages,
            max_tokens=1500,
        )

        if response.stop_reason == "end_turn":
            texto = next(
                (b.text for b in response.content if hasattr(b, "text")),
                "No se pudo generar una respuesta.",
            )
            return _build_response(texto, predeclaracion_result, herramientas_usadas, ctx)

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue

                tool_name = block.name
                tool_input = block.input or {}
                herramientas_usadas.append(tool_name)

                resultado_str, desglose_dict = ejecutar_tool(tool_name, tool_input, ctx)
                if desglose_dict:
                    predeclaracion_result = desglose_dict

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": resultado_str,
                })

            messages.append({"role": "user", "content": tool_results})
        else:
            break

    # Fallback si se agotaron las iteraciones
    return AgentePreDeclaracionResponse(
        respuesta="No pude completar el análisis. Intenta de nuevo con una pregunta más específica.",
        herramientas_usadas=herramientas_usadas,
    )


# ─────────────────────────────────────────────────────────────
# Agentic loop — OpenAI
# ─────────────────────────────────────────────────────────────

async def _run_openai_agent(
    mensaje: str,
    ctx: RequestContext,
) -> AgentePreDeclaracionResponse:
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT_OPENAI},
        {"role": "user", "content": mensaje},
    ]
    herramientas_usadas: list[str] = []
    predeclaracion_result: dict | None = None

    for _ in range(10):
        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            tools=TOOLS_OPENAI,
            messages=messages,
            max_tokens=1500,
        )

        choice = response.choices[0]

        if choice.finish_reason == "stop":
            texto = choice.message.content or "No se pudo generar una respuesta."
            return _build_response(texto, predeclaracion_result, herramientas_usadas, ctx)

        if choice.finish_reason == "tool_calls" and choice.message.tool_calls:
            messages.append(choice.message)

            for tool_call in choice.message.tool_calls:
                tool_name = tool_call.function.name
                tool_input = json.loads(tool_call.function.arguments or "{}")
                herramientas_usadas.append(tool_name)

                resultado_str, desglose_dict = ejecutar_tool(tool_name, tool_input, ctx)
                if desglose_dict:
                    predeclaracion_result = desglose_dict

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": resultado_str,
                })
        else:
            break

    return AgentePreDeclaracionResponse(
        respuesta="No pude completar el análisis. Intenta de nuevo con una pregunta más específica.",
        herramientas_usadas=herramientas_usadas,
    )


# ─────────────────────────────────────────────────────────────
# Helper — construir response final
# ─────────────────────────────────────────────────────────────

def _build_response(
    texto: str,
    predeclaracion_dict: dict | None,
    herramientas_usadas: list[str],
    ctx: RequestContext,
) -> AgentePreDeclaracionResponse:
    predeclaracion_obj: PreDeclaracionResponse | None = None

    if predeclaracion_dict:
        periodo = predeclaracion_dict.pop("periodo", "")
        regimen = predeclaracion_dict.pop("regimen", NOMBRES_REGIMEN.get(ctx.contribuyente.regimen, ctx.contribuyente.regimen))
        tipo = "anual" if ctx.periodo_month is None else "mensual"

        try:
            desglose = DesgloseFiscal(**predeclaracion_dict)
            predeclaracion_obj = PreDeclaracionResponse(
                tipo_declaracion=tipo,
                periodo=periodo,
                regimen=regimen,
                desglose=desglose,
            )
        except Exception:
            logger.exception("Error construyendo PreDeclaracionResponse desde tool result")

    return AgentePreDeclaracionResponse(
        respuesta=texto,
        predeclaracion=predeclaracion_obj,
        herramientas_usadas=herramientas_usadas,
    )
