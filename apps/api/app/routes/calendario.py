"""
Endpoint de calendario fiscal personalizado.

POST /api/v1/calendario → Genera calendario de obligaciones fiscales
"""

from fastapi import APIRouter, HTTPException
from app.schemas.calendario import (
    CalendarioRequest,
    CalendarioResponse,
    ObligacionFiscalSchema,
)
from app.schemas.declaraciones import ErrorResponse
from app.fiscal_engine.calendario import generar_calendario

router = APIRouter(tags=["Calendario"])

CONTRIBUTOR_TYPES_VALIDOS = {"asalariado", "independiente", "arrendamiento", "plataformas", "pyme"}


@router.post(
    "/calendario",
    response_model=CalendarioResponse,
    responses={400: {"model": ErrorResponse}},
    summary="Generar calendario fiscal personalizado",
    description="Genera lista de obligaciones fiscales con fechas limite "
    "segun el tipo de contribuyente, regimen y RFC.",
)
async def calendario_fiscal(req: CalendarioRequest):
    if req.contributor_type not in CONTRIBUTOR_TYPES_VALIDOS:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo de contribuyente invalido. Opciones: {', '.join(sorted(CONTRIBUTOR_TYPES_VALIDOS))}",
        )

    obligaciones = generar_calendario(
        contributor_type=req.contributor_type,
        regimen=req.regimen,
        rfc=req.rfc,
        year=req.year,
    )

    return CalendarioResponse(
        contributor_type=req.contributor_type,
        total_obligaciones=len(obligaciones),
        obligaciones=[
            ObligacionFiscalSchema(
                nombre=o.nombre,
                descripcion=o.descripcion,
                fecha_limite=o.fecha_limite,
                periodicidad=o.periodicidad,
                completada=o.completada,
            )
            for o in obligaciones
        ],
    )
