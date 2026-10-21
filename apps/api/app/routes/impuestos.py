"""
Impuestos del cliente (P3-02, P3-03, P3-07): `/api/v1/impuestos/clientes/{clave}/...`.

Todo pasa por `contexto_actual` + `cliente_o_404` (cliente de otro despacho = 404). Los
importes salen de la bóveda (`comprobantes_vigentes`) y de los motores; nada se guarda salvo
la configuración del cliente (DP-3). Contrato en `docs/api-contract.md` §Impuestos.
"""

from __future__ import annotations

import csv
import io
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import Response

from app.fiscal_engine.actualizacion import fecha_limite_mensual
from app.fiscal_engine.isn import resultado_isn_dict
from app.fiscal_engine.resumen_impuestos import (
    Captura,
    OpcionesResumen,
    ResumenImpuestos,
    armar_resumen,
    resumen_dict,
)
from app.impuestos import isn_cliente, servicio
from app.schemas.impuestos import ConfigImpuestosSchema, IvaPeriodoRequest, ResumenRequest
from app.tenancy import Contexto, cliente_o_404, contexto_actual

router = APIRouter(prefix="/impuestos", tags=["impuestos"])

COLUMNAS = (("concepto", "Concepto"), ("importe_sistema", "Importe sistema"),
            ("importe_a_pagar", "Importe a pagar"), ("actualizacion", "Actualización"),
            ("recargos", "Recargos"), ("subsidio", "Subsidio para el empleo"),
            ("compensaciones", "Compensaciones"), ("total", "Total"))


@router.get("/clientes/{clave}/config")
def leer_config(clave: str, ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    """Criterio fiscal del cliente (DP-3), con defaults si no hay."""
    cliente = cliente_o_404(ctx, clave)
    return {"exito": True, "config": servicio.config_de(ctx.db, cliente).model_dump(mode="json")}


@router.put("/clientes/{clave}/config")
def guardar_config(
    clave: str, cfg: ConfigImpuestosSchema, ctx: Contexto = Depends(contexto_actual)
) -> dict[str, Any]:
    """Guarda el criterio fiscal del cliente."""
    cliente = cliente_o_404(ctx, clave)
    servicio.guardar_config(ctx.db, cliente, cfg)
    return {"exito": True, "config": cfg.model_dump(mode="json")}


def _resumen(ctx: Contexto, clave: str, req: ResumenRequest) -> ResumenImpuestos:
    cliente = cliente_o_404(ctx, clave)
    cfg = servicio.config_de(ctx.db, cliente)
    importes, notas = servicio.importes_del_periodo(ctx.db, cliente, req.anio, req.mes)
    capturas = {
        k: Captura(v.importe_a_pagar, v.subsidio, v.compensaciones)
        for k, v in req.capturas.items()
    }
    r = armar_resumen(
        req.anio, req.mes, req.fecha_limite or fecha_limite_mensual(req.anio, req.mes),
        req.fecha_pago, importes, capturas,
        OpcionesResumen(cfg.modo_factor, cfg.tipo_recargo, cfg.tope_meses_recargos),
    )
    r.notas = notas + r.notas
    return r


def _xlsx(r: ResumenImpuestos, nombre: str) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Font

    libro = Workbook()
    hoja = libro.active
    hoja.title = f"{r.anio}-{r.mes:02d}"
    hoja.append([f"Resumen de impuestos · {nombre} · {r.mes:02d}/{r.anio}"])
    hoja.append([f"Fecha límite {r.fecha_limite.isoformat()} · Fecha de pago "
                 f"{r.fecha_pago.isoformat()}"])
    hoja.append([t for _, t in COLUMNAS])
    for celda in hoja[3]:
        celda.font = Font(bold=True)
    for x in r.renglones:
        hoja.append([x.concepto] + [float(getattr(x, k)) for k, _ in COLUMNAS[1:]])
    hoja.append(["Total"] + [float(r.totales[k]) for k, _ in COLUMNAS[1:]])
    hoja.append(["Total a pagar (ajustado a pesos, Art. 20 CFF)",
                 float(r.total_a_pagar_ajustado)])
    for nota in r.notas:
        hoja.append([nota])
    for fila in hoja.iter_rows(min_row=4, min_col=2):
        for c in fila:
            c.number_format = "#,##0.00"
    hoja.column_dimensions["A"].width = 46
    buf = io.BytesIO()
    libro.save(buf)
    return buf.getvalue()


def _csv(r: ResumenImpuestos) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([t for _, t in COLUMNAS])
    for x in r.renglones:
        w.writerow([x.concepto] + [f"{getattr(x, k):.2f}" for k, _ in COLUMNAS[1:]])
    w.writerow(["Total"] + [f"{r.totales[k]:.2f}" for k, _ in COLUMNAS[1:]])
    return buf.getvalue().encode("utf-8-sig")


@router.post("/clientes/{clave}/resumen", response_model=None)
def resumen(
    clave: str, req: ResumenRequest, ctx: Contexto = Depends(contexto_actual)
) -> dict[str, Any] | Response:
    """Tabla de impuestos del periodo con actualización y recargos a la fecha de pago."""
    r = _resumen(ctx, clave, req)
    base = f"resumen-impuestos-{clave}-{r.anio}-{r.mes:02d}"
    if req.formato == "xlsx":
        cliente = cliente_o_404(ctx, clave)
        return Response(
            _xlsx(r, cliente.nombre or clave),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{base}.xlsx"'},
        )
    if req.formato == "csv":
        return Response(_csv(r), media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="{base}.csv"'})
    return {"exito": True, **resumen_dict(r)}


@router.post("/clientes/{clave}/iva")
def iva(
    clave: str, req: IvaPeriodoRequest, ctx: Contexto = Depends(contexto_actual)
) -> dict[str, Any]:
    """IVA de uno o varios meses desde la bóveda, con saldo a favor arrastrado (Art. 6o. LIVA)."""
    cliente = cliente_o_404(ctx, clave)
    resultados = servicio.iva_periodos(
        ctx.db, cliente, req.anio, req.meses, req.saldo_favor_inicial, req.opciones_saldo
    )
    return {"exito": True, "anio": req.anio,
            "meses": [servicio.resumen_iva_json(r) for r in resultados]}


@router.get("/clientes/{clave}/isn")
def isn(
    clave: str, anio: int, mes: int, ctx: Contexto = Depends(contexto_actual)
) -> dict[str, Any]:
    """ISN del mes del cliente con sus CFDI de nómina y su entidad."""
    cliente = cliente_o_404(ctx, clave)
    r, n = isn_cliente.isn_del_cliente(ctx.db, cliente, anio, mes)
    return {"exito": True, "anio": anio, "mes": mes, "nominas": n, **resultado_isn_dict(r),
            "fecha_limite": fecha_limite_mensual(anio, mes).isoformat()}
