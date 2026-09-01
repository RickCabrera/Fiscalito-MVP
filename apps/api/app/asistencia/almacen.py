"""
Almacen de checadas EN MEMORIA DEL PROCESO. **Solo para la demo.**

POR QUE EXISTE Y QUE LO REEMPLAZA
---------------------------------
`apps/api/CLAUDE.md` declara el servicio **stateless**: no guarda datos del
usuario. Esto lo rompe a proposito y de forma acotada, porque el panel de
checador en vivo necesita que los eventos que llegan por push sigan ahi cuando
el front haga el siguiente polling.

Se pierde al reiniciar el proceso, no se replica entre workers y no se
persiste. Lo reemplaza Firestore en F1-09
(`clientes/{id}/asistencia/{periodoId}`, ver `docs/D-DEMO-CHECADOR.md`), y
**este archivo se borra** cuando eso ocurra.

PRIVACIDAD
----------
El `raw` de cada evento puede traer el **nombre de la persona** (campo `name`
del `InfoList`). Vive aqui, en RAM, y no debe escribirse a disco, a un log ni
a un fixture.

TOPE DURO
---------
La cola por cliente es un ring buffer. Sin tope, un `POST` abierto y sin auth
es un agotamiento de memoria de una linea de `curl`; con tope, se pierden los
eventos mas viejos pero **el POST nunca falla en medio de la demo**, que es la
falla que si se ve.
"""

from __future__ import annotations

from collections import deque
from datetime import datetime

from app.schemas.asistencia import EventoChecada

# Una quincena de 9 empleados con entrada y salida son ~270 eventos. 5000 deja
# margen de sobra para la demo y acota la memoria si alguien abusa del POST.
MAX_EVENTOS_POR_CLIENTE = 5_000


class AlmacenChecadas:
    """
    Eventos por cliente, con dedupe por `(empleado_no, serial_no)`.

    El dedupe importa porque el push del dispositivo **reintenta**: los
    duplicados no cambian las incidencias, pero ensucian el panel en vivo.
    Solo aplica cuando el evento trae `serial_no`.
    """

    def __init__(self) -> None:
        self._eventos: dict[str, deque[EventoChecada]] = {}
        self._vistos: dict[str, set[tuple[str, int]]] = {}

    def agregar(
        self, cliente: str, eventos: tuple[EventoChecada, ...]
    ) -> tuple[int, int]:
        """
        Guarda los eventos de un cliente.

        Returns:
            `(aceptados, duplicados)`.
        """
        cola = self._eventos.setdefault(cliente, deque(maxlen=MAX_EVENTOS_POR_CLIENTE))
        vistos = self._vistos.setdefault(cliente, set())
        aceptados = duplicados = 0
        for evento in eventos:
            if evento.serial_no is not None:
                llave = (evento.empleado_no, evento.serial_no)
                if llave in vistos:
                    duplicados += 1
                    continue
                vistos.add(llave)
            cola.append(evento)
            aceptados += 1
        return aceptados, duplicados

    def eventos(
        self, cliente: str, desde: datetime | None = None
    ) -> tuple[EventoChecada, ...]:
        """
        Copia de los eventos del cliente, **ordenada cronologicamente**.

        Devuelve una copia y no la cola viva porque el simulador escribe
        mientras el panel lee: iterar la estructura mutable daria
        `RuntimeError: deque mutated during iteration` en vivo.

        `desde` es **inclusivo**; un cliente desconocido devuelve vacio, no un
        error.
        """
        cola = list(self._eventos.get(cliente, ()))
        if desde is not None:
            cola = [e for e in cola if e.timestamp >= desde]
        return tuple(sorted(cola, key=lambda e: e.timestamp))

    def total(self, cliente: str) -> int:
        return len(self._eventos.get(cliente, ()))

    def reset(self) -> None:
        """Vacia todo. Lo usan los tests para no depender del orden."""
        self._eventos.clear()
        self._vistos.clear()


# Instancia unica del proceso. Es el unico estado mutable del servicio.
almacen = AlmacenChecadas()
