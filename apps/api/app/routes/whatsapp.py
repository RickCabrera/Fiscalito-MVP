"""
Bot de WhatsApp del despacho (P5-06).

Protegidas (sesión de Firebase + `cliente_o_404`):
- `GET/POST /whatsapp/clientes/{clave}/contactos`, `DELETE .../contactos/{id}`: los números
  que pueden pedir documentos del cliente (con consentimiento expreso).
- `GET /whatsapp/clientes/{clave}/conversacion`: la bitácora.

Públicas (`router_publico`, declaradas en `RUTAS_PUBLICAS`), cada una con su verificación:
- `GET /whatsapp/webhook`: verificación de suscripción de Meta (`hub.verify_token`).
- `POST /whatsapp/webhook`: mensajes entrantes; firma del proveedor (`X-Hub-Signature-256` de
  Meta o `X-Twilio-Signature`) verificada por el adaptador ANTES de leer nada. Sin firma
  válida → 401 y no se anota nada.
- `GET /whatsapp/documentos/{mensaje_id}/{archivo}`: enlace firmado con vigencia (como los
  recibos de P4-13).
"""

from __future__ import annotations

import hmac
import os
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import PlainTextResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

import app.whatsapp_bot.trabajos  # noqa: F401 — registra el manejador
from app.db.session import obtener_db
from app.exceptions import FiscalAgentError
from app.integraciones import registro
from app.schemas.declaraciones import ErrorResponse
from app.tenancy import ROLES_CONTABLES, Contexto, cliente_o_404, contexto_actual, exigir_rol
from app.whatsapp_bot import enlaces, servicio

router = APIRouter(prefix="/whatsapp", tags=["WhatsApp — bot"])
router_publico = APIRouter(prefix="/whatsapp", tags=["WhatsApp — bot"])
_ERR = {401: {"model": ErrorResponse}, 403: {"model": ErrorResponse},
        404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}}


class ContactoEntrada(BaseModel):
    telefono: str = Field(min_length=10, max_length=20, description="+52 y 10 dígitos")
    nombre: str = Field(default="", max_length=200)
    consentimiento: Literal[True] = Field(
        description="El titular aceptó recibir por WhatsApp sus documentos fiscales (LFPDPPP). "
                    "Sin esto no se registra.")


@router.get("/clientes/{clave}/contactos", responses=_ERR, summary="Contactos de WhatsApp")
def listar_contactos(clave: str, ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    cliente = cliente_o_404(ctx, clave)
    return {"exito": True, "contactos": [servicio.contacto_json(c)
                                         for c in servicio.contactos(ctx.db, cliente)]}


@router.post("/clientes/{clave}/contactos", responses=_ERR,
             summary="Registrar un número con consentimiento")
def registrar_contacto(clave: str, entrada: ContactoEntrada,
                       ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    cliente = cliente_o_404(ctx, clave)
    exigir_rol(ctx, *ROLES_CONTABLES)
    c = servicio.registrar_contacto(ctx.db, cliente, entrada.telefono, entrada.nombre, ctx.uid)
    return {"exito": True, "contacto": servicio.contacto_json(c)}


@router.delete("/clientes/{clave}/contactos/{contacto_id}", responses=_ERR,
               summary="Dar de baja un número")
def baja_contacto(clave: str, contacto_id: int,
                  ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    cliente = cliente_o_404(ctx, clave)
    exigir_rol(ctx, *ROLES_CONTABLES)
    servicio.desactivar_contacto(ctx.db, cliente, contacto_id)
    return {"exito": True, "id": contacto_id}


@router.get("/clientes/{clave}/conversacion", responses=_ERR,
            summary="Bitácora de la conversación del bot con el cliente")
def conversacion(clave: str, limite: int = Query(200, ge=1, le=1000),
                 ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    cliente = cliente_o_404(ctx, clave)
    return {"exito": True, "mensajes": servicio.conversacion(ctx.db, cliente, limite)}


# ── Públicas ──


@router_publico.get("/webhook", response_class=PlainTextResponse, responses=_ERR,
                    summary="Verificación de la suscripción del webhook (Meta)")
def verificar_suscripcion(
    modo: str = Query("", alias="hub.mode"), token: str = Query("", alias="hub.verify_token"),
    reto: str = Query("", alias="hub.challenge", max_length=200),
) -> PlainTextResponse:
    esperado = os.environ.get("FISCALITO_WHATSAPP_VERIFY_TOKEN", "").strip()
    if not esperado or modo != "subscribe" or not hmac.compare_digest(token, esperado):
        raise FiscalAgentError("Verificación inválida.", 403)
    return PlainTextResponse(reto)


def _url_publica(request: Request) -> str:
    """La URL con la que el proveedor llamó (Twilio firma sobre ella)."""
    base = os.environ.get("FISCALITO_URL_PUBLICA_API", "").rstrip("/")
    return f"{base}{request.url.path}" if base else str(request.url)


@router_publico.post("/webhook", responses=_ERR, summary="Mensajes entrantes del bot")
async def webhook(request: Request, db: Session = Depends(obtener_db)) -> dict[str, Any]:
    cuerpo = await request.body()
    wa = registro.obtener("whatsapp")
    if not wa.verificar_firma_webhook(cuerpo, dict(request.headers), _url_publica(request)):
        raise FiscalAgentError("Firma inválida.", 401)
    try:
        mensajes = wa.parsear_webhook(cuerpo, dict(request.headers))
    except ValueError as exc:  # JSON roto con firma válida: no reintentar en bucle
        raise FiscalAgentError("Cuerpo ilegible.", 422) from exc
    return {"exito": True, **await run_in_threadpool(servicio.recibir, db, mensajes)}


@router_publico.get("/documentos/{mensaje_id}/{archivo}", responses=_ERR,
                    summary="Descarga del documento entregado por el bot (enlace firmado)")
def descargar(mensaje_id: int, archivo: str, vence: int = Query(), firma: str = Query(),
              db: Session = Depends(obtener_db)) -> Response:
    if not enlaces.verificar(mensaje_id, archivo, vence, firma):
        raise FiscalAgentError("No existe el documento.", 404)
    contenido, tipo = servicio.documento_entregado(db, mensaje_id, archivo)
    return Response(content=contenido, media_type=tipo,
                    headers={"Content-Disposition": f'attachment; filename="{archivo}"'})
