"""
Schemas para el endpoint del agente de pre-declaraciones.

El agente recibe el perfil + facturas + historial en un solo request y
usa tools para leer el perfil, consultar el historial y calcular declaraciones.
"""

from __future__ import annotations
from pydantic import BaseModel, Field
from app.schemas.fiscal import PerfilContribuyente, CFDI
from app.schemas.declaraciones import PreDeclaracionResponse


class DeclaracionHistorialItem(BaseModel):
    """Resumen de una declaracion existente (viene de Firestore via frontend)."""
    periodo: str = Field(description="Ej: 'Enero 2026'")
    tipo: str = Field(description="'mensual', 'bimestral' o 'anual'")
    fecha_calculo: str = Field(default="", description="Fecha en que se calculo")
    total_a_pagar: float = Field(default=0.0)
    isr_a_pagar: float = Field(default=0.0)
    iva_a_pagar: float = Field(default=0.0)
    regimen: str = Field(default="")


class AgentePreDeclaracionRequest(BaseModel):
    """
    Request para el agente conversacional de pre-declaraciones.
    Incluye todo el contexto necesario ya que el backend es stateless.
    """
    mensaje: str = Field(
        ...,
        description="Mensaje o pregunta del usuario (ej: '¿Cuánto pago en marzo?')"
    )
    contribuyente: PerfilContribuyente
    facturas: list[CFDI] = Field(
        default_factory=list,
        description="Facturas del periodo o del ejercicio completo"
    )
    historial: list[DeclaracionHistorialItem] = Field(
        default_factory=list,
        description="Declaraciones previas del usuario (viene de Firestore)"
    )
    periodo_year: int = Field(..., description="Año fiscal de referencia")
    periodo_month: int | None = Field(
        default=None,
        description="Mes de referencia (1-12). None si no aplica."
    )


class AgentePreDeclaracionResponse(BaseModel):
    """Respuesta del agente de pre-declaraciones."""
    respuesta: str = Field(description="Respuesta en lenguaje natural del agente")
    predeclaracion: PreDeclaracionResponse | None = Field(
        default=None,
        description="Resultado del calculo si se creo una pre-declaracion"
    )
    herramientas_usadas: list[str] = Field(
        default_factory=list,
        description="Nombres de las tools que uso el agente"
    )
