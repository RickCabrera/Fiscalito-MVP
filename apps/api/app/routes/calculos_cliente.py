"""
Cálculos fiscales de un cliente leyendo su bóveda (plan P, P1-06).

`POST /api/v1/clientes/{clave}/calculos/<calculo>` recibe SÓLO el periodo (y los datos que
no salen de un CFDI, como el ISR pagado en meses anteriores o el predial), toma el RFC y el
régimen de la ficha del cliente y los CFDI vigentes del periodo de su bóveda
(`app/boveda_cfdi/calculo.py`), arma el request de siempre y **llama al mismo handler** que
los endpoints con `facturas` en el body. No hay motor nuevo ni copia del motor: si el cálculo
cambia, cambia para las dos puertas.

La respuesta es la del endpoint original más `boveda` (el resumen de lo que se usó:
cuántos CFDI, emitidos/recibidos, cancelados y nómina que se dejaron fuera).
"""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, ValidationError

from app.boveda_cfdi import calculo
from app.boveda_cfdi.servicio import rfc_del_cliente
from app.constants import NOMBRES_BIMESTRES, NOMBRES_MESES
from app.exceptions import FiscalAgentError
from app.modelos.nucleo import Cliente
from app.routes import declaraciones, diot, estado_cuenta, multi_periodo, retenciones
from app.schemas.declaraciones import PreDeclaracionRequest
from app.schemas.diot import DIOTRequest
from app.schemas.estado_cuenta import EstadoCuentaRequest
from app.schemas.fiscal import PerfilContribuyente
from app.schemas.multi_periodo import MultiPeriodoRequest
from app.schemas.retenciones import RetencionesRequest
from app.tenancy import Contexto, cliente_o_404, contexto_actual

router = APIRouter(prefix="/clientes/{clave}/calculos", tags=["calculos-cliente"])


# ── cuerpos: el request original sin `contribuyente` ni `facturas` ──


class _ConExplicacion(BaseModel):
    periodo_year: int = Field(..., ge=2000, le=2100)
    incluir_explicacion: bool = True


class PreDeclaracionCliente(_ConExplicacion):
    periodo_month: int | None = Field(None, ge=1, le=12)
    periodo_bimestre: int | None = Field(None, ge=1, le=6)
    pagos_provisionales_anteriores: float = Field(0.0, ge=0)
    ingresos_acumulados_anteriores: float = 0.0
    deducciones_acumuladas_anteriores: float = 0.0
    predial_pagado: float = Field(0.0, ge=0)


class DIOTCliente(_ConExplicacion):
    periodo_month: int = Field(..., ge=1, le=12)


class RetencionesCliente(_ConExplicacion):
    periodo_month: int | None = Field(None, ge=1, le=12)
    periodo_bimestre: int | None = Field(None, ge=1, le=6)


class MultiPeriodoCliente(_ConExplicacion):
    periodos: list[int] = Field(..., min_length=1)


# ── comunes ──


def perfil_del_cliente(cliente: Cliente) -> PerfilContribuyente:
    """RFC y régimen de la ficha del cliente. 422 con el dato que falta."""
    rfc = rfc_del_cliente(cliente)
    regimen = str((cliente.datos or {}).get("regimen") or "").strip()
    if not rfc:
        raise FiscalAgentError("Captura el RFC de este cliente.", 422)
    if not regimen:
        raise FiscalAgentError("Captura el régimen de este cliente.", 422)
    try:
        return PerfilContribuyente(rfc=rfc, regimen=regimen, nombre=cliente.nombre)
    except ValidationError as e:
        raise FiscalAgentError(f"El RFC del cliente no es válido: {rfc}.", 422) from e


def _de_la_boveda(
    ctx: Contexto, clave: str, desde: date, hasta: date, etiqueta: str
) -> tuple[PerfilContribuyente, calculo.FacturasCalculo]:
    cliente = cliente_o_404(ctx, clave)
    perfil = perfil_del_cliente(cliente)
    r = calculo.facturas_para_calculo(ctx.db, cliente, desde, hasta)
    if not r.facturas:
        raise FiscalAgentError(
            f"La bóveda de este cliente no tiene CFDI vigentes de {etiqueta}. "
            "Cárgalos en la Bóveda o con la descarga del SAT.", 400,
        )
    return perfil, r


def _sin_motor_primero(ctx: Contexto, clave: str) -> None:
    """Igual que el endpoint original: un 601 se entera de que no hay motor antes que nada."""
    cliente = cliente_o_404(ctx, clave)
    declaraciones._rechazar_si_no_hay_motor(str((cliente.datos or {}).get("regimen") or ""))


def _con_boveda(respuesta: BaseModel, r: calculo.FacturasCalculo) -> dict[str, Any]:
    return {**respuesta.model_dump(mode="json"),
            "boveda": {**r.resumen, "advertencias": r.advertencias}}


