"""
Bitácora de auditoría (P0-07): quién hizo qué, a qué cliente y cuándo.

DOS CAMINOS, UNA BITÁCORA
-------------------------
1. **Explícito** — `registrar(ctx, "trabajo.reintentar", "trabajo", id, {...}, cliente)`
   desde la ruta. Va en la MISMA transacción que el cambio: si el cambio se revierte, el
   renglón también. Es el que dice QUÉ pasó con palabras del dominio.
2. **Red de seguridad** — `AuditoriaMiddleware` deja un renglón `http.<MÉTODO>` por cada
   POST/PUT/PATCH/DELETE autenticado, con ruta y status, cuando la ruta no registró nada
   (o cuando falló: entonces el renglón explícito se revirtió con todo lo demás y el del
   middleware es el que deja constancia del intento). Una ruta nueva que olvide auditar
   igual queda en la bitácora.

CÓMO SABE EL MIDDLEWARE QUIÉN FUE
---------------------------------
El middleware no verifica tokens: pone un `EstadoAuditoria` vacío en un `ContextVar` al
empezar el request, y `contexto_actual` (`app/tenancy.py`) lo llena con uid y despacho;
`cliente_o_404` le agrega el cliente. Un request sin `contexto_actual` (abierto, o de un
router que todavía no migra a la tenencia) no deja renglón: no hay a quién atribuirlo.
"""

from __future__ import annotations

import logging
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.modelos.auditoria import EventoAuditoria

if TYPE_CHECKING:
    from app.modelos.nucleo import Cliente
    from app.tenancy import Contexto

logger = logging.getLogger(__name__)

METODOS_QUE_ESCRIBEN = frozenset({"POST", "PUT", "PATCH", "DELETE"})


@dataclass
class EstadoAuditoria:
    """Lo que el request va sabiendo de sí mismo, para el renglón del middleware."""

    metodo: str
    ruta: str
    ip: str
    uid: str | None = None
    despacho_id: str | None = None
    cliente_id: int | None = None
    cliente_clave: str | None = None
    motor: Engine | None = None
    registrados: int = 0
    extra: dict[str, Any] = field(default_factory=dict)


_ACTUAL: ContextVar[EstadoAuditoria | None] = ContextVar("auditoria_actual", default=None)


def estado_actual() -> EstadoAuditoria | None:
    """El estado del request en curso (None fuera de un request que escribe)."""
    return _ACTUAL.get()


def anotar_contexto(uid: str, despacho_id: str, db: Session) -> None:
    """Lo llama `contexto_actual`: deja dicho quién es y con qué base habla."""
    estado = _ACTUAL.get()
    if estado is not None:
        estado.uid, estado.despacho_id = uid, despacho_id
        estado.motor = db.get_bind()  # type: ignore[assignment]


def anotar_cliente(cliente: Cliente) -> None:
    """Lo llama `cliente_o_404`: el cliente sobre el que actúa el request."""
    estado = _ACTUAL.get()
    if estado is not None:
        estado.cliente_id, estado.cliente_clave = cliente.id, cliente.clave


def registrar(
    ctx: Contexto,
    accion: str,
    entidad: str = "",
    entidad_id: str | int = "",
    detalle: dict[str, Any] | None = None,
    cliente: Cliente | None = None,
) -> EventoAuditoria:
    """Agrega un renglón a la bitácora dentro de la transacción del request (sin commit)."""
    estado = _ACTUAL.get()
    if cliente is None and estado is not None and estado.cliente_id is not None:
        cliente_id, cliente_clave = estado.cliente_id, estado.cliente_clave
    else:
        cliente_id = cliente.id if cliente is not None else None
        cliente_clave = cliente.clave if cliente is not None else None
    evento = EventoAuditoria(
        despacho_id=ctx.despacho_id,
        uid=ctx.uid,
        cliente_id=cliente_id,
        cliente_clave=cliente_clave,
        accion=accion,
        entidad=entidad,
        entidad_id=str(entidad_id),
        detalle=dict(detalle or {}),
        ip=estado.ip if estado is not None else "",
    )
    ctx.db.add(evento)
    ctx.db.flush()
    if estado is not None:
        estado.registrados += 1
    return evento


def _ip(scope: Scope) -> str:
    """IP del cliente. Detrás del proxy de Railway, el primer X-Forwarded-For."""
    for nombre, valor in scope.get("headers") or []:
        if nombre == b"x-forwarded-for":
            return valor.decode("latin-1").split(",")[0].strip()[:64]
    cliente = scope.get("client")
    return str(cliente[0])[:64] if cliente else ""


def _escribir_red(estado: EstadoAuditoria, status: int) -> None:
    """El renglón `http.<MÉTODO>` del middleware, en su propia sesión."""
    if estado.motor is None or estado.uid is None or estado.despacho_id is None:
        return
    with Session(bind=estado.motor) as db:
        db.add(
            EventoAuditoria(
                despacho_id=estado.despacho_id,
                uid=estado.uid,
                cliente_id=estado.cliente_id,
                cliente_clave=estado.cliente_clave,
                accion=f"http.{estado.metodo}",
                entidad="ruta",
                entidad_id=estado.ruta[:200],
                detalle={"metodo": estado.metodo, "ruta": estado.ruta, "status": status},
                ip=estado.ip,
            )
        )
        db.commit()


class AuditoriaMiddleware:
    """ASGI puro (no `BaseHTTPMiddleware`): el `ContextVar` llega intacto a la ruta."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("method") not in METODOS_QUE_ESCRIBEN:
            await self.app(scope, receive, send)
            return
        estado = EstadoAuditoria(metodo=scope["method"], ruta=scope.get("path", ""), ip=_ip(scope))
        status = 500

        async def _send(mensaje: Message) -> None:
            nonlocal status
            if mensaje["type"] == "http.response.start":
                status = int(mensaje["status"])
            await send(mensaje)

        token = _ACTUAL.set(estado)
        try:
            await self.app(scope, receive, _send)
        finally:
            _ACTUAL.reset(token)
            # Éxito con renglón explícito: ya quedó, y mejor contado. Si no, la red.
            if not (estado.registrados and status < 400):
                try:
                    await run_in_threadpool(_escribir_red, estado, status)
                except Exception:  # noqa: BLE001 — la respuesta ya salió; queda en el log
                    logger.exception(
                        "No se pudo escribir la auditoría de %s %s", estado.metodo, estado.ruta
                    )
