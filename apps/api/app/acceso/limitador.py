"""
Límite de peticiones por ventana deslizante (P0-02).

LA INTERFAZ ES PARA CAMBIAR DE ALMACÉN, NO DE ALGORITMO
-------------------------------------------------------
`LimitadorEnMemoria` guarda los instantes de cada llave en la memoria del proceso. Con un
solo proceso (Railway hoy) es exacto; con varias réplicas cada una cuenta lo suyo y el
límite efectivo se multiplica por el número de réplicas. Para entonces se implementa
`Limitador` sobre Redis (ZADD/ZREMRANGEBYSCORE) o sobre la base, se registra en
`_IMPLEMENTACIONES` y se elige con `FISCALITO_LIMITADOR`. Hoy la única es `memoria`.

Los límites se leen del entorno EN CADA LLAMADA (no al importar): así un despliegue los
cambia sin tocar código y los tests los fijan con `monkeypatch.setenv`.
"""

from __future__ import annotations

import os
import threading
import time
from collections import deque
from collections.abc import Callable
from typing import Protocol

VENTANA_S = 60.0

# Defaults documentados en docs/api-contract.md ("Autenticación, límites y tope de LLM").
DEFAULT_POR_MINUTO = 120
DEFAULT_LLM_POR_MINUTO = 20

# Llaves vivas antes de barrer las que ya no tienen nada en la ventana.
_MAX_LLAVES = 10_000


def entero_de_entorno(nombre: str, default: int, minimo: int = 1) -> int:
    """Entero de una variable de entorno; un valor inválido es un error, no el default."""
    crudo = os.environ.get(nombre, "").strip()
    if not crudo:
        return default
    try:
        valor = int(crudo)
    except ValueError as exc:
        raise ValueError(f"{nombre} debe ser un entero, no {crudo!r}.") from exc
    if valor < minimo:
        raise ValueError(f"{nombre} debe ser al menos {minimo}, no {valor}.")
    return valor


def limite_por_minuto() -> int:
    """Peticiones por minuto por usuario (`FISCALITO_RATE_LIMIT_POR_MINUTO`, default 120)."""
    return entero_de_entorno("FISCALITO_RATE_LIMIT_POR_MINUTO", DEFAULT_POR_MINUTO)


def limite_llm_por_minuto() -> int:
    """Peticiones con LLM por minuto por usuario (`..._LLM_POR_MINUTO`, default 20)."""
    return entero_de_entorno("FISCALITO_RATE_LIMIT_LLM_POR_MINUTO", DEFAULT_LLM_POR_MINUTO)


class Limitador(Protocol):
    def consumir(self, llave: str, limite: int, ventana_s: float = VENTANA_S) -> float | None:
        """
        Cuenta una petición de `llave`.

        Devuelve `None` si cabe en la ventana, o los segundos que faltan para que quepa.
        Una petición rechazada NO se cuenta: insistir no alarga el castigo.
        """
        ...

    def reiniciar(self) -> None: ...


class LimitadorEnMemoria:
    """Ventana deslizante exacta: un `deque` de instantes por llave, con candado."""

    def __init__(self, reloj: Callable[[], float] = time.monotonic) -> None:
        self._reloj = reloj
        self._instantes: dict[str, deque[float]] = {}
        self._candado = threading.Lock()

    def consumir(self, llave: str, limite: int, ventana_s: float = VENTANA_S) -> float | None:
        ahora = self._reloj()
        with self._candado:
            cola = self._instantes.setdefault(llave, deque())
            while cola and cola[0] <= ahora - ventana_s:
                cola.popleft()
            if len(cola) >= limite:
                return cola[0] + ventana_s - ahora
            cola.append(ahora)
            if len(self._instantes) > _MAX_LLAVES:
                self._barrer(ahora, ventana_s)
            return None

    def _barrer(self, ahora: float, ventana_s: float) -> None:
        """Quita las llaves sin nada vivo: un usuario que se fue no ocupa memoria siempre."""
        muertas = [k for k, c in self._instantes.items() if not c or c[-1] <= ahora - ventana_s]
        for llave in muertas:
            del self._instantes[llave]

    def reiniciar(self) -> None:
        with self._candado:
            self._instantes.clear()


_IMPLEMENTACIONES: dict[str, Callable[[], Limitador]] = {"memoria": LimitadorEnMemoria}
_ACTUAL: Limitador | None = None


def obtener_limitador() -> Limitador:
    """El limitador del proceso, elegido por `FISCALITO_LIMITADOR` (hoy sólo `memoria`)."""
    global _ACTUAL
    if _ACTUAL is None:
        nombre = os.environ.get("FISCALITO_LIMITADOR", "").strip().lower() or "memoria"
        if nombre not in _IMPLEMENTACIONES:
            raise ValueError(
                f"FISCALITO_LIMITADOR={nombre!r} no existe. Opciones: {sorted(_IMPLEMENTACIONES)}."
            )
        _ACTUAL = _IMPLEMENTACIONES[nombre]()
    return _ACTUAL


def reiniciar_limitador() -> None:
    """Para tests: vacía las ventanas del limitador del proceso."""
    obtener_limitador().reiniciar()
