"""
Observabilidad (P6-02): request_id por petición, errores al monitoreo, latidos de los procesos.

TRES PIEZAS
-----------
1. `ObservabilidadMiddleware` (ASGI puro, para que el `ContextVar` llegue a la ruta): toma el
   `X-Request-ID` que mande el proxy o genera uno, lo pone en el contexto de log y lo devuelve
   en la respuesta; al terminar deja una línea `HTTP <método> <ruta> -> <status> (<ms>)`.
2. `reportar_error(exc, **contexto)`: manda la excepción al adaptador `monitoreo` con su
   contexto (request, trabajo, despacho, intento, traza). NUNCA lanza: un monitoreo caído no
   puede tumbar la ruta ni el worker que lo llamó. Lo usan la cola (`app/trabajos/cola.py`),
   el programador y el manejador global de `app/main.py`.
3. `latir(sesionador, proceso)`: el worker y el programador anotan "sigo vivo" en
   `ejecuciones_programadas` (renglón `latido:<proceso>`); `GET /health` lo lee.
"""

from __future__ import annotations

import logging
import time
import traceback
import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.db.base import ahora as _ahora
from app.logging_config import con_contexto, contexto_log
from app.modelos.trabajos import EjecucionProgramada, Trabajo

logger = logging.getLogger(__name__)

ENCABEZADO_REQUEST_ID = "x-request-id"
# Un proceso que no late en este tiempo se da por caído en `/health`.
MINUTOS_SIN_LATIDO = 5
# Un `pendiente` vencido hace más de esto sin que nadie lo tome = el worker no está corriendo.
MINUTOS_ATORADO = 15
PREFIJO_LATIDO = "latido:"


def _monitoreo() -> Any:
    from app.integraciones import registro

    return registro.obtener("monitoreo")


def reportar_error(error: BaseException, **contexto: Any) -> None:
    """Manda `error` al monitoreo con `contexto` + el contexto de log vigente. Nunca lanza."""
    datos: dict[str, Any] = dict(contexto_log())
    datos.update({k: v for k, v in contexto.items() if v is not None})
    datos.setdefault("tipo_error", type(error).__name__)
    traza = traceback.format_exception(type(error), error, error.__traceback__)
    datos.setdefault("traza", "".join(traza)[-4000:])
    try:
        _monitoreo().capturar_error(error, datos)
    except Exception:  # noqa: BLE001 — el monitoreo no puede tumbar a quien lo llama
        logger.exception("No se pudo reportar el error al monitoreo")


def reportar_mensaje(mensaje: str, nivel: str = "info", **contexto: Any) -> None:
    """Un aviso (no una excepción) al monitoreo, con contexto. Nunca lanza."""
    datos: dict[str, Any] = dict(contexto_log())
    datos.update({k: v for k, v in contexto.items() if v is not None})
    try:
        _monitoreo().capturar_mensaje(mensaje, nivel, datos)
    except Exception:  # noqa: BLE001
        logger.exception("No se pudo reportar el mensaje al monitoreo")


