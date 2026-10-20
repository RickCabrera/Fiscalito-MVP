"""
LLM (P0-06). `FISCALITO_LLM` = falso | openai | anthropic.

**El LLM nunca calcula impuestos**: explica, clasifica texto y conversa. Los cálculos son del
motor determinístico.

Interfaz neutral: `completar(mensajes, herramientas=None) -> RespuestaLLM`.
- `mensajes`: `[{"role": "system"|"user"|"assistant", "content": "..."}]`, más los dos
  mensajes del loop de herramientas (P5-07), en forma NEUTRAL que cada real traduce a la de
  su proveedor:
  - `{"role": "assistant", "content": "...", "llamadas": [{"id", "nombre", "argumentos"}]}`
  - `{"role": "herramienta", "id": "<id de la llamada>", "nombre": "...", "content": "..."}`
- `herramientas`: `[{"nombre", "descripcion", "parametros": <JSON Schema>}]`.

Las reales reusan la configuración de `app/services/llm_service.py` (`OPENAI_API_KEY`,
`OPENAI_MODEL`, `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` en `app.config.settings`); ese módulo
sigue funcionando igual: este adaptador es la vía nueva para lo que construye el plan P.
Hablan REST con httpx y no con los SDK: el SDK de Anthropic instalado ya usa `httpx2` y no
acepta un `httpx.Client` inyectado, lo que haría imposible probarlo sin red.
"""

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

from app.config import settings
from app.integraciones import registro
from app.integraciones.comun import ServicioNoConfigurado, cliente_http, revisar

MAX_TOKENS = 1024


@dataclass(frozen=True)
class LlamadaHerramienta:
    id: str
    nombre: str
    argumentos: dict[str, Any]


@dataclass(frozen=True)
class RespuestaLLM:
    texto: str
    llamadas: list[LlamadaHerramienta] = field(default_factory=list)
    modelo: str = ""
    tokens_entrada: int = 0
    tokens_salida: int = 0


class LLM(Protocol):
    def completar(
        self, mensajes: Sequence[dict[str, Any]],
        herramientas: Sequence[dict[str, Any]] | None = None,
    ) -> RespuestaLLM: ...


@dataclass
class LLMFalso:
    """
    Determinístico y sin red. Si hay herramientas, pide la primera con `{}`; si no, contesta
    `"[falso] <último mensaje del usuario>"`. `respuestas` permite fijar una cola de
    respuestas para un test. Registra lo recibido en `llamadas`.
    """

    respuestas: list[RespuestaLLM] = field(default_factory=list)
    llamadas: list[dict[str, Any]] = field(default_factory=list)

    def completar(self, mensajes, herramientas=None):
        self.llamadas.append({"mensajes": list(mensajes), "herramientas": list(herramientas or [])})
        if self.respuestas:
            return self.respuestas.pop(0)
        if mensajes and mensajes[-1].get("role") == "herramienta":
            # P5-07: tras el resultado de una herramienta, contesta (si no, el loop no acaba).
            return RespuestaLLM(texto=f"[falso] {mensajes[-1].get('content', '')[:500]}",
                                modelo="falso")
        if herramientas:
            h = herramientas[0]
            return RespuestaLLM(texto="", llamadas=[
                LlamadaHerramienta(id="falso-1", nombre=h["nombre"], argumentos={})
            ], modelo="falso")
        ultimo = next((m["content"] for m in reversed(mensajes) if m.get("role") == "user"), "")
        return RespuestaLLM(texto=f"[falso] {ultimo}", modelo="falso")


