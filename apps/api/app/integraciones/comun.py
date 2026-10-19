"""Utilidades compartidas por los adaptadores: variables de entorno y cliente HTTP."""

import os

import httpx

from app.exceptions import FiscalAgentError

TIMEOUT = httpx.Timeout(20.0, connect=10.0)


class ServicioNoConfigurado(FiscalAgentError):
    """Falta una variable de entorno de un servicio externo (503)."""

    def __init__(self, mensaje: str) -> None:
        super().__init__(mensaje, status_code=503)


class ErrorServicioExterno(FiscalAgentError):
    """El servicio externo respondió con error (502)."""

    def __init__(self, mensaje: str) -> None:
        super().__init__(mensaje, status_code=502)


def env(nombre: str, default: str | None = None) -> str:
    """Lee `nombre`; si falta y no hay default, 503 que dice qué variable poner."""
    valor = os.environ.get(nombre, "").strip()
    if valor:
        return valor
    if default is not None:
        return default
    raise ServicioNoConfigurado(
        f"Falta la variable de entorno {nombre} (ver docs/servicios-externos.md)."
    )


def cliente_http(http: httpx.Client | None, **kwargs: object) -> httpx.Client:
    """El cliente inyectado (tests con MockTransport) o uno nuevo con tiempo límite."""
    return http if http is not None else httpx.Client(timeout=TIMEOUT, **kwargs)  # type: ignore[arg-type]


def revisar(respuesta: httpx.Response, servicio: str) -> httpx.Response:
    """502 legible si el servicio no respondió 2xx. Nunca incluye credenciales."""
    if respuesta.is_success:
        return respuesta
    detalle = respuesta.text[:300]
    raise ErrorServicioExterno(
        f"{servicio} respondió {respuesta.status_code}: {detalle}"
    )
