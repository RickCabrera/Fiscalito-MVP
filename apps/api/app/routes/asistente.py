"""
Asistente IA del despacho (P5-07, absorbe S-00): chat con herramientas y voz, sin llave en el
navegador.

- `POST /asistente/turno`: un turno del chat (ver `app/asistente/turno.py`).
- `POST /asistente/transcribir`: audio crudo en el cuerpo (`Content-Type: audio/webm`, …) →
  texto. Sin multipart: el tope de tamaño se aplica al leer el flujo, antes de juntar todo.
- `POST /asistente/hablar`: `{texto}` → `audio/mpeg`.

Todo va por `contexto_actual` (sesión de Firebase, `PROTEGIDO` en `main.py`) y cada llamada al
proveedor pasa por `cobrador.cobrar()`: límite por minuto del usuario y tope diario del
despacho (P0-02). El cliente activo se resuelve con `cliente_o_404`: uno de otro despacho, o
no asignado a un auxiliar, es 404.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response

from app.acceso.llm import ZONA, CobradorLLM, cobrador_llm
from app.asistente import turno
from app.exceptions import FiscalAgentError
from app.integraciones import registro
from app.integraciones.voz import EXTENSIONES
from app.schemas.asistente import (
    HablarRequest,
    TranscripcionResponse,
    TurnoRequest,
    TurnoResponse,
)
from app.schemas.declaraciones import ErrorResponse
from app.tenancy import Contexto, cliente_o_404, contexto_actual

router = APIRouter(prefix="/asistente", tags=["Asistente IA"])
_ERR = {401: {"model": ErrorResponse}, 404: {"model": ErrorResponse},
        413: {"model": ErrorResponse}, 415: {"model": ErrorResponse},
        422: {"model": ErrorResponse}, 429: {"model": ErrorResponse}}

MAX_AUDIO_BYTES = 8 * 1024 * 1024


@router.post("/turno", response_model=TurnoResponse, responses=_ERR,
             summary="Un turno del asistente (herramientas de servidor y de navegador)")
def turno_asistente(
    req: TurnoRequest, ctx: Contexto = Depends(contexto_actual),
    cobrador: CobradorLLM = Depends(cobrador_llm),
) -> TurnoResponse:
    cliente = cliente_o_404(ctx, req.cliente) if req.cliente else None
    hoy = datetime.now(ZONA).date()
    salida = turno.correr(ctx.db, registro.obtener("llm"), cobrador.cobrar, req, ctx.uid,
                          cliente, hoy)
    return TurnoResponse(**salida)


def _tipo_base(request: Request) -> str:
    """`audio/webm;codecs=opus` → `audio/webm` (es lo que produce `MediaRecorder`)."""
    return request.headers.get("content-type", "").split(";")[0].strip().lower()


@router.post("/transcribir", response_model=TranscripcionResponse, responses=_ERR,
             summary="Voz a texto (audio crudo en el cuerpo)")
async def transcribir(
    request: Request, ctx: Contexto = Depends(contexto_actual),
    cobrador: CobradorLLM = Depends(cobrador_llm),
) -> TranscripcionResponse:
    mime = _tipo_base(request)
    if mime not in EXTENSIONES:
        raise FiscalAgentError(
            f"Formato de audio no admitido: usa uno de {', '.join(sorted(EXTENSIONES))}.", 415)
    largo = request.headers.get("content-length", "")
    if largo.isdigit() and int(largo) > MAX_AUDIO_BYTES:
        raise FiscalAgentError("El audio pasa de 8 MB.", 413)
    partes: list[bytes] = []
    recibidos = 0
    async for trozo in request.stream():  # también corta un envío `chunked` sin largo
        recibidos += len(trozo)
        if recibidos > MAX_AUDIO_BYTES:
            raise FiscalAgentError("El audio pasa de 8 MB.", 413)
        partes.append(trozo)
    audio = b"".join(partes)
    if not audio:
        raise FiscalAgentError("No llegó audio.", 422)
    await run_in_threadpool(cobrador.cobrar)
    texto = await run_in_threadpool(registro.obtener("voz").transcribir, audio, mime)
    return TranscripcionResponse(texto=texto)


@router.post("/hablar", responses={**_ERR, 200: {"content": {"audio/mpeg": {}}}},
             response_class=Response, summary="Texto a voz (MP3)")
def hablar(
    req: HablarRequest, ctx: Contexto = Depends(contexto_actual),
    cobrador: CobradorLLM = Depends(cobrador_llm),
) -> Response:
    cobrador.cobrar()
    audio = registro.obtener("voz").sintetizar(req.texto)
    return Response(content=audio, media_type="audio/mpeg")
