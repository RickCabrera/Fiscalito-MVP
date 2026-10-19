"""Esquemas de acceso (P0-02): tokens de dispositivo del checador."""

from pydantic import BaseModel, Field


class EmitirTokenRequest(BaseModel):
    cliente: str = Field(min_length=1, max_length=120, description="Clave del cliente")
    etiqueta: str = Field(default="", max_length=120, description="p. ej. 'Entrada principal'")
    dispositivo: str | None = Field(
        default=None, description="Clave de un dispositivo dado de alta (opcional)"
    )


class TokenDispositivoSchema(BaseModel):
    id: int
    cliente: str
    dispositivo_id: int | None = None
    etiqueta: str
    prefijo: str = Field(description="Primeros 12 caracteres, para reconocerlo en pantalla")
    creado_en: str | None = None
    ultimo_uso: str | None = None


class TokenEmitidoResponse(BaseModel):
    exito: bool = True
    token: str = Field(
        description="El secreto en claro. ÚNICA vez que se muestra: el backend guarda su hash."
    )
    registro: TokenDispositivoSchema


class TokensResponse(BaseModel):
    exito: bool = True
    tokens: list[TokenDispositivoSchema]


class TokenRevocadoResponse(BaseModel):
    exito: bool = True
    registro: TokenDispositivoSchema
