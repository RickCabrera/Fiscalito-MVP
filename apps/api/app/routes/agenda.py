"""
Calendario de vencimientos de la cartera y agenda semanal del despacho (P3-10).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.agenda import servicio
from app.tenancy import Contexto, cliente_o_404, clientes_visibles, contexto_actual

router = APIRouter(tags=["agenda"])


class MarcarObligacion(BaseModel):
    clave: str = Field(min_length=3, max_length=120)
    estado: Literal["presentada", "pendiente"]
    fecha_presentacion: date | None = None
    responsable_uid: str | None = None
    nota: str = Field("", max_length=1000)


class RegistrarDeclaracion(BaseModel):
    tipo: Literal["mensual", "diot", "balanza", "anual"]
    periodo: str = Field(min_length=4, max_length=7)
    fecha_presentacion: date | None = None
    ingresos_declarados: Decimal | None = None
    importe_pagado: Decimal | None = None
    numero_operacion: str = Field("", max_length=60)


class TareaNueva(BaseModel):
    titulo: str = Field(min_length=1, max_length=300)
    fecha: date
    cliente: str | None = None
    responsable_uid: str = ""
    descripcion: str = Field("", max_length=2000)
    estado: Literal["pendiente", "en_proceso", "hecha"] = "pendiente"


class TareaCambio(BaseModel):
    titulo: str | None = Field(None, min_length=1, max_length=300)
    fecha: date | None = None
    responsable_uid: str | None = None
    descripcion: str | None = Field(None, max_length=2000)
    estado: Literal["pendiente", "en_proceso", "hecha"] | None = None


class GenerarTareas(BaseModel):
    desde: date
    hasta: date
    cliente: str = ""
    responsable_uid: str = ""


def _clientes(ctx: Contexto) -> dict[int, Any]:
    return {c.id: c for c in clientes_visibles(ctx)}


@router.get("/calendario/cartera")
def calendario(
    desde: date, hasta: date, cliente: str = "", tipo: str = "", responsable: str = "",
    estado: str = "", con_tareas: bool = True, ctx: Contexto = Depends(contexto_actual),
) -> dict[str, Any]:
    """Obligaciones fiscales, patronales y de credenciales de la cartera en el rango."""
    if cliente:
        cliente_o_404(ctx, cliente)
    obligaciones = servicio.calendario(ctx, desde, hasta, cliente=cliente, tipo=tipo,
                                       responsable=responsable, estado=estado)
    salida: dict[str, Any] = {"exito": True, "desde": desde.isoformat(),
                              "hasta": hasta.isoformat(),
                              "obligaciones": [o.a_dict() for o in obligaciones]}
    if con_tareas:
        cid = cliente_o_404(ctx, cliente).id if cliente else None
        clientes = _clientes(ctx)
        salida["tareas"] = [servicio.tarea_json(t, clientes) for t in servicio.tareas(
            ctx, desde, hasta, cliente_id=cid, responsable=responsable)]
    return salida


@router.put("/clientes/{clave}/obligaciones/estado")
def marcar(clave: str, cuerpo: MarcarObligacion,
           ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    """Marca a mano una obligación como presentada (o la regresa a pendiente)."""
    c = cliente_o_404(ctx, clave)
    if cuerpo.responsable_uid:
        servicio._validar_responsable(ctx, cuerpo.responsable_uid)
    e = servicio.marcar(ctx.db, c, cuerpo.clave, cuerpo.estado, ctx.uid,
                        fecha_presentacion=cuerpo.fecha_presentacion,
                        responsable_uid=cuerpo.responsable_uid, nota=cuerpo.nota)
    return {"exito": True, "clave": e.clave, "estado": e.estado, "origen": e.origen}


@router.post("/clientes/{clave}/declaraciones")
def registrar_declaracion(clave: str, cuerpo: RegistrarDeclaracion,
                          ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    """Registra una declaración presentada: su obligación queda presentada sola."""
    c = cliente_o_404(ctx, clave)
    e = servicio.registrar_declaracion(
        ctx.db, c, cuerpo.tipo, cuerpo.periodo, ctx.uid,
        fecha_presentacion=cuerpo.fecha_presentacion,
        ingresos_declarados=cuerpo.ingresos_declarados, importe_pagado=cuerpo.importe_pagado,
        numero_operacion=cuerpo.numero_operacion)
    return {"exito": True, "clave": e.clave, "estado": e.estado, "origen": e.origen}


@router.get("/agenda/usuarios")
def usuarios(ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    """Usuarios del despacho, para asignar responsables."""
    return {"exito": True, "usuarios": servicio.usuarios_despacho(ctx)}


@router.get("/agenda/tareas")
def tareas(desde: date, hasta: date, cliente: str = "", responsable: str = "", estado: str = "",
           ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    cid = cliente_o_404(ctx, cliente).id if cliente else None
    clientes = _clientes(ctx)
    return {"exito": True, "tareas": [servicio.tarea_json(t, clientes) for t in servicio.tareas(
        ctx, desde, hasta, cliente_id=cid, responsable=responsable, estado=estado)]}


@router.post("/agenda/tareas")
def crear(cuerpo: TareaNueva, ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    c = cliente_o_404(ctx, cuerpo.cliente) if cuerpo.cliente else None
    t = servicio.crear_tarea(ctx, titulo=cuerpo.titulo, fecha=cuerpo.fecha, cliente=c,
                             responsable_uid=cuerpo.responsable_uid,
                             descripcion=cuerpo.descripcion, estado=cuerpo.estado)
    return {"exito": True, "tarea": servicio.tarea_json(t, _clientes(ctx))}


@router.put("/agenda/tareas/{tarea_id}")
def actualizar(tarea_id: int, cuerpo: TareaCambio,
               ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    t = servicio.actualizar_tarea(ctx, servicio.tarea_de(ctx, tarea_id),
                                  cuerpo.model_dump(exclude_unset=True))
    return {"exito": True, "tarea": servicio.tarea_json(t, _clientes(ctx))}


@router.delete("/agenda/tareas/{tarea_id}")
def borrar(tarea_id: int, ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    ctx.db.delete(servicio.tarea_de(ctx, tarea_id))
    ctx.db.flush()
    return {"exito": True}


@router.post("/agenda/tareas/desde-obligaciones")
def generar(cuerpo: GenerarTareas, ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    """Crea una tarea por cada obligación pendiente o vencida del rango (idempotente)."""
    if cuerpo.cliente:
        cliente_o_404(ctx, cuerpo.cliente)
    nuevas = servicio.generar_tareas(ctx, cuerpo.desde, cuerpo.hasta, cliente=cuerpo.cliente,
                                     responsable_uid=cuerpo.responsable_uid)
    clientes = _clientes(ctx)
    return {"exito": True, "creadas": len(nuevas),
            "tareas": [servicio.tarea_json(t, clientes) for t in nuevas]}
