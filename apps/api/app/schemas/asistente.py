"""
Esquemas del asistente del despacho (P5-07): turno de chat y voz.

El historial tiene la forma de mensajes de Chat Completions que ya arma
`apps/store/src/agent/agentLoop.ts` (`tool_calls` en el assistant, `tool_call_id` en
`tool`). NO admite `role: "system"`: el prompt lo arma el servidor con los datos del cliente
que lee de la base, nunca con texto del navegador.
"""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MAX_MENSAJES = 40
MAX_CARACTERES = 20_000
MAX_TTS = 4096
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


class FuncionSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=64)
    arguments: str = Field(default="{}", max_length=4000)


class LlamadaSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=100)
    type: Literal["function"] = "function"
    function: FuncionSchema


class MensajeTurno(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant", "tool"]
    content: str | None = Field(default="", max_length=8000)
    tool_calls: list[LlamadaSchema] | None = Field(default=None, max_length=8)
    tool_call_id: str | None = Field(default=None, max_length=100)
    # Sólo en los resultados de herramientas de SERVIDOR: HMAC que pone el servidor al
    # devolverlos. Sin ella, el navegador podría inventar "lo que dijo la balanza".
    firma: str | None = Field(default=None, max_length=128)


class TurnoRequest(BaseModel):
    """`POST /asistente/turno`."""

    model_config = ConfigDict(extra="forbid")

    cliente: str | None = Field(default=None, max_length=120,
                                description="Clave del cliente activo (null: ninguno).")
    contador: str = Field(default="", max_length=120,
                          description="Nombre con el que el asistente saluda.")
    historial: list[MensajeTurno] = Field(min_length=1, max_length=MAX_MENSAJES)

    @field_validator("contador")
    @classmethod
    def _sin_control(cls, v: str) -> str:
        # Entra al prompt de sistema: sin saltos de línea ni caracteres de control.
        if _CONTROL.search(v):
            raise ValueError("El nombre no puede llevar saltos de línea ni caracteres de "
                             "control.")
        return v.strip()

    @model_validator(mode="after")
    def _tope_de_caracteres(self) -> TurnoRequest:
        total = sum(len(m.content or "") for m in self.historial)
        if total > MAX_CARACTERES:
            raise ValueError(f"El historial pasa de {MAX_CARACTERES} caracteres.")
        return self


class LlamadaNavegador(BaseModel):
    id: str
    name: str
    args: dict[str, Any]


class HerramientaEjecutada(BaseModel):
    id: str
    nombre: str
    argumentos: dict[str, Any]
    ok: bool
    datos: dict[str, Any] | None = None
    error: str | None = None


class TurnoResponse(BaseModel):
    exito: bool = True
    type: Literal["text", "tool_calls"]
    text: str = ""
    toolCalls: list[LlamadaNavegador] = Field(default_factory=list)  # camelCase: contrato TS
    mensajes: list[MensajeTurno] = Field(
        default_factory=list,
        description="Mensajes que el navegador agrega a su historial antes de los resultados "
                    "de sus propias herramientas (assistant con tool_calls + resultados "
                    "firmados de las de servidor).")
    herramientas_servidor: list[HerramientaEjecutada] = Field(
        default_factory=list,
        description="Lo que devolvieron la base y los motores: las cifras salen de aquí.")


class HablarRequest(BaseModel):
    """`POST /asistente/hablar`."""

    texto: str = Field(min_length=1, max_length=MAX_TTS)


class TranscripcionResponse(BaseModel):
    exito: bool = True
    texto: str
