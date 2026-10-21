"""
CRUD de la cartera del despacho: clientes, empleados y dispositivos. (R-07 → P0-01)

EL BACKEND ES EL ÚNICO DUEÑO DEL DATO
-------------------------------------
Hasta P0-01 había **dos dueños**: el front escribía Firestore directo y este router, con
`firebase-admin`, esperaba detrás de un interruptor apagado (`VITE_CARTERA_BACKEND`).
Ahora todo pasa por aquí y se guarda en SQL (`app/modelos/nucleo.py`); el front ya no
toca Firestore para la cartera y el interruptor desapareció. Lo que había en Firestore se
trae con `scripts/migrar_firestore.py`.

TENENCIA
--------
Toda ruta depende de `contexto_actual` y obtiene el cliente con `cliente_o_404`. El
despacho sale del token verificado; **ninguna ruta acepta un uid ni un despacho por
parámetro**. Un cliente de otro despacho es 404, nunca 403: un 403 confirmaría que existe.

LO QUE TODAVÍA NO HACE
----------------------
`POST /nomina/calcular-periodo` sigue recibiendo la plantilla en el cuerpo (R-08). Que el
cálculo lea `empleados_de` en vez de creerle al navegador es P4-01.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import ValidationError

from app import almacen_cartera as almacen
from app.exceptions import FiscalAgentError
from app.schemas.cartera import (
    ClienteCarteraSchema,
    ClientesCarteraResponse,
    EmpleadoIlegible,
    EmpleadosCarteraResponse,
    OperacionResponse,
)
from app.schemas.declaraciones import ErrorResponse
from app.schemas.dispositivo import (
    DispositivoGuardadoResponse,
    DispositivoSchema,
    DispositivosResponse,
)
from app.schemas.empleado import EmpleadoCarteraSchema
from app.tenancy import Contexto, cliente_o_404, clientes_visibles, contexto_actual

router = APIRouter(tags=["Cartera del despacho"])

_ERRORES = {401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}}
_ERRORES_ESCRITURA = {**_ERRORES, 409: {"model": ErrorResponse}, 422: {"model": ErrorResponse}}


def _razon(exc: ValidationError) -> str:
    """La primera causa de un `ValidationError`, en una línea legible para la ficha."""
    errores = exc.errors()
    if not errores:
        return "No pasa la validación actual."
    primero = errores[0]
    campo = ".".join(str(p) for p in primero.get("loc", ())) or "documento"
    mensaje = str(primero.get("msg", "valor inválido")).removeprefix("Value error, ")
    extra = f" (y {len(errores) - 1} más)" if len(errores) > 1 else ""
    return f"{campo}: {mensaje}{extra}"


# ── Clientes ──────────────────────────────────────────────────


@router.get(
    "/cartera/clientes",
    response_model=ClientesCarteraResponse,
    responses={401: {"model": ErrorResponse}},
    summary="Los clientes del despacho autenticado",
    description="Los clientes del despacho de **quien hace el request**, resuelto desde el "
    "ID token. Los documentos van tal como están guardados (no se tipan estricto al leer).",
)
def listar_clientes(ctx: Contexto = Depends(contexto_actual)) -> ClientesCarteraResponse:
    clientes = [almacen.documento_cliente(c) for c in clientes_visibles(ctx)]
    return ClientesCarteraResponse(total=len(clientes), clientes=tuple(clientes))


@router.put(
    "/cartera/clientes/{cliente_id}",
    response_model=OperacionResponse,
    responses=_ERRORES_ESCRITURA,
    summary="Alta o edición de un cliente",
    description="Idempotente: el mismo `cliente_id` sobrescribe (merge: los campos que este "
    "esquema no conoce se conservan). El cuerpo se valida contra `ClienteCarteraSchema`.",
)
def guardar_cliente(
    cliente_id: str,
    cliente: ClienteCarteraSchema,
    ctx: Contexto = Depends(contexto_actual),
) -> OperacionResponse:
    if cliente.id != cliente_id:
        # No se "arregla" en silencio: adivinar cuál de los dos vale escribiría el
        # cliente equivocado.
        raise FiscalAgentError(
            f"El id de la URL ({cliente_id!r}) no coincide con el del cuerpo "
            f"({cliente.id!r}).",
            status_code=422,
        )
    datos = cliente.model_dump(mode="json", exclude={"id"})
    existente = almacen.buscar_cliente(ctx.db, ctx.despacho_id, cliente_id)
    if existente is None:
        if ctx.es_auxiliar:
            raise FiscalAgentError("Tu rol no permite dar de alta clientes.", status_code=403)
        almacen.crear_cliente(ctx.db, ctx.despacho_id, cliente_id, datos)
    else:
        # Pasa por `cliente_o_404` para que un auxiliar no edite lo que no ve.
        almacen.actualizar_cliente(cliente_o_404(ctx, cliente_id), datos)
    return OperacionResponse(mensaje=f"Cliente {cliente_id} guardado.")


@router.delete(
    "/cartera/clientes/{cliente_id}",
    response_model=OperacionResponse,
    responses=_ERRORES,
    summary="Baja de un cliente, con sus empleados y dispositivos",
    description="Borra en cascada (llaves foráneas `ON DELETE CASCADE`): sin esto los "
    "empleados quedarían huérfanos y reaparecerían al recrear un cliente con el mismo id.",
)
def borrar_cliente(cliente_id: str, ctx: Contexto = Depends(contexto_actual)) -> OperacionResponse:
    almacen.borrar_cliente(ctx.db, cliente_o_404(ctx, cliente_id))
    return OperacionResponse(mensaje=f"Cliente {cliente_id} dado de baja.")


# ── Empleados ─────────────────────────────────────────────────


@router.get(
    "/cartera/clientes/{cliente_id}/empleados",
    response_model=EmpleadosCarteraResponse,
    responses=_ERRORES,
    summary="La plantilla de un cliente del despacho",
    description="Lectura laxa: un empleado guardado que ya no pasa la validación actual NO "
    "tumba la respuesta; va en `ilegibles` con su razón.",
)
def listar_empleados(
    cliente_id: str, ctx: Contexto = Depends(contexto_actual)
) -> EmpleadosCarteraResponse:
    cliente = cliente_o_404(ctx, cliente_id)
    # **La lectura NO es estricta.** Un documento de una versión anterior —un NSS de 9
    # dígitos, un campo que falta— producía un 500, y como el front pide los empleados
    # de todos los clientes en paralelo, uno solo dejaba la cartera COMPLETA en cero.
    # Los que no pasan se reportan con su razón (R-10) y la ficha los pinta.
    # `total` EXCLUYE a los ilegibles.
    empleados: list[EmpleadoCarteraSchema] = []
    ilegibles: list[EmpleadoIlegible] = []
    for fila in almacen.empleados_de(ctx.db, cliente):
        crudo = fila.datos or {}
        try:
            empleados.append(EmpleadoCarteraSchema(**crudo))
        except ValidationError as exc:
            ilegibles.append(
                EmpleadoIlegible(
                    empleado_no=fila.empleado_no,
                    nombre=str(crudo.get("nombre") or ""),
                    razon=_razon(exc),
                )
            )

    return EmpleadosCarteraResponse(
        cliente_id=cliente_id,
        total=len(empleados),
        sin_vincular=sum(1 for e in empleados if not e.vinculado_al_checador),
        ilegibles=tuple(i.empleado_no for i in ilegibles),
        ilegibles_detalle=tuple(ilegibles),
        empleados=tuple(empleados),
    )


@router.put(
    "/cartera/clientes/{cliente_id}/empleados/{empleado_no}",
    response_model=OperacionResponse,
    responses=_ERRORES_ESCRITURA,
    summary="Alta o edición de un empleado",
    description="El `empleado_no` de la URL es la llave del CÁLCULO; `employee_no`, en el "
    "cuerpo, es la del CHECADOR y puede ser nula. NSS: 11 dígitos o vacío (§D25).",
)
def guardar_empleado(
    cliente_id: str,
    empleado_no: str,
    empleado: EmpleadoCarteraSchema,
    ctx: Contexto = Depends(contexto_actual),
) -> OperacionResponse:
    if empleado.empleado_no != empleado_no:
        raise FiscalAgentError(
            f"El número de la URL ({empleado_no!r}) no coincide con el del cuerpo "
            f"({empleado.empleado_no!r}).",
            status_code=422,
        )
    # No se crea el cliente al vuelo: un empleado colgando de un cliente que no existe
    # es invisible en la lista y aparece en el cálculo.
    cliente = cliente_o_404(ctx, cliente_id)
    almacen.guardar_empleado(ctx.db, cliente, empleado_no, empleado.model_dump(mode="json"))
    return OperacionResponse(mensaje=f"Empleado {empleado_no} guardado.")


@router.delete(
    "/cartera/clientes/{cliente_id}/empleados/{empleado_no}",
    response_model=OperacionResponse,
    responses=_ERRORES,
    summary="Baja de un empleado",
    description="Idempotente: borrar uno que no existe responde 200.",
)
def borrar_empleado(
    cliente_id: str, empleado_no: str, ctx: Contexto = Depends(contexto_actual)
) -> OperacionResponse:
    cliente = cliente_o_404(ctx, cliente_id)
    empleado = almacen.buscar_empleado(ctx.db, cliente, empleado_no)
    if empleado is not None:
        ctx.db.delete(empleado)
        ctx.db.flush()
    return OperacionResponse(mensaje=f"Empleado {empleado_no} dado de baja.")


# ── Dispositivos ──────────────────────────────────────────────


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
