"""
Schemas de request/response para el endpoint de deducciones personales.
"""

from __future__ import annotations
from pydantic import BaseModel, Field


class DeduccionDetalle(BaseModel):
    """Detalle de una deduccion individual."""
    concepto: str
    monto_solicitado: float
    tope_aplicable: float | None = None
    monto_aceptado: float


class DeduccionesPersonalesRequest(BaseModel):
    """Request para calcular deducciones personales (declaracion anual)."""
    ingresos_anuales: float = Field(..., ge=0, description="Ingresos totales del ejercicio fiscal")
    gastos_medicos: float = Field(default=0.0, ge=0, description="Gastos medicos, dentales y hospitalarios")
    colegiaturas: float = Field(default=0.0, ge=0, description="Colegiaturas pagadas")
    nivel_educativo: str = Field(
        default="",
        description="Nivel educativo: preescolar, primaria, secundaria, profesional_tecnico, bachillerato"
    )
    intereses_hipotecarios: float = Field(default=0.0, ge=0, description="Intereses reales de credito hipotecario")
    donativos: float = Field(default=0.0, ge=0, description="Donativos a instituciones autorizadas")
    aportaciones_voluntarias_retiro: float = Field(default=0.0, ge=0, description="Aportaciones voluntarias al retiro")
    seguros_gastos_medicos: float = Field(default=0.0, ge=0, description="Primas de seguros de gastos medicos")
    transporte_escolar: float = Field(default=0.0, ge=0, description="Transporte escolar obligatorio")
    funeral: float = Field(default=0.0, ge=0, description="Gastos funerarios")
    incluir_explicacion: bool = Field(default=True, description="Incluir explicacion LLM")


class DeduccionesPersonalesResponse(BaseModel):
    """Respuesta del calculo de deducciones personales."""
    exito: bool = True
    desglose: list[DeduccionDetalle]
    total_solicitado: float = Field(description="Suma total de deducciones solicitadas")
    total_antes_tope: float = Field(description="Total despues de topes individuales, antes de tope global")
    tope_global: float = Field(description="Tope global aplicado (5 UMAs o 15% ingresos)")
    tope_tipo: str = Field(description="'5_umas' o '15_porciento'")
    total_deducible: float = Field(description="Total efectivamente deducible")
    excedente_no_aprovechado: float = Field(description="Monto que excede el tope y no se puede deducir")
    saldo_a_favor_estimado: float = Field(description="Estimado de saldo a favor por deducciones")
    explicacion: str | None = None
