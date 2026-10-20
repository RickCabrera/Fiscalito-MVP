"""
Movimientos afiliatorios del IMSS por cliente (P4-09).

`/api/v1/nomina/clientes/{clave}/movimientos-imss/...`: pendientes por enviar, archivo IDSE por
tipo (08/07/02) o de importación al SUA, marcar enviado / acuse; historial y cambio de SBC del
empleado; modificación bimestral de la parte variable. Tenencia: `cliente_o_404`.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select

from app import nomina_servicio as srv
from app.exceptions import FiscalAgentError
from app.modelos.imss import LoteImss, MovimientoImss
from app.nomina_imss import archivos, bimestre_variable
from app.nomina_imss.historial import historial_de, hoy, registrar_sbc
from app.suscripciones.vigencia import exigir_modulo
from app.tenancy import Contexto, cliente_o_404, contexto_actual

router = APIRouter(prefix="/nomina/clientes/{clave}", tags=["Nómina — IMSS"])


class GenerarArchivo(BaseModel):
    destino: Literal["idse_08", "idse_07", "idse_02", "sua_trabajadores", "sua_movimientos"]
    ids: list[int] | None = None
    al: date | None = Field(None, description="SUA trabajadores: plantilla vigente a esta fecha.")
    desde: date | None = None
    hasta: date | None = None


class MarcarMovimientos(BaseModel):
    ids: list[int] = Field(min_length=1)
    estado: Literal["enviado", "acuse", "cancelado"]
    acuse: str = Field("", max_length=120)


class CambioSBC(BaseModel):
    fecha: date
    sbc: Decimal = Field(gt=0)
    tipo_salario: Literal["0", "1", "2"] | None = None
    motivo: Literal["aumento", "prestaciones", "correccion"] = "aumento"
    nota: str = Field("", max_length=500)
    actualizar_ficha: bool = Field(
        True, description="Copia el SBC a la ficha si ya está vigente (fecha <= hoy).")


class BimestreVariable(BaseModel):
    ejercicio: int = Field(ge=2026, le=2030)
    bimestre: int = Field(ge=1, le=6, description="El bimestre que se promedia.")
    aplicar: bool = False


def _fichas(ctx: Contexto, cliente: Any) -> dict[str, Any]:
    return {f.empleado_no: f for f in srv.fichas_del_cliente(ctx.db, cliente)[0]}


def _lote_json(lote: LoteImss) -> dict[str, Any]:
    return {"id": lote.id, "tipo": lote.tipo, "nombre_archivo": lote.nombre_archivo,
            "registros": lote.registros, "sha256": lote.sha256,
            "creado_en": lote.creado_en.isoformat() if lote.creado_en else None}


@router.get("/movimientos-imss", summary="Movimientos afiliatorios del cliente")
def listar(
    clave: str, estado: str | None = Query(None), tipo: str | None = Query(None),
    ctx: Contexto = Depends(contexto_actual),
) -> dict[str, Any]:
    cliente = cliente_o_404(ctx, clave)
    q = select(MovimientoImss).where(MovimientoImss.cliente_id == cliente.id)
    if estado:
        q = q.where(MovimientoImss.estado == estado)
    if tipo:
        q = q.where(MovimientoImss.tipo == tipo)
    fichas = _fichas(ctx, cliente)
    movs = ctx.db.scalars(q.order_by(MovimientoImss.fecha.desc(), MovimientoImss.id.desc()))
    lista = [archivos.movimiento_json(m, fichas.get(m.empleado_no)) for m in movs]
    return {"exito": True, "movimientos": lista,
            "pendientes": sum(1 for m in lista if m["estado"] == "pendiente")}


@router.post("/movimientos-imss/archivo", summary="Generar el archivo IDSE o SUA")
def generar(clave: str, cuerpo: GenerarArchivo, ctx: Contexto = Depends(contexto_actual)
            ) -> dict[str, Any]:
    cliente = cliente_o_404(ctx, clave)
    exigir_modulo(ctx.db, ctx.despacho_id, "imss_archivos")  # P5-08: módulo por plan
    if cuerpo.destino.startswith("idse_"):
        r = archivos.generar_idse(ctx.db, cliente, cuerpo.destino[5:], ctx.uid, cuerpo.ids)
    elif cuerpo.destino == "sua_trabajadores":
        r = archivos.generar_sua_trabajadores(ctx.db, cliente, ctx.uid, cuerpo.al or hoy())
    else:
        if not (cuerpo.desde and cuerpo.hasta):
            raise FiscalAgentError("Indica `desde` y `hasta` para los movimientos del SUA.", 422)
        r = archivos.generar_sua_movimientos(ctx.db, cliente, ctx.uid, cuerpo.desde, cuerpo.hasta)
    return {"exito": True, "lote": _lote_json(r.lote), "no_exportables": r.no_exportables,
            "transliterados": r.transliterados}


@router.get("/movimientos-imss/lotes", summary="Archivos generados")
def lotes(clave: str, ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    cliente = cliente_o_404(ctx, clave)
    filas = ctx.db.scalars(select(LoteImss).where(LoteImss.cliente_id == cliente.id)
                           .order_by(LoteImss.id.desc()))
    return {"exito": True, "lotes": [_lote_json(x) for x in filas]}


@router.get("/movimientos-imss/lotes/{lote_id}/archivo", summary="Descargar un archivo generado")
def descargar(clave: str, lote_id: int, ctx: Contexto = Depends(contexto_actual)) -> Response:
    cliente = cliente_o_404(ctx, clave)
    lote = ctx.db.scalar(select(LoteImss).where(LoteImss.id == lote_id,
                                                LoteImss.cliente_id == cliente.id))
    if lote is None:
        raise FiscalAgentError("No existe ese archivo en este cliente.", status_code=404)
    return Response(lote.contenido.encode("ascii"), media_type="text/plain; charset=us-ascii",
                    headers={"Content-Disposition":
                             f'attachment; filename="{lote.nombre_archivo}"'})


@router.post("/movimientos-imss/marcar", summary="Marcar enviados, con acuse o cancelados")
def marcar(clave: str, cuerpo: MarcarMovimientos, ctx: Contexto = Depends(contexto_actual)
           ) -> dict[str, Any]:
    cliente = cliente_o_404(ctx, clave)
    movs = archivos.marcar(ctx.db, cliente, cuerpo.ids, cuerpo.estado, cuerpo.acuse)
    fichas = _fichas(ctx, cliente)
    return {"exito": True,
            "movimientos": [archivos.movimiento_json(m, fichas.get(m.empleado_no)) for m in movs]}


@router.get("/empleados/{empleado_no}/historial-sbc", summary="Historial de SBC del empleado")
def historial(clave: str, empleado_no: str, ctx: Contexto = Depends(contexto_actual)
              ) -> dict[str, Any]:
    cliente = cliente_o_404(ctx, clave)
    return {"exito": True, "historial": [
        {"fecha": h.fecha.isoformat(), "sbc": str(h.sbc), "tipo_salario": h.tipo_salario,
         "motivo": h.motivo, "nota": h.nota}
        for h in historial_de(ctx.db, cliente, empleado_no)]}


@router.post("/empleados/{empleado_no}/sbc", summary="Registrar un cambio de SBC (genera el 07)")
def cambiar_sbc(clave: str, empleado_no: str, cuerpo: CambioSBC,
                ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    from app import almacen_cartera as almacen

    cliente = cliente_o_404(ctx, clave)
    ficha = _fichas(ctx, cliente).get(empleado_no)
    if ficha is None:
        raise FiscalAgentError(f"No existe el empleado {empleado_no} en este cliente.", 404)
    if ficha.fecha_alta and cuerpo.fecha < ficha.fecha_alta:
        raise FiscalAgentError("El cambio de SBC no puede ser anterior al alta.", 422)
    fila, mov = registrar_sbc(ctx.db, cliente, ficha, cuerpo.fecha, cuerpo.sbc,
                              tipo_salario=cuerpo.tipo_salario or ficha.tipo_salario,
                              motivo=cuerpo.motivo, uid=ctx.uid, nota=cuerpo.nota)
    if cuerpo.actualizar_ficha and cuerpo.fecha <= hoy():
        almacen.guardar_empleado(ctx.db, cliente, empleado_no,
                                 {"salario_diario_integrado": str(cuerpo.sbc)}, con_tope=False)
    return {"exito": True, "historial": {"fecha": fila.fecha.isoformat(), "sbc": str(fila.sbc)},
            "movimiento": archivos.movimiento_json(mov, ficha) if mov else None}


@router.post("/movimientos-imss/bimestre-variable",
             summary="Promedio bimestral de la parte variable del SBC (Art. 30 fr. II LSS)")
def variable(clave: str, cuerpo: BimestreVariable, ctx: Contexto = Depends(contexto_actual)
             ) -> dict[str, Any]:
    cliente = cliente_o_404(ctx, clave)
    return {"exito": True, **bimestre_variable.calcular(
        ctx.db, cliente, cuerpo.ejercicio, cuerpo.bimestre, ctx.uid, cuerpo.aplicar)}
