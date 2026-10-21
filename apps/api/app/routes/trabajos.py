"""
`/api/v1/trabajos` — los trabajos en segundo plano del despacho (P0-04).

Sólo se ven los trabajos con `despacho_id` del contexto; los de sistema (despacho nulo)
nunca. Un auxiliar ve sólo los de sus clientes asignados. Trabajo de otro despacho = 404.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auditoria import registrar
from app.exceptions import FiscalAgentError
from app.modelos.nucleo import Cliente
from app.modelos.trabajos import ESTADOS, Trabajo
from app.schemas.trabajos import EncolarDiagnostico, ListaTrabajos, TrabajoSalida, UnTrabajo
from app.tenancy import Contexto, cliente_o_404, clientes_visibles, contexto_actual
from app.trabajos import cancelar, encolar, reintentar

router = APIRouter(prefix="/trabajos", tags=["trabajos"])


def _salida(t: Trabajo, claves: dict[int, str]) -> TrabajoSalida:
    return TrabajoSalida(
        id=t.id,
        tipo=t.tipo,
        estado=t.estado,
        cliente=claves.get(t.cliente_id) if t.cliente_id is not None else None,
        intentos=t.intentos,
        max_intentos=t.max_intentos,
        ejecutar_en=t.ejecutar_en,
        iniciado_en=t.iniciado_en,
        terminado_en=t.terminado_en,
        creado_en=t.creado_en,
        error=t.error,
        resultado=t.resultado,
        carga=t.carga,
    )


def _claves(db: Session, ids: set[int]) -> dict[int, str]:
    if not ids:
        return {}
    return dict(db.execute(select(Cliente.id, Cliente.clave).where(Cliente.id.in_(ids))).all())


def _trabajo_o_404(ctx: Contexto, trabajo_id: int) -> Trabajo:
    trabajo = ctx.db.get(Trabajo, trabajo_id)
    visible = trabajo is not None and trabajo.despacho_id == ctx.despacho_id
    if visible and ctx.es_auxiliar:
        permitidos = {c.id for c in clientes_visibles(ctx)}
        visible = trabajo.cliente_id in permitidos  # type: ignore[union-attr]
    if not visible:
        raise FiscalAgentError(f"No existe el trabajo {trabajo_id}.", status_code=404)
    return trabajo  # type: ignore[return-value]


def _uno(ctx: Contexto, trabajo: Trabajo) -> UnTrabajo:
    ids = {trabajo.cliente_id} if trabajo.cliente_id is not None else set()
    return UnTrabajo(trabajo=_salida(trabajo, _claves(ctx.db, ids)))


@router.get("", response_model=ListaTrabajos)
def listar(
    estado: str | None = Query(default=None),
    tipo: str | None = Query(default=None),
    cliente: str | None = Query(default=None, description="Clave del cliente."),
    limite: int = Query(default=50, ge=1, le=200),
    ctx: Contexto = Depends(contexto_actual),
) -> ListaTrabajos:
    """Trabajos del despacho, del más reciente al más viejo."""
    if estado is not None and estado not in ESTADOS:
        raise FiscalAgentError(f"Estado desconocido: '{estado}'.", status_code=422)
    consulta = select(Trabajo).where(Trabajo.despacho_id == ctx.despacho_id)
    if cliente is not None:
        consulta = consulta.where(Trabajo.cliente_id == cliente_o_404(ctx, cliente).id)
    elif ctx.es_auxiliar:
        consulta = consulta.where(Trabajo.cliente_id.in_([c.id for c in clientes_visibles(ctx)]))
    if estado is not None:
        consulta = consulta.where(Trabajo.estado == estado)
    if tipo is not None:
        consulta = consulta.where(Trabajo.tipo == tipo)
    trabajos = list(ctx.db.scalars(consulta.order_by(Trabajo.id.desc()).limit(limite)))
    claves = _claves(ctx.db, {t.cliente_id for t in trabajos if t.cliente_id is not None})
    return ListaTrabajos(trabajos=[_salida(t, claves) for t in trabajos])


@router.get("/{trabajo_id}", response_model=UnTrabajo)
def obtener(trabajo_id: int, ctx: Contexto = Depends(contexto_actual)) -> UnTrabajo:
    """Un trabajo del despacho."""
    return _uno(ctx, _trabajo_o_404(ctx, trabajo_id))


@router.post("/{trabajo_id}/reintentar", response_model=UnTrabajo)
def reintentar_trabajo(trabajo_id: int, ctx: Contexto = Depends(contexto_actual)) -> UnTrabajo:
    """Vuelve a encolar un trabajo fallido o cancelado (409 si está en otro estado)."""
    trabajo = reintentar(ctx.db, _trabajo_o_404(ctx, trabajo_id))
    registrar(ctx, "trabajo.reintentar", "trabajo", trabajo.id, {"tipo": trabajo.tipo},
              cliente=_cliente_de(ctx, trabajo))
    return _uno(ctx, trabajo)


@router.post("/{trabajo_id}/cancelar", response_model=UnTrabajo)
def cancelar_trabajo(trabajo_id: int, ctx: Contexto = Depends(contexto_actual)) -> UnTrabajo:
    """Cancela un trabajo pendiente (409 si ya corrió o está corriendo)."""
    trabajo = cancelar(ctx.db, _trabajo_o_404(ctx, trabajo_id))
    registrar(ctx, "trabajo.cancelar", "trabajo", trabajo.id, {"tipo": trabajo.tipo},
              cliente=_cliente_de(ctx, trabajo))
    return _uno(ctx, trabajo)


@router.post("/clientes/{clave}/diagnostico", response_model=UnTrabajo, status_code=201)
def encolar_diagnostico(
    clave: str,
    cuerpo: EncolarDiagnostico | None = None,
    ejecutar_en: datetime | None = Query(default=None),
    ctx: Contexto = Depends(contexto_actual),
) -> UnTrabajo:
    """
    Encola el trabajo de prueba `diagnostico.cliente` (cuenta empleados del cliente).

    Es la demo de la ficha: con `fallar_intentos` se ve el reintento con backoff. La clave
    única impide encolar dos a la vez para el mismo cliente.
    """
    cliente = cliente_o_404(ctx, clave)
    if ejecutar_en is not None and ejecutar_en.tzinfo is None:
        raise FiscalAgentError("`ejecutar_en` debe traer zona horaria.", status_code=422)
    fallar = max(0, min((cuerpo or EncolarDiagnostico()).fallar_intentos, 10))
    trabajo = encolar(
        ctx.db,
        "diagnostico.cliente",
        {"fallar_intentos": fallar},
        despacho_id=ctx.despacho_id,
        cliente_id=cliente.id,
        ejecutar_en=ejecutar_en,
        clave_unica=f"diagnostico.cliente:{cliente.id}",
    )
    registrar(ctx, "trabajo.encolar", "trabajo", trabajo.id, {"tipo": trabajo.tipo}, cliente)
    return _uno(ctx, trabajo)


def _cliente_de(ctx: Contexto, trabajo: Trabajo) -> Cliente | None:
    return ctx.db.get(Cliente, trabajo.cliente_id) if trabajo.cliente_id is not None else None
