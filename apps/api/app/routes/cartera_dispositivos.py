"""
Checadores de un cliente en la cartera (P0-01): listar, alta, edición y baja.

Salieron de `routes/cartera.py` en P6-05 (tope de 300 líneas) sin cambiar comportamiento: se
registran en el mismo `router` de la cartera, que es el que monta `app/main.py`.
"""

from __future__ import annotations

import uuid

from fastapi import Depends

from app import almacen_cartera as almacen
from app.exceptions import FiscalAgentError
from app.routes.cartera import _ERRORES, _ERRORES_ESCRITURA, router
from app.schemas.cartera import OperacionResponse
from app.schemas.dispositivo import (
    DispositivoGuardadoResponse,
    DispositivoSchema,
    DispositivosResponse,
)
from app.tenancy import Contexto, cliente_o_404, contexto_actual


def _serial_repetido(
    ctx: Contexto, cliente_id: str, dispositivo: DispositivoSchema, propio: str | None
) -> None:
    """422 si OTRO dispositivo del cliente ya tiene ese serial (misma regla que el front)."""
    if not dispositivo.serial:
        return
    cliente = cliente_o_404(ctx, cliente_id)
    for otro in almacen.dispositivos_de(ctx.db, cliente):
        if otro.clave != propio and str((otro.datos or {}).get("serial", "")).strip() == (
            dispositivo.serial
        ):
            raise FiscalAgentError(
                f"Ya hay otro dispositivo con el serial {dispositivo.serial}.", status_code=422
            )


@router.get(
    "/cartera/clientes/{cliente_id}/dispositivos",
    response_model=DispositivosResponse,
    responses=_ERRORES,
    summary="Los checadores de un cliente",
)
def listar_dispositivos(
    cliente_id: str, ctx: Contexto = Depends(contexto_actual)
) -> DispositivosResponse:
    cliente = cliente_o_404(ctx, cliente_id)
    dispositivos = [
        almacen.documento_dispositivo(d) for d in almacen.dispositivos_de(ctx.db, cliente)
    ]
    return DispositivosResponse(
        cliente_id=cliente_id, total=len(dispositivos), dispositivos=tuple(dispositivos)
    )


@router.post(
    "/cartera/clientes/{cliente_id}/dispositivos",
    response_model=DispositivoGuardadoResponse,
    status_code=201,
    responses=_ERRORES_ESCRITURA,
    summary="Alta de un checador",
    description="El id lo genera el backend: el nombre y el serial son editables y "
    "repetibles, y un id derivado de ellos convertiría un cambio de nombre en un "
    "dispositivo nuevo con el anterior huérfano.",
)
def crear_dispositivo(
    cliente_id: str,
    dispositivo: DispositivoSchema,
    ctx: Contexto = Depends(contexto_actual),
) -> DispositivoGuardadoResponse:
    cliente = cliente_o_404(ctx, cliente_id)
    _serial_repetido(ctx, cliente_id, dispositivo, None)
    clave = uuid.uuid4().hex[:20]
    almacen.guardar_dispositivo(ctx.db, cliente, clave, dispositivo.model_dump(mode="json"))
    return DispositivoGuardadoResponse(id=clave, mensaje=f"Dispositivo {clave} dado de alta.")


@router.put(
    "/cartera/clientes/{cliente_id}/dispositivos/{dispositivo_id}",
    response_model=DispositivoGuardadoResponse,
    responses=_ERRORES_ESCRITURA,
    summary="Edición de un checador",
    description="404 si el dispositivo no existe en ese cliente: las altas van por POST.",
)
def editar_dispositivo(
    cliente_id: str,
    dispositivo_id: str,
    dispositivo: DispositivoSchema,
    ctx: Contexto = Depends(contexto_actual),
) -> DispositivoGuardadoResponse:
    cliente = cliente_o_404(ctx, cliente_id)
    if almacen.buscar_dispositivo(ctx.db, cliente, dispositivo_id) is None:
        raise FiscalAgentError(
            f"No existe el dispositivo '{dispositivo_id}' en ese cliente.", status_code=404
        )
    _serial_repetido(ctx, cliente_id, dispositivo, dispositivo_id)
    almacen.guardar_dispositivo(
        ctx.db, cliente, dispositivo_id, dispositivo.model_dump(mode="json")
    )
    return DispositivoGuardadoResponse(
        id=dispositivo_id, mensaje=f"Dispositivo {dispositivo_id} guardado."
    )


@router.delete(
    "/cartera/clientes/{cliente_id}/dispositivos/{dispositivo_id}",
    response_model=OperacionResponse,
    responses=_ERRORES,
    summary="Baja de un checador",
    description="Idempotente. No borra a nadie de la plantilla ni del aparato físico.",
)
def borrar_dispositivo(
    cliente_id: str, dispositivo_id: str, ctx: Contexto = Depends(contexto_actual)
) -> OperacionResponse:
    cliente = cliente_o_404(ctx, cliente_id)
    dispositivo = almacen.buscar_dispositivo(ctx.db, cliente, dispositivo_id)
    if dispositivo is not None:
        ctx.db.delete(dispositivo)
        ctx.db.flush()
    return OperacionResponse(mensaje=f"Dispositivo {dispositivo_id} dado de baja.")
