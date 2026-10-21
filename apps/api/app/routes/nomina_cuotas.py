"""
Cuotas obrero-patronales del mes/bimestre y conciliación contra la cédula EMA/EBA (P4-10).

`/api/v1/nomina/clientes/{clave}/cuotas-imss` calcula; `/cedulas` importa la cédula del IMSS
(CSV, XLSX o TXT con configuración de columnas) y la concilia trabajador por trabajador;
`/cedulas/{id}/reporte` la exporta. Tenencia: `cliente_o_404`.
"""

from __future__ import annotations

import json
from typing import Any, Literal

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy import select

from app.exceptions import FiscalAgentError
from app.modelos.imss import CedulaImss
from app.nomina_imss import cedula, cuotas
from app.tenancy import Contexto, cliente_o_404, contexto_actual

router = APIRouter(prefix="/nomina/clientes/{clave}", tags=["Nómina — cuotas IMSS"])
MAX_CEDULA = 5 * 1024 * 1024


def _periodo(tipo: str, periodo: int) -> dict[str, int | None]:
    if tipo == "EMA":
        if not 1 <= periodo <= 12:
            raise FiscalAgentError("La EMA es mensual: periodo 1 a 12.", 422)
        return {"mes": periodo, "bimestre": None}
    if not 1 <= periodo <= 6:
        raise FiscalAgentError("La EBA es bimestral: periodo 1 a 6.", 422)
    return {"mes": None, "bimestre": periodo}


def _cuotas_csv(r: dict[str, Any]) -> bytes:
    claves = sorted(r["por_ramo"])
    filas = [["NSS", "Empleado", "Nombre", "Días", "Ausentismo", "Incapacidad", "SBC",
              *[f"{c} patrón" for c in claves], *[f"{c} obrero" for c in claves], "Total"]]
    for t in r["trabajadores"]:
        filas.append([t["nss"], t["empleado_no"], t["nombre"], str(t["dias"]),
                      str(t["dias_ausentismo"]), str(t["dias_incapacidad"]), t["sbc"],
                      *[t["ramos"].get(c, {}).get("patron", "0.00") for c in claves],
                      *[t["ramos"].get(c, {}).get("obrero", "0.00") for c in claves], t["total"]])
    filas.append(["TOTAL", "", "", "", "", "", "", *[r["por_ramo"][c] for c in claves],
                  *["" for _ in claves], r["total"]])
    return cedula.a_csv(filas)


@router.get("/cuotas-imss", summary="Cuotas del mes (EMA) o del bimestre (EBA) por trabajador")
def calcular(
    clave: str, ejercicio: int = Query(..., ge=2026, le=2030),
    mes: int | None = Query(None, ge=1, le=12), bimestre: int | None = Query(None, ge=1, le=6),
    tope_ausentismo: int | None = Query(7, ge=0, le=31),
    formato: Literal["json", "csv"] = "json", ctx: Contexto = Depends(contexto_actual),
) -> Any:
    cliente = cliente_o_404(ctx, clave)
    r = cuotas.calcular(ctx.db, cliente, ejercicio, mes=mes, bimestre=bimestre,
                        tope_ausentismo=tope_ausentismo)
    if formato == "csv":
        nombre = f"cuotas-{r['tipo']}-{clave}-{ejercicio}-{mes or bimestre}.csv"
        return Response(_cuotas_csv(r), media_type="text/csv",
                        headers={"Content-Disposition": f'attachment; filename="{nombre}"'})
    return {"exito": True, **r}


@router.get("/cedulas/plantilla", summary="Plantilla CSV de la cédula EMA o EBA")
def plantilla(clave: str, tipo: Literal["EMA", "EBA"] = "EMA",
              ctx: Contexto = Depends(contexto_actual)) -> Response:
    cliente_o_404(ctx, clave)
    return Response(cedula.plantilla_csv(tipo).encode(), media_type="text/csv", headers={
        "Content-Disposition": f'attachment; filename="plantilla-{tipo}.csv"'})


