"""Endpoint de resumen de retenciones a terceros."""

from fastapi import APIRouter, HTTPException
from app.schemas.retenciones import RetencionesRequest, RetencionesResponse
from app.fiscal_engine.retenciones import generar_resumen_retenciones
from app.services.llm_service import generar_explicacion_retenciones
from app.constants import NOMBRES_MESES, NOMBRES_BIMESTRES

router = APIRouter(tags=["PYME"])


@router.post(
    "/retenciones-terceros",
    response_model=RetencionesResponse,
    summary="Resumen de retenciones a terceros",
    description="Genera resumen de retenciones de ISR e IVA agrupadas por tercero.",
)
async def retenciones_terceros(req: RetencionesRequest):
    if not req.facturas:
        raise HTTPException(status_code=400, detail="Se requiere al menos una factura.")

    if req.periodo_bimestre is not None:
        bim = req.periodo_bimestre
        if bim < 1 or bim > 6:
            raise HTTPException(status_code=400, detail="Bimestre debe ser entre 1 y 6.")
        periodo_str = f"{NOMBRES_BIMESTRES[bim]} {req.periodo_year}"
    elif req.periodo_month is not None:
        if req.periodo_month < 1 or req.periodo_month > 12:
            raise HTTPException(status_code=400, detail="Mes debe ser entre 1 y 12.")
        periodo_str = f"{NOMBRES_MESES[req.periodo_month]} {req.periodo_year}"
    else:
        periodo_str = f"Ejercicio {req.periodo_year}"

    terceros = generar_resumen_retenciones(req.contribuyente.rfc, req.facturas)

    total_isr = round(sum(t.isr_retenido for t in terceros), 2)
    total_iva = round(sum(t.iva_retenido for t in terceros), 2)

    explicacion = None
    if req.incluir_explicacion:
        resultado_ret = {
            "periodo": periodo_str,
            "total_isr_retenido": total_isr,
            "total_iva_retenido": total_iva,
            "terceros": [
                {
                    "rfc": t.rfc,
                    "nombre": t.nombre,
                    "isr_retenido": t.isr_retenido,
                    "iva_retenido": t.iva_retenido,
                }
                for t in terceros
            ],
        }
        explicacion = await generar_explicacion_retenciones(resultado_ret)

    return RetencionesResponse(
        exito=True,
        periodo=periodo_str,
        terceros=terceros,
        total_isr_retenido=total_isr,
        total_iva_retenido=total_iva,
        explicacion=explicacion,
    )
