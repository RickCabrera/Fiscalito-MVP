"""
Alertas fiscales del despacho (P3-09): listar con filtros, marcar resuelta, conteo por
cliente y evaluación manual (la diaria la hace el trabajo `alertas.programado`).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from app.alertas import reglas
from app.exceptions import FiscalAgentError
from app.modelos.alertas import SEVERIDADES, AlertaFiscal
from app.tenancy import Contexto, cliente_o_404, clientes_visibles, contexto_actual

router = APIRouter(prefix="/alertas", tags=["alertas"])


def _visibles(ctx: Contexto, clave: str = "") -> dict[int, Any]:
    if clave:
        c = cliente_o_404(ctx, clave)
        return {c.id: c}
    return {c.id: c for c in clientes_visibles(ctx)}


@router.get("")
def listar(
    cliente: str = "", tipo: str = "", severidad: str = "",
    resuelta: bool = False, limite: int = Query(200, ge=1, le=1000),
    ctx: Contexto = Depends(contexto_actual),
) -> dict[str, Any]:
    """Alertas de los clientes visibles, las más graves y recientes primero."""
    clientes = _visibles(ctx, cliente)
    if severidad and severidad not in SEVERIDADES:
        raise FiscalAgentError("Severidad inválida: alta, media o baja.", 422)
    q = select(AlertaFiscal).where(AlertaFiscal.despacho_id == ctx.despacho_id,
                                   AlertaFiscal.cliente_id.in_(clientes),
                                   AlertaFiscal.resuelta.is_(resuelta))
    if tipo:
        q = q.where(AlertaFiscal.tipo == tipo)
    if severidad:
        q = q.where(AlertaFiscal.severidad == severidad)
    orden = {s: i for i, s in enumerate(SEVERIDADES)}
    filas = sorted(ctx.db.scalars(q), key=lambda a: (orden.get(a.severidad, 9),
                                                     -a.fecha.toordinal(), a.id))[:limite]
    return {"exito": True, "alertas": [reglas.alerta_json(a, clientes[a.cliente_id])
                                       for a in filas]}


@router.get("/conteo")
def conteo(ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    """Alertas abiertas por cliente y severidad (para la campana y la cartera)."""
    clientes = _visibles(ctx)
    por_cliente: dict[str, dict[str, int]] = {}
    for a in ctx.db.scalars(select(AlertaFiscal).where(
            AlertaFiscal.despacho_id == ctx.despacho_id,
            AlertaFiscal.cliente_id.in_(clientes), AlertaFiscal.resuelta.is_(False))):
        d = por_cliente.setdefault(clientes[a.cliente_id].clave,
                                   {"total": 0, "alta": 0, "media": 0, "baja": 0})
        d["total"] += 1
        d[a.severidad] = d.get(a.severidad, 0) + 1
    return {"exito": True, "total": sum(d["total"] for d in por_cliente.values()),
            "alta": sum(d["alta"] for d in por_cliente.values()), "por_cliente": por_cliente}


@router.post("/{alerta_id}/resolver")
def resolver(alerta_id: int, ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    clientes = _visibles(ctx)
    a = ctx.db.get(AlertaFiscal, alerta_id)
    if a is None or a.despacho_id != ctx.despacho_id or a.cliente_id not in clientes:
        raise FiscalAgentError("No existe esa alerta en tu despacho.", 404)
    a.resuelta, a.resuelta_por, a.resuelta_en = True, ctx.uid, datetime.now(UTC)
    ctx.db.flush()
    return {"exito": True, "alerta": reglas.alerta_json(a, clientes[a.cliente_id])}


@router.post("/evaluar")
def evaluar(cliente: str = "", ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    """Corre las reglas ahora (un cliente o todos los visibles), sin esperar al diario."""
    resultado = {c.clave: reglas.evaluar_cliente(ctx.db, c)
                 for c in _visibles(ctx, cliente).values()}
    return {"exito": True, "clientes": resultado}
