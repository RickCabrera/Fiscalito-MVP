"""Schemas para el endpoint multi-periodo."""

from pydantic import BaseModel
from app.schemas.fiscal import PerfilContribuyente, CFDI
from app.schemas.declaraciones import DesgloseFiscal


class MultiPeriodoRequest(BaseModel):
    """Request para calcular multiples periodos a la vez."""
    contribuyente: PerfilContribuyente
    facturas: list[CFDI]
    periodo_year: int
    periodos: list[int]
    incluir_explicacion: bool = True


class PeriodoResultado(BaseModel):
    """Resultado de un periodo individual."""
    periodo: str
    desglose: DesgloseFiscal


class AcumuladoMultiPeriodo(BaseModel):
    """Resumen acumulado de todos los periodos."""
    total_isr_pagado: float
    total_iva_pagado: float
    total_general_pagado: float
    promedio_mensual: float
    tendencia: str


class MultiPeriodoResponse(BaseModel):
    """Respuesta del endpoint multi-periodo."""
    exito: bool
    year: int
    resultados: list[PeriodoResultado]
    acumulado: AcumuladoMultiPeriodo
    explicacion: str | None = None
