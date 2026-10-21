"""
Envío de documentos al cliente (P5-05). Contrato: `docs/api-contract.md` §"Envío de documentos
al cliente".

Todo cuelga de `/clientes/{clave}/...` con `cliente_o_404`: contactos (con consentimiento de
WhatsApp), expediente subido (declaraciones, acuses), catálogo de documentos enviables, envío
en segundo plano (`documentos.enviar`) con estado y reenvío. La descarga para WhatsApp es la
única ruta pública, con enlace firmado (ámbito `documentos` de `nomina_envio.enlaces`).
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

import app.envio_documentos.trabajos  # noqa: F401 — registra el manejador
from app.db.session import obtener_db
from app.envio_documentos import documentos, servicio
from app.exceptions import FiscalAgentError
from app.modelos.envio_documentos import EnvioDocumento
from app.modelos.nucleo import Cliente
from app.nomina_envio import enlaces
from app.tenancy import Contexto, cliente_o_404, contexto_actual

router = APIRouter(prefix="/clientes/{clave}", tags=["Envío de documentos"])
router_publico = APIRouter(tags=["Envío de documentos"])


class ContactoIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=200)
    puesto: str = Field("", max_length=120)
    correo: str = Field("", max_length=320, pattern=r"^([^@\s]+@[^@\s]+\.[^@\s]+)?$")
    telefono: str = Field("", max_length=20)
    consentimiento_whatsapp: bool = False
    activo: bool = True


class DocumentoRef(BaseModel):
    tipo: Literal["factura", "cfdi", "retencion", "opinion", "constancia", "declaracion",
                  "acuse", "otro", "recibo_nomina"]
    ref: str = Field(min_length=1, max_length=40)


class EnviarIn(BaseModel):
    documentos: list[DocumentoRef] = Field(min_length=1, max_length=20)
    canales: list[Literal["correo", "whatsapp"]] = Field(min_length=1, max_length=2)
    contactos: list[int] = Field(min_length=1, max_length=20)
    mensaje: str = Field("", max_length=2000)


def _estado(ctx: Contexto, cliente: Cliente) -> dict[str, Any]:
    t = servicio.ultimo_trabajo(ctx.db, cliente)
    lista = servicio.envios(ctx.db, cliente)
    resumen: dict[str, int] = {}
    for e in lista:
        resumen[e.estado] = resumen.get(e.estado, 0) + 1
    return {"exito": True, "envios": [servicio.envio_json(e) for e in lista],
            "resumen": resumen,
            "trabajo": {"id": t.id, "estado": t.estado, "error": t.error}
            if t is not None else None}


@router.get("/contactos", summary="Contactos del cliente")
def listar_contactos(clave: str, ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    cliente = cliente_o_404(ctx, clave)
    return {"exito": True, "contactos": [servicio.contacto_json(c)
                                         for c in servicio.contactos(ctx.db, cliente)]}


@router.post("/contactos", summary="Agregar un contacto (con consentimiento de WhatsApp)")
def crear_contacto(clave: str, cuerpo: ContactoIn,
                   ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    c = servicio.guardar_contacto(ctx, cliente_o_404(ctx, clave), cuerpo.model_dump())
    return {"exito": True, "contacto": servicio.contacto_json(c)}


@router.put("/contactos/{contacto_id}", summary="Editar un contacto")
def editar_contacto(clave: str, contacto_id: int, cuerpo: ContactoIn,
                    ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    c = servicio.guardar_contacto(ctx, cliente_o_404(ctx, clave), cuerpo.model_dump(),
                                  contacto_id)
    return {"exito": True, "contacto": servicio.contacto_json(c)}


@router.delete("/contactos/{contacto_id}", summary="Borrar un contacto")
def borrar_contacto(clave: str, contacto_id: int,
                    ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    servicio.borrar_contacto(ctx, cliente_o_404(ctx, clave), contacto_id)
    return {"exito": True}


@router.post("/expediente", summary="Subir una declaración, acuse u otro PDF/XML")
async def subir(clave: str, tipo: Literal["declaracion", "acuse", "otro"] = Form(...),
                descripcion: str = Form(""), periodo: str = Form(""),
                archivo: UploadFile = File(...),
                ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    cliente = cliente_o_404(ctx, clave)
    contenido = await archivo.read(servicio.TAMANO_MAXIMO + 1)
    d = servicio.subir(ctx, cliente, tipo, descripcion, periodo, archivo.filename or "",
                       archivo.content_type or "", contenido)
    return {"exito": True, "documento": {"tipo": d.tipo, "ref": str(d.id),
                                         "descripcion": d.descripcion or d.nombre_archivo}}


@router.get("/documentos-enviables", summary="Documentos del cliente que se pueden enviar")
def enviables(clave: str, ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    cliente = cliente_o_404(ctx, clave)
    return {"exito": True, "documentos": documentos.enviables(ctx.db, cliente)}


@router.get("/documentos/{tipo}/{ref}/{indice}", summary="Descargar un archivo de un documento")
def descargar(clave: str, tipo: str, ref: str, indice: int,
              ctx: Contexto = Depends(contexto_actual)) -> Response:
    p = documentos.paquete(ctx.db, cliente_o_404(ctx, clave), tipo, ref)
    if not 0 <= indice < len(p.archivos):
        raise FiscalAgentError("No existe ese archivo.", 404)
    a = p.archivos[indice]
    return Response(a.contenido, media_type=a.mime,
                    headers={"Content-Disposition": f'attachment; filename="{a.nombre}"'})


@router.post("/envios", summary="Enviar documentos por correo y/o WhatsApp (segundo plano)")
def enviar(clave: str, cuerpo: EnviarIn,
           ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    cliente = cliente_o_404(ctx, clave)
    _, omitidos, _ = servicio.preparar(ctx, cliente, [(d.tipo, d.ref) for d in cuerpo.documentos],
                                       list(cuerpo.canales), cuerpo.contactos, cuerpo.mensaje)
    return {**_estado(ctx, cliente),
            "omitidos": [{"contacto": o.contacto, "canal": o.canal, "motivo": o.motivo}
                         for o in omitidos]}


@router.get("/envios", summary="Estado de los envíos de documentos del cliente")
def estado(clave: str, ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    return _estado(ctx, cliente_o_404(ctx, clave))


@router.post("/envios/{envio_id}/reenviar", summary="Reenviar un documento")
def reenviar(clave: str, envio_id: int,
             ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    cliente = cliente_o_404(ctx, clave)
    servicio.reenviar(ctx, cliente, envio_id)
    return _estado(ctx, cliente)


@router_publico.get("/documentos/descarga/{envio_id}/{archivo}",
                    summary="Descarga del documento para WhatsApp (enlace firmado, sin sesión)")
def descarga_publica(envio_id: int, archivo: str, vence: int = Query(),
                     firma: str = Query(), db: Session = Depends(obtener_db)) -> Response:
    no_existe = FiscalAgentError("No existe el documento.", 404)
    if not enlaces.verificar(envio_id, archivo, vence, firma, ambito="documentos"):
        raise no_existe
    e = db.get(EnvioDocumento, envio_id)
    cliente = db.get(Cliente, e.cliente_id) if e is not None else None
    if e is None or cliente is None:
        raise no_existe
    p = documentos.paquete(db, cliente, e.tipo_documento, e.ref)
    a = p.de_tipo(documentos.PDF if archivo == "documento.pdf" else documentos.XML)
    if a is None:
        raise no_existe
    return Response(a.contenido, media_type=a.mime,
                    headers={"Content-Disposition": f'attachment; filename="{a.nombre}"'})
