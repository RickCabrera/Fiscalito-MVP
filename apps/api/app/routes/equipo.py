"""
Equipo del despacho (P5-01): usuarios, invitaciones, roles, asignaciones y plan.

Sólo el dueño gestiona (ver `app/equipo/servicio.py`). Aceptar una invitación es la única
ruta que NO pasa por `contexto_actual`: quien acepta puede no tener usuario todavía, o tener
uno en su despacho autocreado, y la invitación es la que decide a qué despacho entra.
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth_firebase import usuario_actual
from app.db.session import obtener_db
from app.equipo import servicio
from app.tenancy import Contexto, contexto_actual

router = APIRouter(prefix="/equipo", tags=["equipo"])

Rol = Literal["dueno", "contador", "auxiliar"]


class InvitacionNueva(BaseModel):
    correo: str = Field(min_length=3, max_length=320)
    rol: Rol


class AceptarInvitacion(BaseModel):
    token: str = Field(min_length=10, max_length=200)
    nombre: str = Field("", max_length=300)


class CambioRol(BaseModel):
    rol: Rol


class CambioPlan(BaseModel):
    plan: str = Field(min_length=1, max_length=40)


@router.get("")
def equipo(ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    """Usuarios del despacho, sus clientes asignados, el plan y las invitaciones vigentes."""
    return servicio.resumen(ctx)


@router.post("/invitaciones")
def invitar(cuerpo: InvitacionNueva, ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    """Invita un correo con un rol y le manda el enlace (sólo el dueño)."""
    inv, _token = servicio.invitar(ctx, cuerpo.correo, cuerpo.rol)
    return {"exito": True, "invitacion": servicio.invitacion_json(inv)}


@router.delete("/invitaciones/{invitacion_id}")
def revocar(invitacion_id: int, ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    servicio.revocar(ctx, invitacion_id)
    return {"exito": True}


@router.post("/invitaciones/aceptar")
def aceptar(
    cuerpo: AceptarInvitacion,
    uid: str = Depends(usuario_actual),
    db: Session = Depends(obtener_db),
) -> dict[str, Any]:
    """El usuario de la sesión se une al despacho de la invitación."""
    u = servicio.aceptar(db, uid, cuerpo.token, cuerpo.nombre)
    return {"exito": True, "despacho_id": u.despacho_id, "rol": u.rol}


@router.put("/usuarios/{uid}/rol")
def cambiar_rol(uid: str, cuerpo: CambioRol,
                ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    u = servicio.cambiar_rol(ctx, uid, cuerpo.rol)
    return {"exito": True, "uid": u.uid, "rol": u.rol}


@router.post("/usuarios/{uid}/desactivar")
def desactivar(uid: str, ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    u = servicio.desactivar(ctx, uid)
    return {"exito": True, "uid": u.uid, "activo": u.activo}


@router.post("/usuarios/{uid}/reactivar")
def reactivar(uid: str, ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    u = servicio.reactivar(ctx, uid)
    return {"exito": True, "uid": u.uid, "activo": u.activo}


@router.post("/usuarios/{uid}/clientes/{clave}")
def asignar(uid: str, clave: str, ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    servicio.asignar(ctx, uid, clave)
    return {"exito": True}


@router.delete("/usuarios/{uid}/clientes/{clave}")
def desasignar(uid: str, clave: str, ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    servicio.desasignar(ctx, uid, clave)
    return {"exito": True}


@router.put("/plan")
def cambiar_plan(cuerpo: CambioPlan, ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    """El dueño elige el plan del despacho (la fuente de los límites es `app/planes.py`)."""
    p = servicio.cambiar_plan(ctx, cuerpo.plan)
    return {"exito": True, "plan": {"id": p.id, "nombre": p.nombre,
                                    "max_usuarios": p.max_usuarios,
                                    "max_clientes": p.max_clientes}}
