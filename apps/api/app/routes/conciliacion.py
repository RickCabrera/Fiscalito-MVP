"""
Conciliación bancaria (P2-06): `/api/v1/conciliacion/clientes/{clave}/...`.

Todo pasa por `contexto_actual` + `cliente_o_404` (otro despacho = 404) y cada id (cuenta
bancaria, plantilla, movimiento, conciliación) se busca junto con el cliente. Contrato en
`docs/api-contract.md` §Conciliación bancaria.
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from typing import Any, Literal

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.auditoria import registrar
from app.contabilidad.conciliacion import lectores, reporte, servicio
from app.exceptions import FiscalAgentError
from app.tenancy import ROLES_CONTABLES, Contexto, cliente_o_404, contexto_actual, exigir_rol

router = APIRouter(prefix="/conciliacion", tags=["conciliacion"])


class CuentaBancariaEntrada(BaseModel):
    banco: str = Field(..., pattern=r"^\d{3}$")
    nombre: str = Field("", max_length=120)
    numero: str = Field("", max_length=30)
    clabe: str = Field("", pattern=r"^(\d{18})?$")
    moneda: str = Field("MXN", pattern=r"^[A-Z]{3}$")
    cuenta_contable_id: int
    ventana_dias: int = Field(3, ge=0, le=31)
    umbral: int = Field(60, ge=50, le=100)
    activa: bool = True


class CuentaBancariaCambio(BaseModel):
    banco: str | None = Field(None, pattern=r"^\d{3}$")
    nombre: str | None = Field(None, max_length=120)
    numero: str | None = Field(None, max_length=30)
    clabe: str | None = Field(None, pattern=r"^(\d{18})?$")
    cuenta_contable_id: int | None = None
    ventana_dias: int | None = Field(None, ge=0, le=31)
    umbral: int | None = Field(None, ge=50, le=100)
    activa: bool | None = None


class PlantillaEntrada(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=80)
    banco: str = Field("", max_length=3)
    formato: Literal["csv", "xlsx"] = "csv"
    mapeo: dict[str, Any]


class Rango(BaseModel):
    desde: date | None = None
    hasta: date | None = None
    incluir_cfdi: bool = True


class ConciliacionManual(BaseModel):
    banco: list[str] = Field(..., min_length=1, max_length=200)
    libros: list[str] = Field(..., min_length=1, max_length=200)
    motivo: str = Field("", max_length=300)


class Contrapartida(BaseModel):
    cuenta_id: int
    importe: Decimal = Field(..., gt=0, max_digits=18, decimal_places=2)


class PolizaDesdeBanco(BaseModel):
    contrapartidas: list[Contrapartida] = Field(..., min_length=1, max_length=20)
    concepto: str = Field("", max_length=300)


# ── cuentas bancarias ──


@router.get("/bancos")
def bancos(ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    """Bancos con lector de PDF (diseños POR CONFIRMAR CON PDF REAL)."""
    return {"exito": True, "bancos": servicio.bancos_sat()}


@router.get("/clientes/{clave}/cuentas")
def listar_cuentas(clave: str, ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    cliente = cliente_o_404(ctx, clave)
    return {"exito": True, "cuentas": [servicio.cuenta_dict(ctx.db, c)
                                       for c in servicio.cuentas(ctx.db, cliente)]}


@router.post("/clientes/{clave}/cuentas", status_code=201)
def crear_cuenta(clave: str, entrada: CuentaBancariaEntrada,
                 ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    cliente = cliente_o_404(ctx, clave)
    exigir_rol(ctx, *ROLES_CONTABLES)  # auxiliar: sólo lectura
    cb = servicio.crear_cuenta(ctx.db, cliente, entrada.model_dump())
    registrar(ctx, "conciliacion.crear_cuenta", "cuenta_bancaria", cb.id, None, cliente)
    return {"exito": True, "cuenta": servicio.cuenta_dict(ctx.db, cb)}


@router.patch("/clientes/{clave}/cuentas/{cuenta_id}")
def cambiar_cuenta(clave: str, cuenta_id: int, cambio: CuentaBancariaCambio,
                   ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    cliente = cliente_o_404(ctx, clave)
    exigir_rol(ctx, *ROLES_CONTABLES)  # auxiliar: sólo lectura
    cb = servicio.actualizar_cuenta(ctx.db, cliente, cuenta_id, cambio.model_dump())
    return {"exito": True, "cuenta": servicio.cuenta_dict(ctx.db, cb)}


@router.delete("/clientes/{clave}/cuentas/{cuenta_id}")
def borrar_cuenta(clave: str, cuenta_id: int,
                  ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    cliente = cliente_o_404(ctx, clave)
    exigir_rol(ctx, *ROLES_CONTABLES)  # auxiliar: sólo lectura
    servicio.borrar_cuenta(ctx.db, cliente, cuenta_id)
    registrar(ctx, "conciliacion.borrar_cuenta", "cuenta_bancaria", cuenta_id, None, cliente)
    return {"exito": True}


# ── plantillas ──


@router.get("/clientes/{clave}/plantillas")
def listar_plantillas(clave: str, ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    cliente = cliente_o_404(ctx, clave)
    return {"exito": True, "plantillas": [servicio.plantilla_dict(p)
                                          for p in servicio.plantillas(ctx.db, cliente)]}


@router.put("/clientes/{clave}/plantillas")
def guardar_plantilla(clave: str, entrada: PlantillaEntrada,
                      ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    """Crea o reemplaza (por nombre) una plantilla de columnas."""
    cliente = cliente_o_404(ctx, clave)
    exigir_rol(ctx, *ROLES_CONTABLES)  # auxiliar: sólo lectura
    p = servicio.guardar_plantilla(ctx.db, cliente, entrada.nombre, entrada.banco,
                                   entrada.formato, entrada.mapeo)
    return {"exito": True, "plantilla": servicio.plantilla_dict(p)}


@router.delete("/clientes/{clave}/plantillas/{plantilla_id}")
def borrar_plantilla(clave: str, plantilla_id: int,
                     ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    cliente = cliente_o_404(ctx, clave)
    exigir_rol(ctx, *ROLES_CONTABLES)  # auxiliar: sólo lectura
    ctx.db.delete(servicio.plantilla_o_404(ctx.db, cliente, plantilla_id))
    return {"exito": True}


# ── importar ──


@router.post("/clientes/{clave}/cuentas/{cuenta_id}/estados")
async def importar_estado(
    clave: str, cuenta_id: int,
    archivo: UploadFile = File(...),
    formato: Literal["csv", "xlsx", "ofx", "pdf"] | None = Form(None),
    plantilla_id: int | None = Form(None),
    mapeo: str | None = Form(None, description="JSON con el mapeo de columnas"),
    ctx: Contexto = Depends(contexto_actual),
) -> dict[str, Any]:
    """Importa un estado de cuenta (CSV, XLSX, OFX o PDF). No duplica renglones ya importados."""
    cliente = cliente_o_404(ctx, clave)
    cb = servicio.cuenta_o_404(ctx.db, cliente, cuenta_id)
    datos = await archivo.read(lectores.MAX_BYTES + 1)
    mapa: dict[str, Any] | None = None
    if plantilla_id is not None:
        mapa = dict(servicio.plantilla_o_404(ctx.db, cliente, plantilla_id).mapeo or {})
    if mapeo:
        try:
            extra = json.loads(mapeo)
        except json.JSONDecodeError as e:
            raise FiscalAgentError("El mapeo no es JSON válido.", 422) from e
        if not isinstance(extra, dict):
            raise FiscalAgentError("El mapeo debe ser un objeto.", 422)
        mapa = {**(mapa or {}), **extra}
    imp = servicio.importar(ctx.db, cliente, cb, nombre=archivo.filename or "estado",
                            datos=datos, formato=formato, mapeo=mapa, uid=ctx.uid)
    registrar(ctx, "conciliacion.importar", "estado_cuenta", imp.estado.id,
              {"nuevos": imp.estado.nuevos, "formato": imp.estado.formato}, cliente)
    return {"exito": True, "estado": servicio.estado_dict(imp.estado),
            "banco_pdf": imp.banco_pdf}


@router.get("/clientes/{clave}/cuentas/{cuenta_id}/estados")
def listar_estados(clave: str, cuenta_id: int,
                   ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    cliente = cliente_o_404(ctx, clave)
    cb = servicio.cuenta_o_404(ctx.db, cliente, cuenta_id)
    return {"exito": True, "estados": [servicio.estado_dict(e)
                                       for e in servicio.estados(ctx.db, cb)]}


# ── conciliar ──


def _rango(desde: date | None, hasta: date | None) -> None:
    if desde and hasta and desde > hasta:
        raise FiscalAgentError("'desde' no puede ser posterior a 'hasta'.", 422)


@router.get("/clientes/{clave}/cuentas/{cuenta_id}/movimientos")
def ver_movimientos(clave: str, cuenta_id: int, desde: date | None = Query(None),
                    hasta: date | None = Query(None), incluir_cfdi: bool = Query(True),
                    ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    """Las dos tablas: estado de cuenta y movimientos de libros, con su marca."""
    _rango(desde, hasta)
    cliente = cliente_o_404(ctx, clave)
    cb = servicio.cuenta_o_404(ctx.db, cliente, cuenta_id)
    return {"exito": True, **servicio.vista(ctx.db, cliente, cb, desde, hasta, incluir_cfdi)}


@router.post("/clientes/{clave}/cuentas/{cuenta_id}/conciliar")
def conciliar(clave: str, cuenta_id: int, rango: Rango,
              ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    """Emparejamiento automático de lo pendiente en el rango."""
    _rango(rango.desde, rango.hasta)
    cliente = cliente_o_404(ctx, clave)
    exigir_rol(ctx, *ROLES_CONTABLES)  # auxiliar: sólo lectura
    cb = servicio.cuenta_o_404(ctx.db, cliente, cuenta_id)
    r = servicio.conciliar_automatico(ctx.db, cliente, cb, rango.desde, rango.hasta,
                                      incluir_cfdi=rango.incluir_cfdi, uid=ctx.uid)
    registrar(ctx, "conciliacion.automatica", "cuenta_bancaria", cb.id,
              {"conciliados": r["conciliados"]}, cliente)
    return {"exito": True, "resultado": r}


@router.post("/clientes/{clave}/cuentas/{cuenta_id}/conciliaciones", status_code=201)
def conciliar_manual(clave: str, cuenta_id: int, entrada: ConciliacionManual,
                     ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    cliente = cliente_o_404(ctx, clave)
    exigir_rol(ctx, *ROLES_CONTABLES)  # auxiliar: sólo lectura
    cb = servicio.cuenta_o_404(ctx.db, cliente, cuenta_id)
    c = servicio.conciliar_manual(ctx.db, cliente, cb, entrada.banco, entrada.libros,
                                  entrada.motivo, ctx.uid)
    registrar(ctx, "conciliacion.manual", "conciliacion", c.id, None, cliente)
    return {"exito": True, "conciliacion_id": c.id}


@router.delete("/clientes/{clave}/cuentas/{cuenta_id}/conciliaciones/{conciliacion_id}")
def deshacer(clave: str, cuenta_id: int, conciliacion_id: int,
             ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    cliente = cliente_o_404(ctx, clave)
    exigir_rol(ctx, *ROLES_CONTABLES)  # auxiliar: sólo lectura
    cb = servicio.cuenta_o_404(ctx.db, cliente, cuenta_id)
    servicio.deshacer(ctx.db, cliente, cb, conciliacion_id)
    registrar(ctx, "conciliacion.deshacer", "conciliacion", conciliacion_id, None, cliente)
    return {"exito": True}


@router.get("/clientes/{clave}/cuentas/{cuenta_id}/movimientos/{movimiento_id}/sugerencia")
def sugerencia(clave: str, cuenta_id: int, movimiento_id: int,
               ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    """Cuenta sugerida para la póliza de un movimiento del banco sin CFDI."""
    from app.modelos.conciliacion import MovimientoBancario

    cliente = cliente_o_404(ctx, clave)
    cb = servicio.cuenta_o_404(ctx.db, cliente, cuenta_id)
    mov = ctx.db.get(MovimientoBancario, movimiento_id)
    if mov is None or mov.cuenta_bancaria_id != cb.id:
        raise FiscalAgentError("No existe ese movimiento en esta cuenta bancaria.", 404)
    return {"exito": True, "sugerida": servicio.sugerir_cuenta(ctx.db, cliente, mov)}


@router.post("/clientes/{clave}/cuentas/{cuenta_id}/movimientos/{movimiento_id}/poliza",
             status_code=201)
def poliza_desde_banco(clave: str, cuenta_id: int, movimiento_id: int,
                       entrada: PolizaDesdeBanco,
                       ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    cliente = cliente_o_404(ctx, clave)
    exigir_rol(ctx, *ROLES_CONTABLES)  # póliza manual: auxiliar no
    cb = servicio.cuenta_o_404(ctx.db, cliente, cuenta_id)
    p, c =servicio.crear_poliza(ctx.db, cliente, cb, movimiento_id,
                                 [(x.cuenta_id, x.importe) for x in entrada.contrapartidas],
                                 entrada.concepto, ctx.uid)
    registrar(ctx, "conciliacion.poliza_desde_banco", "poliza", p.id, None, cliente)
    from app.contabilidad import polizas

    return {"exito": True, "poliza": polizas.como_dict(ctx.db, p, detalle=True),
            "conciliacion_id": c.id}


@router.get("/clientes/{clave}/cuentas/{cuenta_id}/reporte")
def ver_reporte(clave: str, cuenta_id: int, corte: date = Query(...),
                formato: Literal["json", "xlsx"] = Query("json"),
                ctx: Contexto = Depends(contexto_actual)) -> Any:
    """Reporte de conciliación al corte (saldo banco vs libros, partidas en tránsito)."""
    cliente = cliente_o_404(ctx, clave)
    cb = servicio.cuenta_o_404(ctx.db, cliente, cuenta_id)
    r = reporte.reporte(ctx.db, cliente, cb, corte)
    if formato == "xlsx":
        nombre = f"conciliacion-{cliente.clave}-{cb.id}-{corte.isoformat()}.xlsx"
        return Response(
            reporte.a_excel(r, cliente.nombre or cliente.clave),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{nombre}"'})
    return {"exito": True, "reporte": r}
