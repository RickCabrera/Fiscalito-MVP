"""
Monitoreo de errores (P0-06). `FISCALITO_MONITOREO` = falso | log | sentry.

- `falso`: guarda en memoria (tests).
- `log`: manda al logger estándar (lo que Railway/Cloud Run ya recolectan).
- `sentry`: usa `sentry-sdk` si está instalado. No es dependencia del proyecto: para
  activarlo, `pip install sentry-sdk` (o agrégalo a `pyproject.toml`) y define
  `FISCALITO_SENTRY_DSN`. Sin el paquete, la fábrica explica eso con un 503.
"""

import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.integraciones import registro
from app.integraciones.comun import ServicioNoConfigurado, env

logger = logging.getLogger("fiscalito.monitoreo")


class Monitoreo(Protocol):
    def capturar_error(
        self, error: BaseException, contexto: Mapping[str, Any] | None = None
    ) -> None: ...
    def capturar_mensaje(
        self, mensaje: str, nivel: str = "info", contexto: Mapping[str, Any] | None = None
    ) -> None: ...


@dataclass
class MonitoreoFalso:
    eventos: list[dict[str, Any]] = field(default_factory=list)

    def capturar_error(self, error, contexto=None):
        self.eventos.append({"tipo": "error", "error": error, "contexto": dict(contexto or {})})

    def capturar_mensaje(self, mensaje, nivel="info", contexto=None):
        self.eventos.append({"tipo": "mensaje", "mensaje": mensaje, "nivel": nivel,
                             "contexto": dict(contexto or {})})


class MonitoreoLog:
    def capturar_error(self, error, contexto=None):
        logger.error("Error capturado: %s | %s", error, dict(contexto or {}), exc_info=error)

    def capturar_mensaje(self, mensaje, nivel="info", contexto=None):
        niveles = {"debug": logging.DEBUG, "info": logging.INFO, "warning": logging.WARNING,
                   "error": logging.ERROR, "fatal": logging.CRITICAL}
        logger.log(niveles.get(nivel.lower(), logging.INFO), "%s | %s", mensaje,
                   dict(contexto or {}))


class MonitoreoSentry:
    """Envoltura sobre `sentry_sdk` (se inyecta para poder probarla sin red)."""

    def __init__(self, dsn: str, entorno: str, sdk: Any = None) -> None:
        if sdk is None:
            try:
                import sentry_sdk as sdk  # type: ignore[no-redef]
            except ImportError as e:
                raise ServicioNoConfigurado(
                    "FISCALITO_MONITOREO=sentry necesita el paquete sentry-sdk: instálalo con "
                    "`pip install sentry-sdk` (y agrégalo a pyproject.toml) o usa "
                    "FISCALITO_MONITOREO=log."
                ) from e
        self._sdk = sdk
        sdk.init(dsn=dsn, environment=entorno, send_default_pii=False)

    def capturar_error(self, error, contexto=None):
        with self._sdk.new_scope() as scope:
            for k, v in (contexto or {}).items():
                scope.set_extra(k, v)
            self._sdk.capture_exception(error)

    def capturar_mensaje(self, mensaje, nivel="info", contexto=None):
        with self._sdk.new_scope() as scope:
            for k, v in (contexto or {}).items():
                scope.set_extra(k, v)
            self._sdk.capture_message(mensaje, level=nivel)


DESCRIPCION = "Monitoreo de errores en producción"
registro.registrar("monitoreo", "falso", MonitoreoFalso, DESCRIPCION)
registro.registrar("monitoreo", "log", MonitoreoLog, DESCRIPCION)
registro.registrar("monitoreo", "sentry", lambda: MonitoreoSentry(
    env("FISCALITO_SENTRY_DSN"), env("FISCALITO_ENTORNO", "desarrollo")), DESCRIPCION)
