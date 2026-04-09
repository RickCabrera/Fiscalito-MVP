"""Schemas para el endpoint de estado de cuenta fiscal."""

from pydantic import BaseModel
from app.schemas.fiscal import PerfilContribuyente, CFDI


class EstadoCuentaRequest(BaseModel):
    """Request para generar estado de cuenta fiscal."""
    contribuyente: PerfilContribuyente
    facturas: list[CFDI]
    periodo_year: int
    incluir_explicacion: bool = True


class EstadoCuentaResponse(BaseModel):
    """Respuesta del endpoint de estado de cuenta."""
    exito: bool
    year: int
    ingresos_acumulados: float
    egresos_acumulados: float
    isr_retenido_acumulado: float
    isr_anual_estimado: float
    isr_faltante: float
    iva_cobrado_acumulado: float
    iva_pagado_acumulado: float
    iva_retenido_acumulado: float
    proyeccion_ingresos_anuales: float
    proporcion_gastos_ingresos: float
    mes_mayor_ingreso: str
    mes_mayor_gasto: str
    advertencias: list[str]
    explicacion: str | None = None
