"""
Reportes contables (P2-05) y cierre de periodo y de ejercicio (P2-08):
`/api/v1/contabilidad/clientes/{clave}/reportes/...`, `.../periodos/...` y `.../cierre-anual/...`.

Mismas reglas que `contabilidad.py`: `contexto_actual` + `cliente_o_404` (otro despacho =
404) y todo id se busca junto con el cliente. Contrato en `docs/api-contract.md`
§Contabilidad — reportes y cierre.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.auditoria import registrar
from app.contabilidad import balanza, cierre, excel, polizas, reportes
from app.exceptions import FiscalAgentError
from app.modelos.nucleo import Cliente
from app.tenancy import ROLES_CONTABLES, Contexto, cliente_o_404, contexto_actual, exigir_rol

router = APIRouter(prefix="/contabilidad", tags=["contabilidad"])

Solo = Literal["con_movimiento", "con_saldo_o_movimiento", "todas"]
Agrupar = Literal["cuenta", "agrupador"]
Comparar = Literal["ninguno", "periodo_anterior", "anio_anterior"]
Idioma = Literal["es", "en"]
Reporte = Literal["balanza", "auxiliar", "estado_resultados", "balance_general", "polizas"]
MAX_POLIZAS_REPORTE = 2000


class FiltrosReporte:
    """Los filtros comunes de los estados financieros, como dependencia de FastAPI."""

    def __init__(
        self,
        desde: date = Query(...), hasta: date = Query(...),
        nivel: int | None = Query(None, ge=1, le=10),
        solo: Solo = Query("con_saldo_o_movimiento"),
        agrupar: Agrupar = Query("cuenta"),
        moneda: str = Query("MXN", min_length=3, max_length=3),
        tipo_cambio: Decimal | None = Query(None, gt=0, max_digits=18, decimal_places=6),
        idioma: Idioma = Query("es"),
        comparar: Comparar = Query("ninguno"),
        incluir_cierre: bool = Query(False),
    ) -> None:
        self.desde, self.hasta = desde, hasta
        self.opciones = reportes.Opciones(
            nivel=nivel, solo=solo, agrupar=agrupar, moneda=moneda, tipo_cambio=tipo_cambio,
            idioma=idioma, comparar=comparar, incluir_cierre=incluir_cierre)


def _estado(ctx: Contexto, cliente: Cliente, reporte: str, f: FiltrosReporte) -> dict[str, Any]:
    if reporte == "estado_resultados":
        return reportes.estado_resultados(ctx.db, cliente, f.desde, f.hasta, f.opciones)
    return reportes.balance_general(ctx.db, cliente, f.hasta, f.opciones, desde=f.desde)


# ── P2-05: estados financieros ──


@router.get("/clientes/{clave}/reportes/estado-resultados")
def estado_resultados(clave: str, f: FiltrosReporte = Depends(),
                      ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    cliente = cliente_o_404(ctx, clave)
    return {"exito": True, **_estado(ctx, cliente, "estado_resultados", f)}


@router.get("/clientes/{clave}/reportes/balance-general")
def balance_general(clave: str, f: FiltrosReporte = Depends(),
                    ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    cliente = cliente_o_404(ctx, clave)
    return {"exito": True, **_estado(ctx, cliente, "balance_general", f)}


def _polizas_detalle(ctx: Contexto, cliente: Cliente, desde: date, hasta: date,
                     estado: str | None) -> tuple[list[dict[str, Any]], int]:
    filtros = polizas.FiltrosPolizas(desde=desde, hasta=hasta, estado=estado)
    filas, total = polizas.listar(ctx.db, cliente, filtros, 1, MAX_POLIZAS_REPORTE)
    return [polizas.como_dict(ctx.db, p, detalle=True) for p in filas], total


@router.get("/clientes/{clave}/reportes/polizas")
def polizas_impresion(
    clave: str, desde: date = Query(...), hasta: date = Query(...),
    estado: Literal["activa", "cancelada"] | None = Query(None),
    ctx: Contexto = Depends(contexto_actual),
) -> dict[str, Any]:
    """Pólizas del rango CON sus movimientos, para imprimirlas (máx. 2000)."""
    cliente = cliente_o_404(ctx, clave)
    lista, total = _polizas_detalle(ctx, cliente, desde, hasta, estado)
    return {"exito": True, "desde": desde.isoformat(), "hasta": hasta.isoformat(),
            "total": total, "truncado": total > len(lista), "polizas": lista}


@router.get("/clientes/{clave}/reportes/excel")
def exportar_excel(
    clave: str, reporte: Reporte = Query(...), cuenta_id: int | None = Query(None),
    f: FiltrosReporte = Depends(), ctx: Contexto = Depends(contexto_actual),
) -> Response:
    """El reporte pedido como .xlsx (importes numéricos con formato y sus totales)."""
    cliente = cliente_o_404(ctx, clave)
    datos_cliente = {"clave": cliente.clave, "nombre": cliente.nombre, "rfc": cliente.rfc}
    op = f.opciones
    if reporte == "balanza":
        datos = balanza.balanza(ctx.db, cliente, f.desde, f.hasta, nivel=op.nivel, solo=op.solo,
                                incluir_cierre=op.incluir_cierre)
        contenido = excel.balanza(datos, datos_cliente)
    elif reporte == "auxiliar":
        if cuenta_id is None:
            raise FiscalAgentError("El auxiliar pide 'cuenta_id'.", 422)
        datos = balanza.auxiliar(ctx.db, cliente, cuenta_id, f.desde, f.hasta,
                                 incluir_cierre=op.incluir_cierre)
        contenido = excel.auxiliar(datos, datos_cliente)
    elif reporte == "polizas":
        lista, _total = _polizas_detalle(ctx, cliente, f.desde, f.hasta, None)
        contenido = excel.polizas(lista, datos_cliente, f.desde.isoformat(),
                                  f.hasta.isoformat())
    else:
        contenido = excel.estado_financiero(_estado(ctx, cliente, reporte, f))
    nombre = f"{reporte}_{cliente.clave}_{f.desde.isoformat()}_{f.hasta.isoformat()}.xlsx"
    nombre = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in nombre)
    return Response(content=contenido, media_type=excel.MIME,
                    headers={"Content-Disposition": f'attachment; filename="{nombre}"'})


# ── P2-08: periodos ──


class Cierre(BaseModel):
    forzar: bool = False
    motivo: str = Field("", max_length=500)


class Reapertura(BaseModel):
    motivo: str = Field(..., min_length=5, max_length=500)


class CierreAnual(BaseModel):
    traspasar_resultado: bool = False
    forzar: bool = False
    motivo: str = Field("", max_length=500)


def _anio(anio: int) -> int:
    if not 2000 <= anio <= 2100:
        raise FiscalAgentError("Ejercicio inválido.", 422)
    return anio


@router.get("/clientes/{clave}/periodos/{anio}")
def periodos_del_ejercicio(clave: str, anio: int,
                           ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    cliente = cliente_o_404(ctx, clave)
    return {"exito": True, **cierre.estado_ejercicio(ctx.db, cliente, _anio(anio))}


@router.get("/clientes/{clave}/periodos/{anio}/{mes}/validacion")
def validar_mes(clave: str, anio: int, mes: int,
                ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    """Qué impide cerrar el mes: descuadre y CFDI vigentes sin póliza (con su lista)."""
    cliente = cliente_o_404(ctx, clave)
    if not 1 <= mes <= 12:
        raise FiscalAgentError("Periodo inválido.", 422)
    desde = date(_anio(anio), mes, 1)
    return {"exito": True, **cierre.validar(ctx.db, cliente, desde,
                                            reportes._fin_de_mes(anio, mes))}


@router.post("/clientes/{clave}/periodos/{anio}/{mes}/cerrar")
def cerrar_mes(clave: str, anio: int, mes: int, entrada: Cierre,
               ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    cliente = cliente_o_404(ctx, clave)
    exigir_rol(ctx, *ROLES_CONTABLES)  # auxiliar: sólo lectura
    v = cierre.cerrar_mes(ctx.db, cliente, anio, mes, ctx.uid, forzar=entrada.forzar,
                          motivo=entrada.motivo)
    registrar(ctx, "contabilidad.cerrar_periodo", "cliente", cliente.id,
              {"anio": anio, "mes": mes, "forzado": bool(v["total_cfdi_sin_poliza"]),
               "motivo": entrada.motivo}, cliente)
    return {"exito": True, "validacion": v}


@router.post("/clientes/{clave}/periodos/{anio}/{mes}/reabrir")
def reabrir_mes(clave: str, anio: int, mes: int, entrada: Reapertura,
                ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    cliente = cliente_o_404(ctx, clave)
    exigir_rol(ctx, *ROLES_CONTABLES)  # auxiliar: sólo lectura
    cierre.reabrir_mes(ctx.db, cliente, anio, mes, ctx.uid, ctx.rol, entrada.motivo)
    registrar(ctx, "contabilidad.abrir_periodo", "cliente", cliente.id,
              {"anio": anio, "mes": mes, "motivo": entrada.motivo}, cliente)
    return {"exito": True}


@router.get("/clientes/{clave}/cierre-anual/{anio}/validacion")
def validar_ejercicio(clave: str, anio: int,
                      ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    cliente = cliente_o_404(ctx, clave)
    inicio = cierre._inicio_ejercicio(ctx.db, cliente, _anio(anio))
    return {"exito": True, **cierre.validar(ctx.db, cliente, inicio, date(anio, 12, 31))}


@router.post("/clientes/{clave}/cierre-anual/{anio}")
def cierre_anual(clave: str, anio: int, entrada: CierreAnual,
                 ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    cliente = cliente_o_404(ctx, clave)
    exigir_rol(ctx, *ROLES_CONTABLES)  # auxiliar: sólo lectura
    r = cierre.cierre_anual(ctx.db, cliente, _anio(anio), ctx.uid,
                            traspasar_resultado=entrada.traspasar_resultado,
                            forzar=entrada.forzar, motivo=entrada.motivo)
    registrar(ctx, "contabilidad.cierre_anual", "cliente", cliente.id,
              {"anio": anio, "resultado": r["resultado"], "motivo": entrada.motivo}, cliente)
    return {"exito": True, **r}


@router.post("/clientes/{clave}/cierre-anual/{anio}/deshacer")
def deshacer_cierre_anual(clave: str, anio: int, entrada: Reapertura,
                          ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    cliente = cliente_o_404(ctx, clave)
    exigir_rol(ctx, *ROLES_CONTABLES)  # auxiliar: sólo lectura
    n = cierre.deshacer_cierre_anual(ctx.db, cliente, _anio(anio), ctx.uid, ctx.rol,
                                     entrada.motivo)
    registrar(ctx, "contabilidad.deshacer_cierre_anual", "cliente", cliente.id,
              {"anio": anio, "motivo": entrada.motivo}, cliente)
    return {"exito": True, "canceladas": n}