def _rango_y_etiqueta(anio: int, mes: int | None, bimestre: int | None) -> tuple[date, date, str]:
    desde, hasta = calculo.rango_del_periodo(anio, mes, bimestre)
    if bimestre is not None:
        return desde, hasta, f"{NOMBRES_BIMESTRES[bimestre]} {anio}"
    if mes is not None:
        return desde, hasta, f"{NOMBRES_MESES[mes]} {anio}"
    return desde, hasta, f"el ejercicio {anio}"


# ── rutas ──


@router.post("/pre-declaracion")
async def pre_declaracion(
    clave: str, cuerpo: PreDeclaracionCliente, ctx: Contexto = Depends(contexto_actual)
) -> dict[str, Any]:
    """Pre-declaración mensual o bimestral con los CFDI del periodo en la bóveda."""
    if cuerpo.periodo_month is None and cuerpo.periodo_bimestre is None:
        raise FiscalAgentError("Indica periodo_month o periodo_bimestre.", 422)
    desde, hasta, etiqueta = _rango_y_etiqueta(
        cuerpo.periodo_year, cuerpo.periodo_month, cuerpo.periodo_bimestre)
    _sin_motor_primero(ctx, clave)
    perfil, r = _de_la_boveda(ctx, clave, desde, hasta, etiqueta)
    req = PreDeclaracionRequest(contribuyente=perfil, facturas=r.todas(), **cuerpo.model_dump())
    return _con_boveda(await declaraciones.pre_declaracion(req), r)


@router.post("/pre-declaracion-anual")
async def pre_declaracion_anual(
    clave: str, cuerpo: _ConExplicacion, ctx: Contexto = Depends(contexto_actual)
) -> dict[str, Any]:
    """Pre-declaración anual con los CFDI del ejercicio en la bóveda."""
    desde, hasta, etiqueta = _rango_y_etiqueta(cuerpo.periodo_year, None, None)
    _sin_motor_primero(ctx, clave)
    perfil, r = _de_la_boveda(ctx, clave, desde, hasta, etiqueta)
    req = PreDeclaracionRequest(contribuyente=perfil, facturas=r.todas(), **cuerpo.model_dump())
    return _con_boveda(await declaraciones.pre_declaracion_anual(req), r)


@router.post("/diot")
async def diot_cliente(
    clave: str, cuerpo: DIOTCliente, ctx: Contexto = Depends(contexto_actual)
) -> dict[str, Any]:
    """DIOT del mes. Sólo los CFDI del periodo: el motor de DIOT no distingue PPD."""
    desde, hasta, etiqueta = _rango_y_etiqueta(cuerpo.periodo_year, cuerpo.periodo_month, None)
    perfil, r = _de_la_boveda(ctx, clave, desde, hasta, etiqueta)
    req = DIOTRequest(contribuyente=perfil, facturas=r.facturas, **cuerpo.model_dump())
    return _con_boveda(await diot.diot(req), r)


@router.post("/retenciones-terceros")
async def retenciones_cliente(
    clave: str, cuerpo: RetencionesCliente, ctx: Contexto = Depends(contexto_actual)
) -> dict[str, Any]:
    """Retenciones a terceros del mes, bimestre o ejercicio."""
    desde, hasta, etiqueta = _rango_y_etiqueta(
        cuerpo.periodo_year, cuerpo.periodo_month, cuerpo.periodo_bimestre)
    perfil, r = _de_la_boveda(ctx, clave, desde, hasta, etiqueta)
    req = RetencionesRequest(contribuyente=perfil, facturas=r.facturas, **cuerpo.model_dump())
    return _con_boveda(await retenciones.retenciones_terceros(req), r)


@router.post("/multi-periodo")
async def multi_periodo_cliente(
    clave: str, cuerpo: MultiPeriodoCliente, ctx: Contexto = Depends(contexto_actual)
) -> dict[str, Any]:
    """Varios meses del ejercicio con los CFDI del año en la bóveda."""
    if any(p < 1 or p > 12 for p in cuerpo.periodos):
        raise FiscalAgentError("Los periodos son meses del 1 al 12.", 422)
    desde, hasta, etiqueta = _rango_y_etiqueta(cuerpo.periodo_year, None, None)
    perfil, r = _de_la_boveda(ctx, clave, desde, hasta, etiqueta)
    req = MultiPeriodoRequest(contribuyente=perfil, facturas=r.todas(), **cuerpo.model_dump())
    return _con_boveda(await multi_periodo.multi_periodo(req), r)


@router.post("/estado-cuenta")
async def estado_cuenta_cliente(
    clave: str, cuerpo: _ConExplicacion, ctx: Contexto = Depends(contexto_actual)
) -> dict[str, Any]:
    """Estado de cuenta fiscal del ejercicio con los CFDI del año en la bóveda."""
    desde, hasta, etiqueta = _rango_y_etiqueta(cuerpo.periodo_year, None, None)
    perfil, r = _de_la_boveda(ctx, clave, desde, hasta, etiqueta)
    req = EstadoCuentaRequest(contribuyente=perfil, facturas=r.todas(), **cuerpo.model_dump())
    return _con_boveda(await estado_cuenta.estado_cuenta(req), r)