def _a_openai(mensajes: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Mensajes neutrales → Chat Completions (`tool_calls` y `role: tool`)."""
    salida: list[dict[str, Any]] = []
    for m in mensajes:
        if m.get("role") == "herramienta":
            salida.append({"role": "tool", "tool_call_id": m["id"], "content": m["content"]})
        elif m.get("role") == "assistant" and m.get("llamadas"):
            salida.append({"role": "assistant", "content": m.get("content") or None,
                           "tool_calls": [{
                               "id": ll["id"], "type": "function",
                               "function": {"name": ll["nombre"],
                                            "arguments": json.dumps(ll["argumentos"])},
                           } for ll in m["llamadas"]]})
        else:
            salida.append({"role": m["role"], "content": m.get("content", "")})
    return salida


def _a_anthropic(mensajes: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Mensajes neutrales → Messages API: `tool_use` en el assistant y `tool_result` en un
    mensaje `user` (los resultados consecutivos van juntos en UN mensaje, como exige la API).
    """
    salida: list[dict[str, Any]] = []
    for m in mensajes:
        rol = m.get("role")
        if rol == "system":
            continue
        if rol == "herramienta":
            bloque = {"type": "tool_result", "tool_use_id": m["id"], "content": m["content"]}
            previo = salida[-1] if salida else None
            if (previo and previo["role"] == "user" and isinstance(previo["content"], list)
                    and all(b.get("type") == "tool_result" for b in previo["content"])):
                previo["content"].append(bloque)
            else:
                salida.append({"role": "user", "content": [bloque]})
        elif rol == "assistant" and m.get("llamadas"):
            bloques: list[dict[str, Any]] = []
            if m.get("content"):
                bloques.append({"type": "text", "text": m["content"]})
            bloques += [{"type": "tool_use", "id": ll["id"], "name": ll["nombre"],
                         "input": ll["argumentos"]} for ll in m["llamadas"]]
            salida.append({"role": "assistant", "content": bloques})
        else:
            salida.append({"role": rol, "content": m.get("content", "")})
    return salida


def _exigir(llave: str, variable: str) -> str:
    if not llave:
        raise ServicioNoConfigurado(f"Falta {variable} para usar el LLM.")
    return llave


class LLMOpenAI:
    """Chat Completions de OpenAI con tool calling (REST con httpx, sin depender del SDK)."""

    URL = "https://api.openai.com/v1/chat/completions"

    def __init__(self, api_key: str, modelo: str, http: httpx.Client | None = None) -> None:
        self.modelo = modelo
        self._key = api_key
        self._http = cliente_http(http, timeout=httpx.Timeout(60.0, connect=10.0))

    def completar(self, mensajes, herramientas=None):
        cuerpo: dict[str, Any] = {
            "model": self.modelo, "messages": _a_openai(mensajes),
            "max_tokens": MAX_TOKENS, "temperature": 0.3,
        }
        if herramientas:
            cuerpo["tools"] = [{"type": "function", "function": {
                "name": h["nombre"], "description": h.get("descripcion", ""),
                "parameters": h.get("parametros", {"type": "object", "properties": {}}),
            }} for h in herramientas]
        r = self._http.post(self.URL, json=cuerpo,
                            headers={"Authorization": f"Bearer {self._key}"})
        d = revisar(r, "OpenAI").json()
        msg = d["choices"][0]["message"]
        llamadas = [
            LlamadaHerramienta(id=t["id"], nombre=t["function"]["name"],
                               argumentos=json.loads(t["function"].get("arguments") or "{}"))
            for t in (msg.get("tool_calls") or [])
        ]
        uso = d.get("usage") or {}
        return RespuestaLLM(
            texto=msg.get("content") or "", llamadas=llamadas, modelo=d.get("model", ""),
            tokens_entrada=uso.get("prompt_tokens", 0),
            tokens_salida=uso.get("completion_tokens", 0),
        )


class LLMAnthropic:
    """Messages API de Anthropic con tool use (REST con httpx, sin depender del SDK)."""

    URL = "https://api.anthropic.com/v1/messages"
    VERSION_API = "2023-06-01"

    def __init__(self, api_key: str, modelo: str, http: httpx.Client | None = None) -> None:
        self.modelo = modelo
        self._key = api_key
        self._http = cliente_http(http, timeout=httpx.Timeout(60.0, connect=10.0))

    def completar(self, mensajes, herramientas=None):
        sistema = "\n\n".join(m["content"] for m in mensajes if m.get("role") == "system")
        cuerpo: dict[str, Any] = {
            "model": self.modelo, "max_tokens": MAX_TOKENS, "temperature": 0.3,
            "messages": _a_anthropic(mensajes),
        }
        if sistema:
            cuerpo["system"] = sistema
        if herramientas:
            cuerpo["tools"] = [{
                "name": h["nombre"], "description": h.get("descripcion", ""),
                "input_schema": h.get("parametros", {"type": "object", "properties": {}}),
            } for h in herramientas]
        r = self._http.post(self.URL, json=cuerpo, headers={
            "x-api-key": self._key, "anthropic-version": self.VERSION_API,
        })
        d = revisar(r, "Anthropic").json()
        bloques = d.get("content", [])
        uso = d.get("usage") or {}
        return RespuestaLLM(
            texto="".join(b.get("text", "") for b in bloques if b.get("type") == "text"),
            llamadas=[
                LlamadaHerramienta(id=b["id"], nombre=b["name"], argumentos=dict(b["input"]))
                for b in bloques if b.get("type") == "tool_use"
            ],
            modelo=d.get("model", ""),
            tokens_entrada=uso.get("input_tokens", 0), tokens_salida=uso.get("output_tokens", 0),
        )


DESCRIPCION = "Modelo de lenguaje (explicaciones, bot de WhatsApp). Nunca calcula impuestos."
registro.registrar("llm", "falso", LLMFalso, DESCRIPCION)
registro.registrar("llm", "openai", lambda: LLMOpenAI(
    _exigir(settings.OPENAI_API_KEY, "OPENAI_API_KEY"), settings.OPENAI_MODEL), DESCRIPCION)
registro.registrar("llm", "anthropic", lambda: LLMAnthropic(
    _exigir(settings.ANTHROPIC_API_KEY, "ANTHROPIC_API_KEY"), settings.ANTHROPIC_MODEL),
    DESCRIPCION)