def _cedula_json(c: CedulaImss, completo: bool = False) -> dict[str, Any]:
    base = {"id": c.id, "tipo": c.tipo, "ejercicio": c.ejercicio, "periodo": c.periodo,
            "nombre_archivo": c.nombre_archivo, "diferencias": c.diferencias,
            "creado_en": c.creado_en.isoformat() if c.creado_en else None}
    if completo:
        base.update({"conciliacion": c.conciliacion, "configuracion": c.configuracion})
    return base


@router.post("/cedulas", summary="Importar la cédula EMA/EBA y conciliarla")
async def importar(
    clave: str,
    archivo: UploadFile = File(...),
    tipo: Literal["EMA", "EBA"] = Form(...),
    ejercicio: int = Form(..., ge=2026, le=2030),
    periodo: int = Form(...),
    configuracion: str = Form("{}"),
    ctx: Contexto = Depends(contexto_actual),
) -> dict[str, Any]:
    cliente = cliente_o_404(ctx, clave)
    try:
        cfg = cedula.Configuracion.de_dict(json.loads(configuracion or "{}"))
    except (ValueError, TypeError) as e:
        raise FiscalAgentError(f"Configuración de columnas ilegible: {e}", 422) from e
    datos = await archivo.read(MAX_CEDULA + 1)
    if len(datos) > MAX_CEDULA:
        raise FiscalAgentError("La cédula pesa más de 5 MB.", 413)
    filas = cedula.leer(datos, archivo.filename or "cedula.csv", tipo, cfg)
    calculo = cuotas.calcular(ctx.db, cliente, ejercicio, **_periodo(tipo, periodo))
    conciliacion = cedula.conciliar(calculo, filas, tipo, cfg.tolerancia)
    conciliacion["advertencias_calculo"] = calculo["advertencias"]
    fila = CedulaImss(
        cliente_id=cliente.id, tipo=tipo, ejercicio=ejercicio, periodo=periodo,
        nombre_archivo=archivo.filename or "", configuracion=cfg.como_dict(),
        filas=json.loads(json.dumps(filas, default=str)), conciliacion=conciliacion,
        diferencias=conciliacion["con_diferencia"], creado_por=ctx.uid,
    )
    ctx.db.add(fila)
    ctx.db.flush()
    return {"exito": True, "cedula": _cedula_json(fila, completo=True)}


@router.get("/cedulas", summary="Cédulas importadas")
def listar(clave: str, ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    cliente = cliente_o_404(ctx, clave)
    filas = ctx.db.scalars(select(CedulaImss).where(CedulaImss.cliente_id == cliente.id)
                           .order_by(CedulaImss.id.desc()))
    return {"exito": True, "cedulas": [_cedula_json(c) for c in filas]}


def _cedula(ctx: Contexto, clave: str, cedula_id: int) -> CedulaImss:
    cliente = cliente_o_404(ctx, clave)
    c = ctx.db.scalar(select(CedulaImss).where(CedulaImss.id == cedula_id,
                                               CedulaImss.cliente_id == cliente.id))
    if c is None:
        raise FiscalAgentError("No existe esa cédula en este cliente.", status_code=404)
    return c


@router.get("/cedulas/{cedula_id}", summary="Una cédula con su conciliación")
def abrir(clave: str, cedula_id: int, ctx: Contexto = Depends(contexto_actual)
          ) -> dict[str, Any]:
    return {"exito": True, "cedula": _cedula_json(_cedula(ctx, clave, cedula_id), True)}


@router.get("/cedulas/{cedula_id}/reporte", summary="Reporte de la conciliación (CSV o XLSX)")
def reporte(clave: str, cedula_id: int, formato: Literal["csv", "xlsx"] = "csv",
            ctx: Contexto = Depends(contexto_actual)) -> Response:
    c = _cedula(ctx, clave, cedula_id)
    filas = cedula.reporte_filas(c.conciliacion)
    nombre = f"conciliacion-{c.tipo}-{c.ejercicio}-{c.periodo}.{formato}"
    if formato == "xlsx":
        cuerpo = cedula.a_xlsx(filas, f"{c.tipo} {c.ejercicio}-{c.periodo}")
        tipo = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        cuerpo, tipo = cedula.a_csv(filas), "text/csv"
    return Response(cuerpo, media_type=tipo,
                    headers={"Content-Disposition": f'attachment; filename="{nombre}"'})
