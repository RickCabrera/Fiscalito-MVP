"""
DIOT vigente por cliente (P3-05): cortes por tasa desde la bóveda y archivo de carga masiva
con el layout 2025 del SAT. El endpoint viejo (`POST /diot`, `/calculos/diot`) queda igual.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Path
from fastapi.responses import Response

from app.diot import servicio
from app.exceptions import FiscalAgentError
from app.schemas.diot_layout import ConfigProveedorDiotSchema
from app.tenancy import Contexto, cliente_o_404, contexto_actual

router = APIRouter(prefix="/clientes/{clave}/diot", tags=["diot"])

ANIO = Path(..., ge=2025, le=2100, description="El layout de 54 campos aplica desde 2025.")
MES = Path(..., ge=1, le=12)


@router.get("/proveedores")
def proveedores(clave: str, ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    """Clasificación capturada por proveedor."""
    cliente = cliente_o_404(ctx, clave)
    return {"exito": True, "proveedores": {
        rfc: c.model_dump(mode="json") for rfc, c in servicio.configs(ctx.db, cliente).items()}}


@router.put("/proveedores/{rfc}")
def guardar_proveedor(clave: str, rfc: str, cuerpo: ConfigProveedorDiotSchema,
                      ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    cliente = cliente_o_404(ctx, clave)
    if not 12 <= len(rfc) <= 13:
        raise FiscalAgentError("RFC inválido.", 422)
    servicio.guardar_config(ctx.db, cliente, rfc, cuerpo)
    return {"exito": True}


@router.get("/{anio}/{mes}")
def diot(clave: str, anio: int = ANIO, mes: int = MES,
         ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    """Proveedores del mes con sus 54 campos y los errores contra el layout (si hay)."""
    cliente = cliente_o_404(ctx, clave)
    return {"exito": True, **servicio.diot_del_mes(ctx.db, cliente, anio, mes).a_dict()}


@router.get("/{anio}/{mes}/txt")
def archivo(clave: str, anio: int = ANIO, mes: int = MES,
            ctx: Contexto = Depends(contexto_actual)) -> Response:
    """El `.txt` de carga masiva. 422 si algún renglón no cumple el layout (no se entrega)."""
    cliente = cliente_o_404(ctx, clave)
    r = servicio.diot_del_mes(ctx.db, cliente, anio, mes)
    if not r.proveedores:
        raise FiscalAgentError("No hay operaciones con proveedores pagadas en el mes.", 404)
    errores = r.errores()
    if errores:
        raise FiscalAgentError("El archivo no cumple el layout: " + "; ".join(errores[:5]), 422)
    nombre = f"DIOT_{cliente.rfc or clave}_{anio}{mes:02d}.txt"
    return Response(r.archivo(), media_type="text/plain; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{nombre}"'})