class ObservabilidadMiddleware:
    """request_id en el contexto de log y en la respuesta; una línea por request."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request_id = ""
        for nombre, valor in scope.get("headers") or []:
            if nombre == ENCABEZADO_REQUEST_ID.encode():
                request_id = valor.decode("latin-1").strip()[:64]
        request_id = request_id or uuid.uuid4().hex
        metodo, ruta = scope.get("method", ""), scope.get("path", "")
        status = 500
        inicio = time.perf_counter()

        async def _send(mensaje: Message) -> None:
            nonlocal status
            if mensaje["type"] == "http.response.start":
                status = int(mensaje["status"])
                encabezados = list(mensaje.get("headers") or [])
                encabezados.append((ENCABEZADO_REQUEST_ID.encode(), request_id.encode()))
                mensaje = {**mensaje, "headers": encabezados}
            await send(mensaje)

        with con_contexto(request_id=request_id):
            try:
                await self.app(scope, receive, _send)
            except Exception as exc:
                # Aquí todavía hay contexto (request_id, despacho); afuera ya no.
                reportar_error(exc, origen="ruta", metodo=metodo, ruta=ruta)
                try:
                    exc._fiscalito_reportado = True  # type: ignore[attr-defined]
                except Exception:  # noqa: BLE001 — excepciones con __slots__
                    pass
                raise
            finally:
                ms = (time.perf_counter() - inicio) * 1000
                logger.info("HTTP %s %s -> %d (%.1fms)", metodo, ruta, status, ms)


# ── Latidos y salud de worker/programador ───────────────────────────────────


def latir(sesionador: sessionmaker, proceso: str, *, ahora: datetime | None = None) -> None:
    """Anota que `proceso` (worker | programador) sigue vivo."""
    momento = ahora or _ahora()
    nombre = f"{PREFIJO_LATIDO}{proceso}"
    with sesionador() as db:
        fila = db.get(EjecucionProgramada, nombre)
        if fila is None:
            db.add(EjecucionProgramada(nombre=nombre, ultima_ejecucion=momento))
        else:
            fila.ultima_ejecucion = momento
        db.commit()


def salud_procesos(db: Session, *, ahora: datetime | None = None) -> dict[str, Any]:
    """Último latido de worker y programador, trabajos atorados y si todo está sano."""
    momento = ahora or _ahora()
    latidos: dict[str, dict[str, Any]] = {}
    for proceso in ("worker", "programador"):
        fila = db.get(EjecucionProgramada, f"{PREFIJO_LATIDO}{proceso}")
        ultimo = fila.ultima_ejecucion if fila is not None else None
        vivo = ultimo is not None and momento - ultimo <= timedelta(minutes=MINUTOS_SIN_LATIDO)
        latidos[proceso] = {
            "ultimo_latido": ultimo.isoformat() if ultimo else None,
            "vivo": vivo,
        }
    from app.trabajos.cola import MINUTOS_HUERFANO

    corriendo_viejos = db.scalar(
        select(func.count()).select_from(Trabajo).where(
            Trabajo.estado == "corriendo",
            Trabajo.iniciado_en < momento - timedelta(minutes=MINUTOS_HUERFANO),
        )
    ) or 0
    pendientes_viejos = db.scalar(
        select(func.count()).select_from(Trabajo).where(
            Trabajo.estado == "pendiente",
            Trabajo.ejecutar_en < momento - timedelta(minutes=MINUTOS_ATORADO),
        )
    ) or 0
    fallidos = db.scalar(
        select(func.count()).select_from(Trabajo).where(Trabajo.estado == "fallido")
    ) or 0
    atorados = int(corriendo_viejos) + int(pendientes_viejos)
    return {
        "worker": latidos["worker"],
        "programador": latidos["programador"],
        "trabajos": {
            "corriendo_sin_terminar": int(corriendo_viejos),
            "pendientes_sin_tomar": int(pendientes_viejos),
            "fallidos": int(fallidos),
            "atorados": atorados,
        },
        "sano": latidos["worker"]["vivo"] and latidos["programador"]["vivo"] and atorados == 0,
    }


def main(argv: list[str] | None = None) -> int:
    """
    `python -m app.observabilidad <worker|programador>`: exit 0 si ese proceso latió en los
    últimos MINUTOS_SIN_LATIDO minutos. Es el healthcheck del contenedor del worker y del
    programador (docker compose); la API usa `GET /health`.
    """
    import sys

    from app.db.session import SesionLocal

    args = sys.argv[1:] if argv is None else argv
    proceso = args[0] if args else "worker"
    with SesionLocal() as db:
        vivo = bool(salud_procesos(db)[proceso]["vivo"])
    print(f"{proceso}: {'vivo' if vivo else 'sin latido reciente'}")
    return 0 if vivo else 1


if __name__ == "__main__":
    raise SystemExit(main())
