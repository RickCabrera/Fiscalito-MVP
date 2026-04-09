"""
Endpoint de comparacion de regimenes fiscales.

POST /api/v1/comparar-regimenes → Compara los 5 regimenes de PF entre si
"""

from fastapi import APIRouter, HTTPException
from app.schemas.comparador import CompararRegimenRequest, CompararRegimenResponse
from app.schemas.declaraciones import ErrorResponse
from app.fiscal_engine.comparador import calcular_todos_regimenes
from app.services.llm_service import generar_explicacion_comparacion

router = APIRouter(tags=["Comparador"])


@router.post(
    "/comparar-regimenes",
    response_model=CompararRegimenResponse,
    responses={400: {"model": ErrorResponse}},
    summary="Comparar todos los regimenes fiscales de personas fisicas",
    description="Simula ISR anual en los 5 regimenes (626, 612, 606, 625, 605) y los ordena de menor a mayor costo.",
)
async def comparar(req: CompararRegimenRequest):
    if req.ingresos_mensuales_estimados <= 0:
        raise HTTPException(
            status_code=400,
            detail="Los ingresos mensuales estimados deben ser mayores a cero.",
        )

    resultados, regimen_recomendado, ahorro_maximo, recomendacion = calcular_todos_regimenes(
        ingresos_mensuales=req.ingresos_mensuales_estimados,
        gastos_mensuales=req.gastos_mensuales_estimados,
        predial_mensual=req.predial_mensual,
    )

    nombre_recomendado = next(
        (r.nombre for r in resultados if r.regimen == regimen_recomendado), ""
    )

    explicacion = None
    if req.incluir_explicacion:
        explicacion = await generar_explicacion_comparacion(
            ingresos_mensuales=req.ingresos_mensuales_estimados,
            gastos_mensuales=req.gastos_mensuales_estimados,
            resultados=resultados,
            regimen_recomendado=nombre_recomendado,
            recomendacion=recomendacion,
        )

    return CompararRegimenResponse(
        resultados=resultados,
        regimen_recomendado=regimen_recomendado,
        nombre_recomendado=nombre_recomendado,
        ahorro_maximo=ahorro_maximo,
        recomendacion=recomendacion,
        explicacion=explicacion,
    )
