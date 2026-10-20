"""
Envío de recibos al trabajador (P4-13). Contrato: `docs/api-contract.md` §"Nómina — envío de
recibos".

Tenencia: `cliente_o_404` + `periodo_o_404`; plantillas y avisos de rebote por despacho. El
envío corre en segundo plano (`nomina.enviar_recibos`); aquí sólo se preparan los renglones,
se encola y se consulta el estado. La descarga del documento para WhatsApp es la única ruta
pública, con enlace firmado (`app/nomina_envio/enlaces.py`).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

import app.nomina_envio.trabajos  # noqa: F401 — registra el manejador
from app import nomina_servicio as srv
from app.auditoria import registrar
from app.db.session import obtener_db
from app.exceptions import FiscalAgentError
from app.modelos.nomina import NominaPeriodo, ReciboNomina
from app.modelos.nomina_envio import EnvioRecibo
from app.modelos.nucleo import Cliente
from app.nomina_envio import enlaces, plantillas, servicio
from app.nomina_envio.documentos import documentos_del_recibo
from app.schemas.declaraciones import ErrorResponse
from app.tenancy import Contexto, cliente_o_404, contexto_actual

router = APIRouter(tags=["Nómina — envío de recibos"])
router_publico = APIRouter(tags=["Nómina — envío de recibos"])
_ERR = {401: {"model": ErrorResponse}, 404: {"model": ErrorResponse},
        409: {"model": ErrorResponse}, 422: {"model": ErrorResponse}}
Canal = Literal["correo", "whatsapp"]


class PlantillaSchema(BaseModel):
    canal: Canal
    asunto: str = Field(default="", max_length=200)
    cuerpo: str = Field(default="", max_length=8000)
    plantilla_whatsapp: str = Field(default="", max_length=120)
    idioma: str = Field(default="es_MX", max_length=10)
    personalizada: bool = False


class PlantillasResponse(BaseModel):
    exito: bool = True
    variables: list[str]
    plantillas: list[PlantillaSchema]


class PlantillaEntrada(BaseModel):
    asunto: str = Field(default="", max_length=200)
    cuerpo: str = Field(default="", max_length=8000)
    plantilla_whatsapp: str = Field(default="", max_length=120)
    idioma: str = Field(default="es_MX", max_length=10)


class EnviarRequest(BaseModel):
    canal: Canal


class EnvioSchema(BaseModel):
    id: int
    empleado_no: str
    destino: str
    estado: str = Field(description="pendiente | enviado | fallido | rebotado")
    intentos: int
    error: str
    timbrado: bool
    enviado_en: datetime | None


class OmitidoSchema(BaseModel):
    empleado_no: str
    nombre: str
    motivo: str


class EstadoEnviosResponse(BaseModel):
    exito: bool = True
    canal: Canal
    envios: list[EnvioSchema]
    omitidos: list[OmitidoSchema]
    resumen: dict[str, int]
    trabajo: dict[str, str | int | None] | None


class ReboteRequest(BaseModel):
    canal: Canal
    id_mensaje: str = Field(min_length=1, max_length=200)
    motivo: str = Field(default="", max_length=300)


def _plantilla(d: dict[str, str]) -> PlantillaSchema:
    return PlantillaSchema(**{**d, "personalizada": bool(d.get("personalizada"))})


def _estado(ctx: Contexto, cliente: Cliente, periodo: NominaPeriodo,
            canal: str) -> EstadoEnviosResponse:
    envios = servicio.envios_de(ctx.db, periodo, canal)
    resumen = {k: 0 for k in ("pendiente", "enviado", "fallido", "rebotado")}
    for e in envios:
        resumen[e.estado] = resumen.get(e.estado, 0) + 1
    t = servicio.ultimo_trabajo(ctx.db, periodo.id, canal)
    return EstadoEnviosResponse(
        canal=canal,  # type: ignore[arg-type]
        envios=[EnvioSchema(id=e.id, empleado_no=e.empleado_no, destino=e.destino,
                            estado=e.estado, intentos=e.intentos, error=e.error,
                            timbrado=e.timbrado, enviado_en=e.enviado_en) for e in envios],
        omitidos=[OmitidoSchema(**o.__dict__)
                  for o in servicio.omitidos_de(ctx.db, cliente, periodo, canal)],
        resumen=resumen,
        trabajo=None if t is None else {"id": t.id, "estado": t.estado, "error": t.error},
    )


@router.get("/nomina/recibos/plantillas", response_model=PlantillasResponse, responses=_ERR,
            summary="Plantillas del envío de recibos del despacho")
def ver_plantillas(ctx: Contexto = Depends(contexto_actual)) -> PlantillasResponse:
    return PlantillasResponse(
        variables=list(plantillas.VARIABLES),
        plantillas=[_plantilla(plantillas.de_despacho(ctx.db, ctx.despacho_id, c))
                    for c in ("correo", "whatsapp")])


@router.put("/nomina/recibos/plantillas/{canal}", response_model=PlantillaSchema,
            responses=_ERR, summary="Editar la plantilla de un canal")
def editar_plantilla(canal: Canal, entrada: PlantillaEntrada,
                     ctx: Contexto = Depends(contexto_actual)) -> PlantillaSchema:
    plantillas.guardar(ctx.db, ctx.despacho_id, canal, entrada.model_dump())
    registrar(ctx, "nomina.recibos.plantilla", "plantilla_recibo", canal, {"canal": canal})
    return _plantilla(plantillas.de_despacho(ctx.db, ctx.despacho_id, canal))


@router.post("/nomina/clientes/{cliente_id}/periodos/{periodo_id}/envios",
             response_model=EstadoEnviosResponse, responses=_ERR,
             summary="Enviar los recibos de una nómina cerrada (en segundo plano)")
def enviar(cliente_id: str, periodo_id: int, req: EnviarRequest,
           ctx: Contexto = Depends(contexto_actual)) -> EstadoEnviosResponse:
    cliente = cliente_o_404(ctx, cliente_id)
    periodo = srv.periodo_o_404(ctx.db, cliente, periodo_id)
    envios, omitidos = servicio.preparar(ctx.db, ctx.despacho_id, cliente, periodo, req.canal)
    if any(e.estado == "pendiente" for e in envios):
        servicio.encolar_envio(ctx.db, ctx.despacho_id, cliente, periodo, req.canal)
    registrar(ctx, "nomina.recibos.enviar", "nomina_periodo", periodo.id,
              {"canal": req.canal, "envios": len(envios), "omitidos": len(omitidos)}, cliente)
    return _estado(ctx, cliente, periodo, req.canal)


@router.get("/nomina/clientes/{cliente_id}/periodos/{periodo_id}/envios",
            response_model=EstadoEnviosResponse, responses=_ERR,
            summary="Estado del envío de recibos por canal")
def estado(cliente_id: str, periodo_id: int, canal: Canal = Query(default="correo"),
           ctx: Contexto = Depends(contexto_actual)) -> EstadoEnviosResponse:
    cliente = cliente_o_404(ctx, cliente_id)
    return _estado(ctx, cliente, srv.periodo_o_404(ctx.db, cliente, periodo_id), canal)


@router.post("/nomina/clientes/{cliente_id}/periodos/{periodo_id}/envios/{envio_id}/reenviar",
             response_model=EstadoEnviosResponse, responses=_ERR,
             summary="Reenviar un recibo (individual)")
def reenviar(cliente_id: str, periodo_id: int, envio_id: int,
             ctx: Contexto = Depends(contexto_actual)) -> EstadoEnviosResponse:
    cliente = cliente_o_404(ctx, cliente_id)
    periodo = srv.periodo_o_404(ctx.db, cliente, periodo_id)
    e = ctx.db.scalar(select(EnvioRecibo).where(EnvioRecibo.id == envio_id,
                                                EnvioRecibo.periodo_id == periodo.id))
    if e is None:
        raise FiscalAgentError(f"No existe el envío {envio_id} de este periodo.", 404)
    e.estado, e.intentos, e.error = "pendiente", 0, ""
    ctx.db.flush()
    servicio.encolar_envio(ctx.db, ctx.despacho_id, cliente, periodo, e.canal)
    registrar(ctx, "nomina.recibos.reenviar", "envio_recibo", e.id,
              {"canal": e.canal, "empleado_no": e.empleado_no}, cliente)
    return _estado(ctx, cliente, periodo, e.canal)


@router.post("/nomina/recibos/envios/rebote", response_model=EnvioSchema, responses=_ERR,
             summary="Marcar como rebotado un envío (aviso del proveedor u operador)")
def rebote(req: ReboteRequest, ctx: Contexto = Depends(contexto_actual)) -> EnvioSchema:
    e = ctx.db.scalar(select(EnvioRecibo).where(
        EnvioRecibo.despacho_id == ctx.despacho_id, EnvioRecibo.canal == req.canal,
        EnvioRecibo.id_mensaje == req.id_mensaje))
    if e is None:
        raise FiscalAgentError("No hay un envío con ese id de mensaje.", 404)
    e.estado, e.error = "rebotado", (req.motivo or "Rebotado por el proveedor.")[:500]
    ctx.db.flush()
    registrar(ctx, "nomina.recibos.rebote", "envio_recibo", e.id,
              {"canal": e.canal, "empleado_no": e.empleado_no})
    return EnvioSchema(id=e.id, empleado_no=e.empleado_no, destino=e.destino, estado=e.estado,
                       intentos=e.intentos, error=e.error, timbrado=e.timbrado,
                       enviado_en=e.enviado_en)


@router_publico.get("/recibos/descarga/{envio_id}/{archivo}",
                    responses={404: {"model": ErrorResponse}},
                    summary="Descarga del recibo para WhatsApp (enlace firmado, sin sesión)")
def descargar(envio_id: int, archivo: str, vence: int = Query(), firma: str = Query(),
              db: Session = Depends(obtener_db)) -> Response:
    no_existe = FiscalAgentError("No existe el documento.", 404)
    if not enlaces.verificar(envio_id, archivo, vence, firma):
        raise no_existe
    e = db.get(EnvioRecibo, envio_id)
    if e is None:
        raise no_existe
    recibo, periodo = db.get(ReciboNomina, e.recibo_id), db.get(NominaPeriodo, e.periodo_id)
    cliente = db.get(Cliente, e.cliente_id)
    if recibo is None or periodo is None or cliente is None:
        raise no_existe
    docs = documentos_del_recibo(db, cliente, periodo, recibo)
    contenido = docs.pdf if archivo == "recibo.pdf" else docs.xml
    if contenido is None:
        raise no_existe
    mime = "application/pdf" if archivo == "recibo.pdf" else "application/xml"
    return Response(contenido, media_type=mime, headers={
        "Content-Disposition": f'attachment; filename="{docs.nombre_base}.{archivo[-3:]}"'})
