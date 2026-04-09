"""Schemas para el endpoint DIOT (Declaracion Informativa de Operaciones con Terceros)."""

from pydantic import BaseModel
from app.schemas.fiscal import PerfilContribuyente, CFDI


class DIOTRequest(BaseModel):
    """Request para generar DIOT."""
    contribuyente: PerfilContribuyente
    facturas: list[CFDI]
    periodo_year: int
    periodo_month: int
    incluir_explicacion: bool = True


class ProveedorDIOT(BaseModel):
    """Detalle de un proveedor en el DIOT."""
    rfc: str
    nombre: str
    total_operaciones: float
    iva_pagado: float
    cantidad_facturas: int


class DIOTResponse(BaseModel):
    """Respuesta del endpoint DIOT."""
    exito: bool
    periodo: str
    proveedores: list[ProveedorDIOT]
    total_proveedores: int
    total_operaciones: float
    total_iva: float
    explicacion: str | None = None
