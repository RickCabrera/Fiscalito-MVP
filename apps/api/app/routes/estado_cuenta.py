"""Endpoint de estado de cuenta fiscal."""

from fastapi import APIRouter, HTTPException
from app.schemas.estado_cuenta import EstadoCuentaRequest, EstadoCuentaResponse
from app.fiscal_engine.estado_cuenta import generar_estado_cuenta
from app.services.llm_service import generar_explicacion_estado_cuenta

router = APIRouter(tags=["PYME"])


@router.post(
    "/estado-cuenta",
    response_model=EstadoCuentaResponse,
    summary="Estado de cuenta fiscal acumulado",
    description="Genera estado de cuenta fiscal del ejercicio con totales acumulados, "
    "ISR estimado, proyeccion anual y advertencias.",
)
async def estado_cuenta(req: EstadoCuentaRequest):
    if not req.facturas:
        raise HTTPException(status_code=400, detail="Se requiere al menos una factura.")

    resultado = generar_estado_cuenta(
        contribuyente=req.contribuyente,
        facturas=req.facturas,
        year=req.periodo_year,
    )

    explicacion = None
    if req.incluir_explicacion:
        explicacion = await generar_explicacion_estado_cuenta(resultado)

    return EstadoCuentaResponse(**resultado, explicacion=explicacion)
