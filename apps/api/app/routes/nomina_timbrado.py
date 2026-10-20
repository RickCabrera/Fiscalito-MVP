"""
Timbrado del CFDI de nómina de un periodo cerrado (P4-11).

`/api/v1/nomina/clientes/{clave}/periodos/{id}/...`: timbrar (trabajo en segundo plano),
estado por recibo, XML/PDF de cada uno, ZIP de todos y cancelación con motivo. Tenencia:
`cliente_o_404` + `periodo_o_404`; un CFDI de otro periodo es 404.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app import nomina_servicio as srv
from app.modelos.trabajos import Trabajo
from app.nomina_cfdi import pdf, servicio
from app.tenancy import Contexto, cliente_o_404, contexto_actual

router = APIRouter(prefix="/nomina/clientes/{clave}/periodos/{periodo_id}",
                   tags=["Nómina — timbrado"])


class CancelarCfdi(BaseModel):
    motivo: str = Field(pattern=r"^0[1-4]$")
    folio_sustitucion: str | None = Field(None, pattern=r"^[0-9A-Fa-f-]{36}$")


def _trabajo_json(t: Trabajo | None) -> dict[str, Any] | None:
    if t is None:
        return None
    return {"id": t.id, "estado": t.estado, "intentos": t.intentos, "error": t.error,
            "resultado": t.resultado}


def _estado(ctx: Contexto, clave: str, periodo_id: int) -> dict[str, Any]:
    from sqlalchemy import select

    cliente = cliente_o_404(ctx, clave)
    periodo = servicio.periodo_de(ctx.db, cliente, periodo_id)
    nombres = {r.id: r.nombre for r in srv.recibos_de(ctx.db, periodo)}
    trabajo = ctx.db.scalar(select(Trabajo).where(
        Trabajo.clave_unica == f"nomina-timbrar-{periodo.id}",
        Trabajo.cliente_id == cliente.id).order_by(Trabajo.id.desc()))
    return {
        "exito": True, "periodo_id": periodo.id, "estado_periodo": periodo.estado,
        "por_estado": servicio.resumen(ctx.db, periodo), "trabajo": _trabajo_json(trabajo),
        "recibos": [servicio.cfdi_json(c, nombres.get(c.recibo_id, ""))
                    for c in servicio.cfdi_de(ctx.db, periodo)],
    }


@router.post("/timbrar", summary="Timbrar la nómina completa (trabajo en segundo plano)")
def timbrar(clave: str, periodo_id: int, ctx: Contexto = Depends(contexto_actual)
            ) -> dict[str, Any]:
    cliente = cliente_o_404(ctx, clave)
    periodo = servicio.periodo_de(ctx.db, cliente, periodo_id)
    trabajo = servicio.solicitar(ctx.db, cliente, periodo, ctx.uid)
    return {**_estado(ctx, clave, periodo_id), "trabajo": _trabajo_json(trabajo)}


@router.get("/cfdi", summary="Estado del timbrado por recibo")
def estado(clave: str, periodo_id: int, ctx: Contexto = Depends(contexto_actual)
           ) -> dict[str, Any]:
    return _estado(ctx, clave, periodo_id)


def _cfdi(ctx: Contexto, clave: str, periodo_id: int, cfdi_id: int) -> Any:
    cliente = cliente_o_404(ctx, clave)
    periodo = servicio.periodo_de(ctx.db, cliente, periodo_id)
    return cliente, periodo, servicio.obtener(ctx.db, periodo, cfdi_id)


@router.get("/cfdi/{cfdi_id}/xml", summary="XML timbrado de un recibo")
def xml(clave: str, periodo_id: int, cfdi_id: int, ctx: Contexto = Depends(contexto_actual)
        ) -> Response:
    _, _, c = _cfdi(ctx, clave, periodo_id, cfdi_id)
    return Response(servicio.leer_xml(c), media_type="application/xml", headers={
        "Content-Disposition": f'attachment; filename="nomina-{c.empleado_no}-{c.uuid}.xml"'})


@router.get("/cfdi/{cfdi_id}/pdf", summary="Recibo PDF con QR")
def recibo_pdf(clave: str, periodo_id: int, cfdi_id: int,
               ctx: Contexto = Depends(contexto_actual)) -> Response:
    _, _, c = _cfdi(ctx, clave, periodo_id, cfdi_id)
    return Response(pdf.recibo(servicio.leer_xml(c), c.es_prueba), media_type="application/pdf",
                    headers={"Content-Disposition":
                             f'attachment; filename="nomina-{c.empleado_no}-{c.uuid}.pdf"'})


@router.get("/cfdi.zip", summary="ZIP con el XML y el PDF de todos los recibos timbrados")
def zip_periodo(clave: str, periodo_id: int, ctx: Contexto = Depends(contexto_actual)
                ) -> Response:
    cliente = cliente_o_404(ctx, clave)
    periodo = servicio.periodo_de(ctx.db, cliente, periodo_id)
    return Response(servicio.zip_del_periodo(ctx.db, periodo, pdf.recibo),
                    media_type="application/zip", headers={
                        "Content-Disposition":
                        f'attachment; filename="nomina-{clave}-{periodo.inicio}-'
                        f'{periodo.fin}.zip"'})


@router.post("/cfdi/{cfdi_id}/cancelar", summary="Cancelar el CFDI de un recibo con motivo")
def cancelar(clave: str, periodo_id: int, cfdi_id: int, cuerpo: CancelarCfdi,
             ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    cliente, periodo, c = _cfdi(ctx, clave, periodo_id, cfdi_id)
    servicio.cancelar(ctx.db, cliente, periodo, c, cuerpo.motivo, cuerpo.folio_sustitucion)
    return {"exito": True, "cfdi": servicio.cfdi_json(c), "estado_periodo": periodo.estado}
