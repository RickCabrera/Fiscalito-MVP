"""
`GET /api/v1/auditoria` — la bitácora del despacho (P0-07). Sólo `dueno` y `contador`.

El filtro `cliente` es la clave pública y NO pasa por `cliente_o_404`: un cliente ya
borrado conserva sus renglones (con `cliente_clave`) y tiene que poder consultarse.
"""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select

from app.exceptions import FiscalAgentError
from app.modelos.auditoria import EventoAuditoria
from app.schemas.trabajos import EventoSalida, PaginaAuditoria
from app.tenancy import Contexto, contexto_actual, exigir_rol

router = APIRouter(prefix="/auditoria", tags=["auditoria"])

# Los filtros por día se leen en la hora del despacho, no en UTC.
ZONA = ZoneInfo("America/Mexico_City")


def _inicio_del_dia(dia: date) -> datetime:
    return datetime.combine(dia, time.min, tzinfo=ZONA)


@router.get("", response_model=PaginaAuditoria)
def listar(
    usuario: str | None = Query(default=None, description="uid de quien hizo la acción."),
    cliente: str | None = Query(default=None, description="Clave del cliente."),
    accion: str | None = Query(default=None, description="Exacta, o prefijo con `*`."),
    desde: date | None = Query(default=None, description="Día inicial (incluido)."),
    hasta: date | None = Query(default=None, description="Día final (incluido)."),
    pagina: int = Query(default=1, ge=1),
    por_pagina: int = Query(default=50, ge=1, le=200),
    ctx: Contexto = Depends(contexto_actual),
) -> PaginaAuditoria:
    """Renglones de la bitácora del despacho, del más reciente al más viejo."""
    exigir_rol(ctx, "dueno", "contador")
    if desde and hasta and desde > hasta:
        raise FiscalAgentError("`desde` no puede ser posterior a `hasta`.", status_code=422)
    filtros = [EventoAuditoria.despacho_id == ctx.despacho_id]
    if usuario:
        filtros.append(EventoAuditoria.uid == usuario)
    if cliente:
        filtros.append(EventoAuditoria.cliente_clave == cliente)
    if accion:
        if accion.endswith("*"):
            filtros.append(EventoAuditoria.accion.startswith(accion[:-1], autoescape=True))
        else:
            filtros.append(EventoAuditoria.accion == accion)
    if desde:
        filtros.append(EventoAuditoria.fecha >= _inicio_del_dia(desde))
    if hasta:
        filtros.append(EventoAuditoria.fecha < _inicio_del_dia(hasta + timedelta(days=1)))

    total = ctx.db.scalar(select(func.count()).select_from(EventoAuditoria).where(*filtros))
    eventos = ctx.db.scalars(
        select(EventoAuditoria)
        .where(*filtros)
        .order_by(EventoAuditoria.fecha.desc(), EventoAuditoria.id.desc())
        .offset((pagina - 1) * por_pagina)
        .limit(por_pagina)
    )
    return PaginaAuditoria(
        eventos=[
            EventoSalida(
                id=e.id,
                fecha=e.fecha,
                uid=e.uid,
                cliente=e.cliente_clave,
                accion=e.accion,
                entidad=e.entidad,
                entidad_id=e.entidad_id,
                detalle=e.detalle,
                ip=e.ip,
            )
            for e in eventos
        ],
        total=int(total or 0),
        pagina=pagina,
        por_pagina=por_pagina,
    )
