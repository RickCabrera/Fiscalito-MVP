"""
Suscripción y cobro del plan del despacho (P5-08). Contrato: `docs/api-contract.md`
§"Suscripción y cobro de planes".

- `router` (protegido): estado, alta, cambio y cancelación. Sólo el dueño modifica.
  Sus rutas siguen funcionando en modo solo lectura (`vigencia.RUTAS_EXENTAS`): son las
  que sacan al despacho del bloqueo.
- `router_publico`: el webhook del proveedor de pagos. Sin sesión de Firebase; se
  autentica con la firma del proveedor (400 si no cuadra) y es idempotente.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import obtener_db
from app.suscripciones import servicio
from app.tenancy import Contexto, contexto_actual

router = APIRouter(prefix="/suscripcion", tags=["Suscripción"])
router_publico = APIRouter(tags=["Suscripción"])


class AltaSuscripcion(BaseModel):
    plan: str = Field(min_length=1, max_length=40)
    correo: str = Field("", max_length=320)


class CambioPlan(BaseModel):
    plan: str = Field(min_length=1, max_length=40)


@router.get("", summary="Plan, estado de la suscripción, uso, bloqueos y pagos")
def estado(ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    return servicio.resumen(ctx)


@router.post("", summary="Suscribirse a un plan (alta del cobro)")
def suscribirse(cuerpo: AltaSuscripcion, ctx: Contexto = Depends(contexto_actual)
                ) -> dict[str, Any]:
    return servicio.suscribirse(ctx, cuerpo.plan, cuerpo.correo)


@router.put("/plan", summary="Cambiar de plan")
def cambiar_plan(cuerpo: CambioPlan, ctx: Contexto = Depends(contexto_actual)
                 ) -> dict[str, Any]:
    p = servicio.cambiar_plan(ctx, cuerpo.plan)
    return {"exito": True, "plan": p.id}


@router.post("/cancelar", summary="Cancelar la suscripción (acceso hasta fin de periodo)")
def cancelar(ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    return servicio.cancelar(ctx)


@router_publico.post("/pagos/webhook", summary="Webhook del proveedor de pagos (firmado)")
async def webhook(request: Request, db: Session = Depends(obtener_db)) -> dict[str, Any]:
    cuerpo = await request.body()
    return servicio.procesar_webhook(db, cuerpo, dict(request.headers))
