"""
Schemas de request/response para el endpoint de comparacion de regimenes.
"""

from __future__ import annotations
from pydantic import BaseModel, Field


class ResultadoRegimen(BaseModel):
    """Resultado ISR estimado para un regimen fiscal especifico."""
    regimen: str = Field(description="Codigo SAT del regimen (626, 612, 606, 625, 605)")
    nombre: str = Field(description="Nombre descriptivo del regimen")
    isr_anual: float = Field(description="ISR anual estimado")
    isr_mensual: float = Field(description="ISR mensual promedio estimado")
    disponible: bool = Field(description="Si el regimen es aplicable con los ingresos dados")
    notas: list[str] = Field(default_factory=list, description="Notas sobre el calculo o restricciones")


class CompararRegimenRequest(BaseModel):
    """Request para comparar todos los regimenes fiscales entre si."""
    ingresos_mensuales_estimados: float = Field(..., ge=0, description="Ingresos mensuales estimados")
    gastos_mensuales_estimados: float = Field(..., ge=0, description="Gastos mensuales deducibles estimados")
    predial_mensual: float = Field(default=0.0, ge=0, description="Impuesto predial mensual (relevante para 606)")
    tipo_actividad: str = Field(default="", description="Descripcion de la actividad economica")
    incluir_explicacion: bool = Field(default=True, description="Incluir explicacion LLM")


class CompararRegimenResponse(BaseModel):
    """Respuesta con ISR estimado para cada regimen fiscal, ordenado de menor a mayor."""
    exito: bool = True
    resultados: list[ResultadoRegimen] = Field(description="Lista de regimenes ordenados por ISR anual (menor = mas conveniente)")
    regimen_recomendado: str = Field(description="Codigo del regimen con menor ISR disponible")
    nombre_recomendado: str = Field(description="Nombre del regimen recomendado")
    ahorro_maximo: float = Field(description="Diferencia entre el mas caro y el mas barato (disponibles)")
    recomendacion: str = Field(description="Texto de recomendacion")
    explicacion: str | None = None
