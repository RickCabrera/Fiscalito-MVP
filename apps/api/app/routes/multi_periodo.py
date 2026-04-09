"""Endpoint multi-periodo — calcula multiples periodos a la vez."""

from fastapi import APIRouter, HTTPException
from app.schemas.multi_periodo import MultiPeriodoRequest, MultiPeriodoResponse
from app.fiscal_engine.multi_periodo import calcular_multi_periodo
from app.services.llm_service import generar_explicacion_multi_periodo

router = APIRouter(tags=["PYME"])


@router.post(
    "/multi-periodo",
    response_model=MultiPeriodoResponse,
    summary="Calcular multiples periodos",
    description="Calcula declaraciones para multiples meses o bimestres "
    "y genera resumen acumulado con tendencia.",
)
async def multi_periodo(req: MultiPeriodoRequest):
    if not req.facturas:
        raise HTTPException(status_code=400, detail="Se requiere al menos una factura.")
    if not req.periodos:
        raise HTTPException(status_code=400, detail="Se requiere al menos un periodo.")

    resultados, acumulado = calcular_multi_periodo(
        contribuyente=req.contribuyente,
        facturas=req.facturas,
        year=req.periodo_year,
        periodos=req.periodos,
    )

    explicacion = None
    if req.incluir_explicacion:
        acumulado_dict = {
            "total_isr_pagado": acumulado.total_isr_pagado,
            "total_iva_pagado": acumulado.total_iva_pagado,
            "total_general_pagado": acumulado.total_general_pagado,
            "promedio_mensual": acumulado.promedio_mensual,
            "tendencia": acumulado.tendencia,
        }
        explicacion = await generar_explicacion_multi_periodo(
            acumulado=acumulado_dict,
            year=req.periodo_year,
            n_periodos=len(req.periodos),
        )

    return MultiPeriodoResponse(
        exito=True,
        year=req.periodo_year,
        resultados=resultados,
        acumulado=acumulado,
        explicacion=explicacion,
    )
