"""Registro y selección de implementaciones de cada servicio externo."""

import os
from collections.abc import Callable
from typing import Any

from app.config import settings
from app.exceptions import FiscalAgentError

_FABRICAS: dict[str, dict[str, Callable[[], Any]]] = {}
_DESCRIPCION: dict[str, str] = {}
_CACHE: dict[str, Any] = {}


def registrar(
    servicio: str, nombre: str, fabrica: Callable[[], Any], descripcion: str = ""
) -> None:
    """Registra la implementación `nombre` del `servicio`."""
    _FABRICAS.setdefault(servicio, {})[nombre] = fabrica
    if descripcion:
        _DESCRIPCION[servicio] = descripcion


def variable(servicio: str) -> str:
    """Nombre de la variable de entorno que elige la implementación."""
    return f"FISCALITO_{servicio.upper()}"


# Servicios cuyo `falso` acepta webhooks firmados con un secreto conocido: en producción
# alguien podría activar una suscripción o hablar con el bot sin pagar ni ser cliente.
FALSO_VETADO_EN_PRODUCCION = frozenset({"pagos", "whatsapp"})


def elegida(servicio: str) -> str:
    """La implementación que manda el entorno (o `falso` fuera de producción)."""
    valor = os.environ.get(variable(servicio), "").strip().lower()
    if valor:
        return valor
    return "" if settings.ENTORNO == "produccion" else "falso"


def obtener(servicio: str) -> Any:
    """La instancia configurada del servicio. Se cachea por (servicio, implementación)."""
    _cargar_todo()
    nombre = elegida(servicio)
    opciones = _FABRICAS.get(servicio, {})
    if not nombre or nombre not in opciones:
        raise FiscalAgentError(
            f"El servicio '{servicio}' no está configurado: pon {variable(servicio)} con "
            f"uno de {sorted(opciones)}.",
            status_code=503,
        )
    if nombre == "falso" and servicio in FALSO_VETADO_EN_PRODUCCION and \
            settings.ENTORNO == "produccion":
        raise FiscalAgentError(
            f"El servicio '{servicio}' no puede usar la implementación falsa en producción: "
            "su webhook se firma con un secreto que está en el repo.", status_code=503)
    llave = f"{servicio}:{nombre}"
    if llave not in _CACHE:
        _CACHE[llave] = opciones[nombre]()
    return _CACHE[llave]


def limpiar_cache() -> None:
    """Para tests: olvida instancias creadas (p. ej. tras cambiar variables)."""
    _CACHE.clear()


def verificar_configuracion() -> list[dict[str, Any]]:
    """Estado de cada servicio: qué implementación se usa y si es la falsa."""
    _cargar_todo()
    estado = []
    for servicio in sorted(_FABRICAS):
        nombre = elegida(servicio)
        estado.append({
            "servicio": servicio,
            "descripcion": _DESCRIPCION.get(servicio, ""),
            "variable": variable(servicio),
            "implementacion": nombre or None,
            "disponibles": sorted(_FABRICAS[servicio]),
            "configurado": bool(nombre) and nombre in _FABRICAS[servicio],
            "es_falso": nombre == "falso",
        })
    return estado


_CARGADO = False


def _cargar_todo() -> None:
    """Importa los módulos de integración para que se registren (una sola vez)."""
    global _CARGADO
    if _CARGADO:
        return
    import importlib
    import pkgutil

    import app.integraciones as paquete

    for info in pkgutil.iter_modules(paquete.__path__):
        if info.name not in {"registro"}:
            importlib.import_module(f"app.integraciones.{info.name}")
    _CARGADO = True
