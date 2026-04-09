"""Endpoint DIOT — Declaracion Informativa de Operaciones con Terceros."""

from fastapi import APIRouter, HTTPException
from app.schemas.diot import DIOTRequest, DIOTResponse
from app.fiscal_engine.diot import generar_diot
from app.services.llm_service import generar_explicacion_diot
from app.constants import NOMBRES_MESES

router = APIRouter(tags=["PYME"])


@router.post(
    "/diot",
    response_model=DIOTResponse,
    summary="Generar DIOT automatico",
    description="Genera la Declaracion Informativa de Operaciones con Terceros "
    "agrupando egresos por proveedor.",
)
async def diot(req: DIOTRequest):
    if not req.facturas:
        raise HTTPException(status_code=400, detail="Se requiere al menos una factura.")

    if req.periodo_month < 1 or req.periodo_month > 12:
        raise HTTPException(status_code=400, detail="Mes debe ser entre 1 y 12.")

    proveedores = generar_diot(req.contribuyente.rfc, req.facturas)
    periodo_str = f"{NOMBRES_MESES[req.periodo_month]} {req.periodo_year}"

    total_operaciones = sum(p.total_operaciones for p in proveedores)
    total_iva = sum(p.iva_pagado for p in proveedores)

    explicacion = None
    if req.incluir_explicacion:
        resultado_diot = {
            "periodo": periodo_str,
            "total_proveedores": len(proveedores),
            "total_operaciones": round(total_operaciones, 2),
            "total_iva": round(total_iva, 2),
            "proveedores": [
                {
                    "rfc": p.rfc,
                    "nombre": p.nombre,
                    "total_operaciones": p.total_operaciones,
                    "iva_pagado": p.iva_pagado,
                    "cantidad_facturas": p.cantidad_facturas,
                }
                for p in proveedores
            ],
        }
        explicacion = await generar_explicacion_diot(resultado_diot)

    return DIOTResponse(
        exito=True,
        periodo=periodo_str,
        proveedores=proveedores,
        total_proveedores=len(proveedores),
        total_operaciones=round(total_operaciones, 2),
        total_iva=round(total_iva, 2),
        explicacion=explicacion,
    )
