"""
Contabilidad por cliente (P2-01 a P2-04; reportes y cierre P2-05/08 en
`contabilidad_reportes.py`): `/api/v1/contabilidad/...`.

Todo lo de un cliente cuelga de `/contabilidad/clientes/{clave}/...`, pasa por
`contexto_actual` y obtiene al cliente con `cliente_o_404` (otro despacho = 404). Los ids de
cuenta, regla y póliza se buscan siempre junto con el cliente. Contrato en
`docs/api-contract.md` §Contabilidad.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.auditoria import registrar
from app.contabilidad import agrupador, balanza, catalogo, config, generador, polizas
from app.contabilidad import trabajos as trabajos_conta
from app.exceptions import FiscalAgentError
from app.tenancy import ROLES_CONTABLES, Contexto, cliente_o_404, contexto_actual, exigir_rol

router = APIRouter(prefix="/contabilidad", tags=["contabilidad"])

Naturaleza = Literal["deudora", "acreedora"]
TipoCuenta = Literal["activo", "pasivo", "capital", "ingreso", "costo", "gasto", "orden"]
TipoPoliza = Literal["ingreso", "egreso", "diario"]
# Hasta este número de días se genera en el request; más largo, en la cola.
MAX_DIAS_SINCRONO = 62
MAX_DIAS = 5 * 366


# ── agrupador (público para cualquier despacho) ──


@router.get("/codigo-agrupador")
def codigo_agrupador(ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    """El código agrupador del SAT completo, con su fuente."""
    return {"exito": True, "fuente": agrupador.FUENTE, "codigos": agrupador.como_lista()}


# ── P2-01: catálogo ──


class CuentaEntrada(BaseModel):
    numero: str = Field(..., min_length=1, max_length=40)
    nombre: str = Field(..., min_length=1, max_length=200)
    codigo_agrupador: str = Field(..., max_length=10)
    padre_id: int | None = None
    nivel: int | None = Field(None, ge=1, le=10)
    naturaleza: Naturaleza | None = None
    tipo: TipoCuenta | None = None


class CuentaCambio(BaseModel):
    numero: str | None = Field(None, min_length=1, max_length=40)
    nombre: str | None = Field(None, max_length=200)
    codigo_agrupador: str | None = Field(None, max_length=10)
    naturaleza: Naturaleza | None = None
    tipo: TipoCuenta | None = None


@router.get("/clientes/{clave}/cuentas")
def listar_cuentas(clave: str, ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    cliente = cliente_o_404(ctx, clave)
    return {"exito": True,
            "cuentas": [catalogo.como_dict(c) for c in catalogo.cuentas(ctx.db, cliente)]}


@router.post("/clientes/{clave}/cuentas/sembrar")
def sembrar(clave: str, ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    """Agrega el catálogo base (lo que falte). Idempotente."""
    cliente = cliente_o_404(ctx, clave)
    exigir_rol(ctx, *ROLES_CONTABLES)  # auxiliar: sólo lectura
    creadas = catalogo.sembrar_base(ctx.db, cliente)
    registrar(ctx, "contabilidad.sembrar_catalogo", "cliente", cliente.id, {"creadas": creadas},
              cliente)
    return {"exito": True, "creadas": creadas}


@router.post("/clientes/{clave}/cuentas", status_code=201)
def crear_cuenta(clave: str, entrada: CuentaEntrada,
                 ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    cliente = cliente_o_404(ctx, clave)
    exigir_rol(ctx, *ROLES_CONTABLES)  # auxiliar: sólo lectura
    cuenta = catalogo.crear(ctx.db, cliente, **entrada.model_dump())
    registrar(ctx, "contabilidad.crear_cuenta", "cuenta", cuenta.id, {"numero": cuenta.numero},
              cliente)
    return {"exito": True, "cuenta": catalogo.como_dict(cuenta)}


@router.patch("/clientes/{clave}/cuentas/{cuenta_id}")
def cambiar_cuenta(clave: str, cuenta_id: int, cambio: CuentaCambio,
                   ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    cliente = cliente_o_404(ctx, clave)
    exigir_rol(ctx, *ROLES_CONTABLES)  # auxiliar: sólo lectura
    cuenta = catalogo.actualizar(ctx.db, cliente, cuenta_id, **cambio.model_dump())
    return {"exito": True, "cuenta": catalogo.como_dict(cuenta)}


@router.delete("/clientes/{clave}/cuentas/{cuenta_id}")
def borrar_cuenta(clave: str, cuenta_id: int,
                  ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    cliente = cliente_o_404(ctx, clave)
    exigir_rol(ctx, *ROLES_CONTABLES)  # auxiliar: sólo lectura
    catalogo.borrar(ctx.db, cliente, cuenta_id)
    registrar(ctx, "contabilidad.borrar_cuenta", "cuenta", cuenta_id, None, cliente)
    return {"exito": True}


# ── P2-02: configuración ──


class ConfigEntrada(BaseModel):
    automatica_ingresos: bool | None = None
    automatica_egresos: bool | None = None
    automatica_pagos: bool | None = None
    automatica_nomina: bool | None = None
    pue_registra_cobro: bool | None = None
    uso_s01_no_deducible: bool | None = None
    efectivo_no_deducible: bool | None = None
    retenciones_al_pago: bool | None = None
    tope_activo: Decimal | None = Field(None, ge=0, max_digits=16, decimal_places=2)
    plantilla_concepto: str | None = Field(None, max_length=200)
    cuentas: dict[str, str] | None = None
    formas_pago: dict[str, str] | None = None
    fecha_saldos_iniciales: date | None = None


class ReglaEntrada(BaseModel):
    criterio: Literal["rfc", "clave", "prefijo", "uso", "descripcion"]
    valor: str = Field(..., min_length=1, max_length=200)
    cuenta_numero: str = Field(..., min_length=1, max_length=40)
    prioridad: int = Field(100, ge=0, le=100000)
    activa: bool = True


class ReglaCambio(BaseModel):
    criterio: Literal["rfc", "clave", "prefijo", "uso", "descripcion"] | None = None
    valor: str | None = Field(None, max_length=200)
    cuenta_numero: str | None = Field(None, max_length=40)
    prioridad: int | None = Field(None, ge=0, le=100000)
    activa: bool | None = None


@router.get("/clientes/{clave}/config")
def leer_config(clave: str, ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    cliente = cliente_o_404(ctx, clave)
    return {"exito": True, "config": config.como_dict(ctx.db, cliente)}


@router.put("/clientes/{clave}/config")
def guardar_config(clave: str, entrada: ConfigEntrada,
                   ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    cliente = cliente_o_404(ctx, clave)
    exigir_rol(ctx, *ROLES_CONTABLES)  # auxiliar: sólo lectura
    config.guardar(ctx.db, cliente, entrada.model_dump(exclude_unset=True))
    registrar(ctx, "contabilidad.config", "cliente", cliente.id, None, cliente)
    return {"exito": True, "config": config.como_dict(ctx.db, cliente)}


@router.post("/clientes/{clave}/reglas", status_code=201)
def crear_regla(clave: str, entrada: ReglaEntrada,
                ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    cliente = cliente_o_404(ctx, clave)
    exigir_rol(ctx, *ROLES_CONTABLES)  # auxiliar: sólo lectura
    regla = config.crear_regla(ctx.db, cliente, **entrada.model_dump())
    return {"exito": True, "regla": config.regla_dict(regla)}


@router.patch("/clientes/{clave}/reglas/{regla_id}")
def cambiar_regla(clave: str, regla_id: int, cambio: ReglaCambio,
                  ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    cliente = cliente_o_404(ctx, clave)
    exigir_rol(ctx, *ROLES_CONTABLES)  # auxiliar: sólo lectura
    regla = config.actualizar_regla(ctx.db, cliente, regla_id, cambio.model_dump())
    return {"exito": True, "regla": config.regla_dict(regla)}


@router.delete("/clientes/{clave}/reglas/{regla_id}")
def borrar_regla(clave: str, regla_id: int,
                 ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    cliente = cliente_o_404(ctx, clave)
    exigir_rol(ctx, *ROLES_CONTABLES)  # auxiliar: sólo lectura
    ctx.db.delete(config.regla_o_404(ctx.db, cliente, regla_id))
    return {"exito": True}


# ── P2-03: pólizas ──


class Rango(BaseModel):
    desde: date
    hasta: date
    segundo_plano: bool | None = None


class MovimientoEntrada(BaseModel):
    cuenta_id: int
    cargo: Decimal = Field(Decimal("0"), ge=0, max_digits=18, decimal_places=2)
    abono: Decimal = Field(Decimal("0"), ge=0, max_digits=18, decimal_places=2)
    concepto: str = Field("", max_length=300)
    uuid: str = Field("", max_length=36)
    rfc: str = Field("", max_length=13)


class PolizaEntrada(BaseModel):
    tipo: TipoPoliza
    fecha: date
    concepto: str = Field("", max_length=500)
    movimientos: list[MovimientoEntrada] = Field(..., min_length=2, max_length=500)


class PolizaCambio(BaseModel):
    fecha: date | None = None
    concepto: str | None = Field(None, max_length=500)
    movimientos: list[MovimientoEntrada] | None = Field(None, min_length=2, max_length=500)


class Cancelacion(BaseModel):
    motivo: str = Field("", max_length=300)


def _movs(lista: list[MovimientoEntrada] | None) -> list[polizas.MovimientoEntrada] | None:
    if lista is None:
        return None
    return [polizas.MovimientoEntrada(**m.model_dump()) for m in lista]


@router.post("/clientes/{clave}/polizas/generar")
def generar_polizas(clave: str, rango: Rango,
                    ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    """
    Genera las pólizas automáticas del rango desde la bóveda. Rango corto: en el request;
    largo (o `segundo_plano: true`): encola un trabajo.
    """
    cliente = cliente_o_404(ctx, clave)
    if rango.desde > rango.hasta:
        raise FiscalAgentError("'desde' no puede ser posterior a 'hasta'.", 422)
    dias = (rango.hasta - rango.desde).days
    if dias > MAX_DIAS:
        raise FiscalAgentError("El rango máximo es de cinco años.", 422)
    fondo = rango.segundo_plano if rango.segundo_plano is not None else dias > MAX_DIAS_SINCRONO
    if fondo:
        t = trabajos_conta.encolar_generacion(ctx.db, cliente, rango.desde, rango.hasta, ctx.uid)
        registrar(ctx, "contabilidad.generar_polizas", "trabajo", t.id,
                  {"desde": rango.desde.isoformat(), "hasta": rango.hasta.isoformat()}, cliente)
        return {"exito": True, "en_segundo_plano": True,
                "trabajo": {"id": t.id, "tipo": t.tipo, "estado": t.estado}}
    r = generador.generar(ctx.db, cliente, rango.desde, rango.hasta, ctx.uid)
    registrar(ctx, "contabilidad.generar_polizas", "cliente", cliente.id,
              {"desde": rango.desde.isoformat(), "hasta": rango.hasta.isoformat(),
               "generadas": r.generadas}, cliente)
    return {"exito": True, "en_segundo_plano": False, "resultado": r.como_dict()}


@router.get("/clientes/{clave}/polizas")
def listar_polizas(
    clave: str,
    desde: date | None = Query(None), hasta: date | None = Query(None),
    tipo: TipoPoliza | None = Query(None),
    origen: Literal["automatica", "manual"] | None = Query(None),
    estado: Literal["activa", "cancelada"] | None = Query(None),
    uuid: str | None = Query(None, max_length=36), texto: str | None = Query(None, max_length=100),
    pagina: int = Query(1, ge=1), por_pagina: int = Query(50, ge=1, le=200),
    ctx: Contexto = Depends(contexto_actual),
) -> dict[str, Any]:
    cliente = cliente_o_404(ctx, clave)
    filtros = polizas.FiltrosPolizas(desde, hasta, tipo, origen, estado, uuid, texto)
    filas, total = polizas.listar(ctx.db, cliente, filtros, pagina, por_pagina)
    return {"exito": True, "total": total, "pagina": pagina, "por_pagina": por_pagina,
            "polizas": [polizas.como_dict(ctx.db, p) for p in filas]}


@router.get("/clientes/{clave}/polizas/{poliza_id}")
def detalle_poliza(clave: str, poliza_id: int,
                   ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    cliente = cliente_o_404(ctx, clave)
    p = polizas.obtener(ctx.db, cliente, poliza_id)
    return {"exito": True, "poliza": polizas.como_dict(ctx.db, p, detalle=True)}


@router.post("/clientes/{clave}/polizas", status_code=201)
def crear_poliza(clave: str, entrada: PolizaEntrada,
                 ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    cliente = cliente_o_404(ctx, clave)
    exigir_rol(ctx, *ROLES_CONTABLES)  # auxiliar: sólo lectura
    p = polizas.crear_manual(ctx.db, cliente, tipo=entrada.tipo, fecha=entrada.fecha,
                             concepto=entrada.concepto, movimientos=_movs(entrada.movimientos)
                             or [], uid=ctx.uid)
    registrar(ctx, "contabilidad.crear_poliza", "poliza", p.id, {"folio": polizas.folio(p)},
              cliente)
    return {"exito": True, "poliza": polizas.como_dict(ctx.db, p, detalle=True)}


@router.patch("/clientes/{clave}/polizas/{poliza_id}")
def editar_poliza(clave: str, poliza_id: int, cambio: PolizaCambio,
                  ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    cliente = cliente_o_404(ctx, clave)
    exigir_rol(ctx, *ROLES_CONTABLES)  # auxiliar: sólo lectura
    p = polizas.editar(ctx.db, cliente, poliza_id, fecha=cambio.fecha, concepto=cambio.concepto,
                       movimientos=_movs(cambio.movimientos))
    registrar(ctx, "contabilidad.editar_poliza", "poliza", p.id, {"folio": polizas.folio(p)},
              cliente)
    return {"exito": True, "poliza": polizas.como_dict(ctx.db, p, detalle=True)}


@router.post("/clientes/{clave}/polizas/{poliza_id}/cancelar")
def cancelar_poliza(clave: str, poliza_id: int, entrada: Cancelacion,
                    ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    cliente = cliente_o_404(ctx, clave)
    exigir_rol(ctx, *ROLES_CONTABLES)  # auxiliar: sólo lectura
    p = polizas.cancelar(ctx.db, cliente, poliza_id, entrada.motivo)
    registrar(ctx, "contabilidad.cancelar_poliza", "poliza", p.id, {"folio": polizas.folio(p)},
              cliente)
    return {"exito": True, "poliza": polizas.como_dict(ctx.db, p)}


# ── periodos ──


@router.get("/clientes/{clave}/periodos-cerrados")
def periodos(clave: str, ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    """Los meses cerrados. Cerrar y reabrir: `contabilidad_reportes.py` (P2-08)."""
    cliente = cliente_o_404(ctx, clave)
    return {"exito": True, "periodos": polizas.periodos_cerrados(ctx.db, cliente)}


# ── P2-04: balanza, auxiliar y saldos iniciales ──


@router.get("/clientes/{clave}/balanza")
def ver_balanza(
    clave: str, desde: date = Query(...), hasta: date = Query(...),
    nivel: int | None = Query(None, ge=1, le=10),
    solo: Literal["con_movimiento", "con_saldo_o_movimiento", "todas"] = Query(
        "con_saldo_o_movimiento"),
    incluir_cierre: bool = Query(False),
    ctx: Contexto = Depends(contexto_actual),
) -> dict[str, Any]:
    cliente = cliente_o_404(ctx, clave)
    return {"exito": True, **balanza.balanza(ctx.db, cliente, desde, hasta, nivel=nivel,
                                              solo=solo, incluir_cierre=incluir_cierre)}


@router.get("/clientes/{clave}/cuentas/{cuenta_id}/auxiliar")
def ver_auxiliar(clave: str, cuenta_id: int, desde: date = Query(...),
                 hasta: date = Query(...), incluir_cierre: bool = Query(False),
                 ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    cliente = cliente_o_404(ctx, clave)
    return {"exito": True, **balanza.auxiliar(ctx.db, cliente, cuenta_id, desde, hasta,
                                              incluir_cierre=incluir_cierre)}


class SaldoEntrada(BaseModel):
    cuenta_id: int
    deudor: Decimal = Field(Decimal("0"), ge=0, max_digits=18, decimal_places=2)
    acreedor: Decimal = Field(Decimal("0"), ge=0, max_digits=18, decimal_places=2)


class SaldosEntrada(BaseModel):
    saldos: list[SaldoEntrada] = Field(..., max_length=5000)


@router.get("/clientes/{clave}/saldos-iniciales")
def leer_saldos(clave: str, ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    cliente = cliente_o_404(ctx, clave)
    return {"exito": True, "saldos": balanza.saldos_iniciales(ctx.db, cliente)}


@router.put("/clientes/{clave}/saldos-iniciales")
def guardar_saldos(clave: str, entrada: SaldosEntrada,
                   ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    cliente = cliente_o_404(ctx, clave)
    exigir_rol(ctx, *ROLES_CONTABLES)  # auxiliar: sólo lectura
    totales = balanza.guardar_saldos_iniciales(
        ctx.db, cliente, [(s.cuenta_id, s.deudor, s.acreedor) for s in entrada.saldos])
    registrar(ctx, "contabilidad.saldos_iniciales", "cliente", cliente.id,
              {"cuentas": len(entrada.saldos)}, cliente)
    return {"exito": True, "totales": totales,
            "saldos": balanza.saldos_iniciales(ctx.db, cliente)}
