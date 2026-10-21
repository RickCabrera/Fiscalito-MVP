"""
Descarga masiva del SAT por cliente (P1-01, P1-02): `/api/v1/sat/clientes/{clave}/...`.

Todas pasan por `contexto_actual` + `cliente_o_404` (cliente de otro despacho = 404). Leer lo
puede cualquier rol que vea al cliente; escribir (config, descargar, histórica) sólo `dueno`
y `contador`. Contrato en `docs/api-contract.md`, sección "Descarga masiva del SAT".
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select

from app.auditoria import registrar
from app.exceptions import FiscalAgentError
from app.modelos.sat_descarga import SolicitudDescargaSat
from app.sat_descarga import servicio, sincronizacion
from app.tenancy import Contexto, cliente_o_404, contexto_actual, exigir_rol

router = APIRouter(prefix="/sat/clientes/{clave}", tags=["sat"])

ROLES_ESCRITURA = ("dueno", "contador")
MAX_MESES_HISTORICA = 72  # el SAT sólo guarda seis años
MAX_DIAS_RANGO = 366


class ConfigEntrada(BaseModel):
    activa: bool | None = None
    emitidos: bool | None = None
    recibidos: bool | None = None
    metadata: bool | None = None
    cancelados: bool | None = None
    desde: date | None = None
    hora: str | None = Field(default=None, description="HH:MM, hora de la Ciudad de México")

    @field_validator("hora")
    @classmethod
    def _hora(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", v):
            raise ValueError("La hora va como HH:MM (00:00 a 23:59).")
        return v


class Seleccion(BaseModel):
    emitidos: bool = True
    recibidos: bool = True
    metadata: bool = True
    cancelados: bool = True


class RangoEntrada(BaseModel):
    desde: date
    hasta: date
    seleccion: Seleccion | None = None


class HistoricaEntrada(BaseModel):
    desde: date
    hasta: date | None = None
    seleccion: Seleccion | None = None


def _config_salida(ctx: Contexto, cliente: Any) -> dict[str, Any]:
    cfg = sincronizacion.config_de(ctx.db, cliente)
    return {
        "activa": cfg.activa, "emitidos": cfg.emitidos, "recibidos": cfg.recibidos,
        "metadata": cfg.metadata_, "cancelados": cfg.cancelados,
        "desde": cfg.desde.isoformat() if cfg.desde else None, "hora": cfg.hora,
        "pausada_por": cfg.pausada_por or None,
        "ultimo_dia_encolado": (cfg.ultimo_dia_encolado.isoformat()
                                if cfg.ultimo_dia_encolado else None),
    }


def _seleccion(ctx: Contexto, cliente: Any, s: Seleccion | None) -> sincronizacion.Seleccion:
    if s is not None:
        return sincronizacion.Seleccion(**s.model_dump())
    return sincronizacion.Seleccion.de_config(sincronizacion.config_de(ctx.db, cliente))


def _exigir_efirma(ctx: Contexto, cliente: Any) -> None:
    estado = sincronizacion.estado_efirma(ctx.db, cliente)
    if not estado["vigente"]:
        raise FiscalAgentError(estado["mensaje"], status_code=409)


@router.get("/config")
def leer_config(clave: str, ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    """Configuración de la descarga del cliente, estado de su e.firma y alertas abiertas."""
    cliente = cliente_o_404(ctx, clave)
    return {
        "exito": True, "config": _config_salida(ctx, cliente),
        "efirma": sincronizacion.estado_efirma(ctx.db, cliente),
        "alertas": sincronizacion.alertas_abiertas(ctx.db, cliente),
    }


@router.put("/config")
def guardar_config(
    clave: str, entrada: ConfigEntrada, ctx: Contexto = Depends(contexto_actual)
) -> dict[str, Any]:
    """Cambia la configuración. Activarla sin e.firma vigente la deja en pausa con alerta."""
    exigir_rol(ctx, *ROLES_ESCRITURA)
    cliente = cliente_o_404(ctx, clave)
    sincronizacion.guardar_config(ctx.db, cliente, entrada.model_dump())
    registrar(ctx, "sat.config", "cliente", cliente.clave, entrada.model_dump(mode="json"),
              cliente)
    return {
        "exito": True, "config": _config_salida(ctx, cliente),
        "efirma": sincronizacion.estado_efirma(ctx.db, cliente),
        "alertas": sincronizacion.alertas_abiertas(ctx.db, cliente),
    }


@router.post("/descargar")
def descargar_rango(
    clave: str, entrada: RangoEntrada, ctx: Contexto = Depends(contexto_actual)
) -> dict[str, Any]:
    """"Descargar ahora": encola el rango (partido por mes). Requiere e.firma vigente."""
    exigir_rol(ctx, *ROLES_ESCRITURA)
    cliente = cliente_o_404(ctx, clave)
    if entrada.desde > entrada.hasta:
        raise FiscalAgentError("'desde' no puede ser posterior a 'hasta'.", 422)
    if (entrada.hasta - entrada.desde).days >= MAX_DIAS_RANGO:
        raise FiscalAgentError("Para más de un año usa la descarga histórica.", 422)
    if entrada.hasta > date.today():
        raise FiscalAgentError("No se puede pedir al SAT un día que no ha pasado.", 422)
    _exigir_efirma(ctx, cliente)
    sel = _seleccion(ctx, cliente, entrada.seleccion)
    encolados = sincronizacion.encolar_meses(ctx.db, cliente, entrada.desde, entrada.hasta,
                                             sel, "manual")
    registrar(ctx, "sat.descargar", "cliente", cliente.clave,
              {"desde": entrada.desde.isoformat(), "hasta": entrada.hasta.isoformat()}, cliente)
    return {"exito": True, "encolados": encolados}


@router.post("/historica")
def descarga_historica(
    clave: str, entrada: HistoricaEntrada, ctx: Contexto = Depends(contexto_actual)
) -> dict[str, Any]:
    """Descarga histórica: un trabajo por mes desde `desde` hasta `hasta` (default: ayer)."""
    exigir_rol(ctx, *ROLES_ESCRITURA)
    cliente = cliente_o_404(ctx, clave)
    hasta = entrada.hasta or date.fromordinal(date.today().toordinal() - 1)
    if entrada.desde > hasta:
        raise FiscalAgentError("'desde' no puede ser posterior a 'hasta'.", 422)
    meses = (hasta.year - entrada.desde.year) * 12 + hasta.month - entrada.desde.month + 1
    if meses > MAX_MESES_HISTORICA:
        raise FiscalAgentError("El SAT sólo guarda seis años: pide a lo más 72 meses.", 422)
    _exigir_efirma(ctx, cliente)
    sel = _seleccion(ctx, cliente, entrada.seleccion)
    encolados = sincronizacion.encolar_meses(ctx.db, cliente, entrada.desde, hasta, sel,
                                             "historica")
    registrar(ctx, "sat.historica", "cliente", cliente.clave,
              {"desde": entrada.desde.isoformat(), "hasta": hasta.isoformat(),
               "meses": len(encolados)}, cliente)
    return {"exito": True, "encolados": encolados}


@router.get("/solicitudes")
def listar_solicitudes(
    clave: str,
    estado: str | None = Query(None),
    pagina: int = Query(1, ge=1),
    por_pagina: int = Query(20, ge=1, le=100),
    ctx: Contexto = Depends(contexto_actual),
) -> dict[str, Any]:
    """Solicitudes del cliente, más recientes primero."""
    cliente = cliente_o_404(ctx, clave)
    cond = [SolicitudDescargaSat.cliente_id == cliente.id]
    if estado:
        cond.append(SolicitudDescargaSat.estado == estado)
    total = ctx.db.scalar(select(func.count(SolicitudDescargaSat.id)).where(*cond)) or 0
    filas = ctx.db.scalars(
        select(SolicitudDescargaSat).where(*cond)
        .order_by(SolicitudDescargaSat.id.desc())
        .offset((pagina - 1) * por_pagina).limit(por_pagina)
    )
    return {"exito": True, "total": int(total), "pagina": pagina, "por_pagina": por_pagina,
            "solicitudes": [servicio.como_dict(s) for s in filas]}


@router.get("/bitacora")
def bitacora(
    clave: str,
    anio: int = Query(..., ge=2000, le=2100),
    mes: int = Query(..., ge=1, le=12),
    ctx: Contexto = Depends(contexto_actual),
) -> dict[str, Any]:
    """Estado de cada día del mes para el calendario, con conteos."""
    cliente = cliente_o_404(ctx, clave)
    dias = sincronizacion.bitacora(ctx.db, cliente, anio, mes)
    return {"exito": True, "anio": anio, "mes": mes, "dias": dias}
