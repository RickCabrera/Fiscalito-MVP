"""
Historial de nóminas del cliente (P4-02): listar, abrir, cerrar y comparar.

Abrir devuelve lo GUARDADO, nunca recalcula: una nómina de hace tres meses se ve igual
a como se calculó aunque hayan cambiado tablas o criterios. Tenencia: `cliente_o_404`
y, dentro del cliente, `periodo_o_404` (un periodo de otro cliente es 404).
"""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, Query

from app import nomina_servicio as srv
from app.exceptions import FiscalAgentError
from app.schemas.declaraciones import ErrorResponse
from app.schemas.nomina_p4 import (
    ComparacionResponse,
    DiferenciaEmpleado,
    HistorialResponse,
    PeriodoGuardadoResponse,
    ResumenPeriodoSchema,
)
from app.tenancy import Contexto, cliente_o_404, contexto_actual

router = APIRouter(tags=["Nómina — historial"])
_ERR = {401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}}
CERO = Decimal("0.00")


@router.get(
    "/nomina/clientes/{cliente_id}/historial",
    response_model=HistorialResponse,
    responses=_ERR,
    summary="Historial de nóminas del cliente",
)
def listar_historial(
    cliente_id: str,
    tipo: str | None = Query(default=None),
    ctx: Contexto = Depends(contexto_actual),
) -> HistorialResponse:
    cliente = cliente_o_404(ctx, cliente_id)
    return HistorialResponse(
        cliente=cliente_id,
        periodos=tuple(
            ResumenPeriodoSchema(**srv.resumen(p)) for p in srv.historial(ctx.db, cliente, tipo)
        ),
    )


@router.get(
    "/nomina/clientes/{cliente_id}/periodos/{periodo_id}",
    response_model=PeriodoGuardadoResponse,
    responses=_ERR,
    summary="Abrir un periodo guardado, idéntico a como se calculó",
)
def abrir_periodo(
    cliente_id: str, periodo_id: int, ctx: Contexto = Depends(contexto_actual)
) -> PeriodoGuardadoResponse:
    p = srv.periodo_o_404(ctx.db, cliente_o_404(ctx, cliente_id), periodo_id)
    return PeriodoGuardadoResponse(
        periodo=ResumenPeriodoSchema(**srv.resumen(p)),
        criterios=p.criterios,
        parametros=p.parametros,
        resultado=p.resultado,
    )


@router.post(
    "/nomina/clientes/{cliente_id}/periodos/{periodo_id}/cerrar",
    response_model=PeriodoGuardadoResponse,
    responses=_ERR,
    summary="Cerrar un periodo: ya no se puede recalcular",
)
def cerrar_periodo(
    cliente_id: str, periodo_id: int, ctx: Contexto = Depends(contexto_actual)
) -> PeriodoGuardadoResponse:
    p = srv.periodo_o_404(ctx.db, cliente_o_404(ctx, cliente_id), periodo_id)
    if p.estado == "timbrada":
        raise FiscalAgentError("El periodo ya está timbrado.", status_code=409)
    p.estado = "cerrada"
    ctx.db.flush()
    return PeriodoGuardadoResponse(
        periodo=ResumenPeriodoSchema(**srv.resumen(p)),
        criterios=p.criterios,
        parametros=p.parametros,
        resultado=p.resultado,
    )


@router.get(
    "/nomina/clientes/{cliente_id}/comparar",
    response_model=ComparacionResponse,
    responses=_ERR,
    summary="Comparar dos periodos guardados (b − a)",
)
def comparar(
    cliente_id: str, a: int = Query(), b: int = Query(), ctx: Contexto = Depends(contexto_actual)
) -> ComparacionResponse:
    cliente = cliente_o_404(ctx, cliente_id)
    pa, pb = srv.periodo_o_404(ctx.db, cliente, a), srv.periodo_o_404(ctx.db, cliente, b)
    ra = {r.empleado_no: r for r in srv.recibos_de(ctx.db, pa)}
    rb = {r.empleado_no: r for r in srv.recibos_de(ctx.db, pb)}
    filas = []
    for no in sorted(set(ra) | set(rb)):
        x, y = ra.get(no), rb.get(no)
        filas.append(
            DiferenciaEmpleado(
                empleado_no=no,
                nombre=(y or x).nombre,
                neto_a=x.neto if x else None,
                neto_b=y.neto if y else None,
                diferencia=(y.neto if y else CERO) - (x.neto if x else CERO),
            )
        )
    return ComparacionResponse(
        a=ResumenPeriodoSchema(**srv.resumen(pa)),
        b=ResumenPeriodoSchema(**srv.resumen(pb)),
        diferencia_neto=pb.total_neto - pa.total_neto,
        diferencia_isr=pb.total_isr - pa.total_isr,
        diferencia_percepciones=pb.total_percepciones - pa.total_percepciones,
        por_empleado=tuple(filas),
    )
