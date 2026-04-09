"""Schemas para el endpoint de resumen de retenciones a terceros."""

from pydantic import BaseModel
from app.schemas.fiscal import PerfilContribuyente, CFDI


class RetencionesRequest(BaseModel):
    """Request para generar resumen de retenciones."""
    contribuyente: PerfilContribuyente
    facturas: list[CFDI]
    periodo_year: int
    periodo_month: int | None = None
    periodo_bimestre: int | None = None
    incluir_explicacion: bool = True


class TerceroRetencion(BaseModel):
    """Detalle de retenciones a un tercero."""
    rfc: str
    nombre: str
    total_pagado: float
    isr_retenido: float
    iva_retenido: float
    cantidad_facturas: int


class RetencionesResponse(BaseModel):
    """Respuesta del endpoint de retenciones."""
    exito: bool
    periodo: str
    terceros: list[TerceroRetencion]
    total_isr_retenido: float
    total_iva_retenido: float
    explicacion: str | None = None
