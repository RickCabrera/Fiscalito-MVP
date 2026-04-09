"""
Schemas de request/response para el endpoint de calendario fiscal.
"""

from __future__ import annotations
from pydantic import BaseModel, Field


class ObligacionFiscalSchema(BaseModel):
    """Una obligacion fiscal con fecha limite."""
    nombre: str
    descripcion: str
    fecha_limite: str
    periodicidad: str
    completada: bool = False


class CalendarioRequest(BaseModel):
    """Request para generar calendario fiscal personalizado."""
    contributor_type: str = Field(..., description="Tipo: asalariado, independiente, arrendamiento, plataformas, pyme")
    regimen: str = Field(..., description="Codigo de regimen fiscal (626, 612, 606, 625, 605)")
    rfc: str = Field(..., description="RFC del contribuyente")
    year: int = Field(default=2025, description="Anio fiscal")


class CalendarioResponse(BaseModel):
    """Respuesta con el calendario de obligaciones fiscales."""
    exito: bool = True
    contributor_type: str
    total_obligaciones: int
    obligaciones: list[ObligacionFiscalSchema]
