"""
Logging estructurado (JSON, una línea por evento) para API, worker y programador.

EL CONTEXTO VIAJA EN UN `ContextVar` (P6-02)
--------------------------------------------
Cada línea lleva, además del mensaje, lo que haga falta para seguirle la pista: en la API el
`request_id` (del encabezado `X-Request-ID` o uno nuevo) y el `despacho_id` en cuanto
`contexto_actual` sabe quién es; en el worker el `trabajo_id`, su `tipo`, `despacho_id` e
`intento`; en el programador la `tarea`. Se pone con `con_contexto(...)` (un `with`) o con
`anotar(...)` para agregar campos a lo que ya hay, y el formateador los mezcla en cada línea
sin que el código que loggea tenga que saber nada.

`proceso` dice quién escribe (`api`, `worker`, `programador`) para filtrar en Railway.
"""

from __future__ import annotations

import json
import logging
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any

# El valor es un dict que se MUTA en sitio (`anotar`), no se reemplaza: FastAPI corre las
# dependencias y los endpoints síncronos en hilos con una COPIA del contexto, y un `.set()`
# dentro de la dependencia no llegaría al endpoint; mutar el mismo dict sí (es el mismo truco
# que `EstadoAuditoria` en `app/auditoria.py`).
_CONTEXTO: ContextVar[dict[str, Any] | None] = ContextVar("log_contexto", default=None)
_PROCESO = "api"


def contexto_log() -> dict[str, Any]:
    """Los campos que llevan ahora mismo todas las líneas de log (copia)."""
    return dict(_CONTEXTO.get() or {})


def anotar(**campos: Any) -> None:
    """Agrega campos al contexto vigente (p. ej. el despacho cuando ya se sabe)."""
    actual = _CONTEXTO.get()
    if actual is None:
        actual = {}
        _CONTEXTO.set(actual)
    actual.update({k: v for k, v in campos.items() if v is not None})


@contextmanager
def con_contexto(**campos: Any) -> Iterator[None]:
    """Las líneas de log dentro del `with` llevan `campos`; al salir se restaura lo anterior."""
    nuevo = dict(_CONTEXTO.get() or {})
    nuevo.update({k: v for k, v in campos.items() if v is not None})
    token = _CONTEXTO.set(nuevo)
    try:
        yield
    finally:
        _CONTEXTO.reset(token)


class JSONFormatter(logging.Formatter):
    """Formateador que emite registros de log en formato JSON estructurado."""

    def format(self, record: logging.LogRecord) -> str:
        """Convierte un LogRecord a una linea JSON estructurada."""
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "proceso": _PROCESO,
            "message": record.getMessage(),
        }
        contexto = _CONTEXTO.get()
        if contexto:
            log_entry.update(contexto)
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)
        if hasattr(record, "extra_data"):
            log_entry["data"] = record.extra_data
        return json.dumps(log_entry, ensure_ascii=False, default=str)


def setup_logging(level: int = logging.INFO, proceso: str = "api") -> None:
    """Inicializa el logging estructurado para toda la aplicacion."""
    global _PROCESO
    _PROCESO = proceso
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Evitar duplicar handlers si se llama mas de una vez
    if root_logger.handlers:
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    root_logger.addHandler(handler)

    # Reducir ruido de librerias externas
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
