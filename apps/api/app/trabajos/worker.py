"""
Worker de la cola: `python -m app.trabajos.worker [--una-vez] [--pausa 5] [--sin-programacion]`.

Cada vuelta: revisa la programación recurrente (salvo `--sin-programacion`, cuando el
programador corre en su propio proceso: `python -m app.trabajos.programador`), recupera
huérfanos y corre trabajos vencidos hasta vaciar la cola; luego duerme `--pausa` segundos.
SIGINT/SIGTERM terminan el trabajo en curso y salen limpio (Railway manda SIGTERM al
redeployar). Cada vuelta deja un latido en la base que `GET /health` lee (P6-02).
"""

from __future__ import annotations

import argparse
import logging
import signal
import threading
from datetime import datetime

from sqlalchemy.orm import sessionmaker

from app.observabilidad import latir
from app.trabajos.cola import procesar_siguiente
from app.trabajos.manejadores import cargar_manejadores
from app.trabajos.programacion import TareaRecurrente, revisar_programacion

logger = logging.getLogger(__name__)

# Tope por vuelta: con la cola llena, la programación se sigue revisando cada tanto.
MAX_POR_VUELTA = 100


def una_vuelta(
    sesionador: sessionmaker,
    *,
    ahora: datetime | None = None,
    tareas: list[TareaRecurrente] | None = None,
    parar: threading.Event | None = None,
    con_programacion: bool = True,
) -> int:
    """Programación + trabajos vencidos. Devuelve cuántos trabajos corrió."""
    if con_programacion:
        revisar_programacion(sesionador, ahora=ahora, tareas=tareas)
        latir(sesionador, "programador", ahora=ahora)
    latir(sesionador, "worker", ahora=ahora)
    corridos = 0
    while corridos < MAX_POR_VUELTA and not (parar and parar.is_set()):
        if procesar_siguiente(sesionador, ahora=ahora) is None:
            break
        corridos += 1
    return corridos


def correr(
    sesionador: sessionmaker,
    *,
    pausa: float = 5.0,
    una_vez: bool = False,
    con_programacion: bool = True,
) -> None:
    """Loop del worker hasta recibir una señal (o una sola vuelta con `una_vez`)."""
    cargar_manejadores()
    parar = threading.Event()

    def _senal(numero: int, _marco: object) -> None:
        logger.info("Señal %s: el worker termina después del trabajo en curso.", numero)
        parar.set()

    if threading.current_thread() is threading.main_thread():
        signal.signal(signal.SIGINT, _senal)
        signal.signal(signal.SIGTERM, _senal)

    while not parar.is_set():
        try:
            corridos = una_vuelta(sesionador, parar=parar, con_programacion=con_programacion)
            if corridos:
                logger.info("Worker: %s trabajos corridos.", corridos)
        except Exception as exc:  # noqa: BLE001 — la base pudo caerse; se reintenta en la siguiente
            logger.exception("Vuelta del worker fallida")
            from app.observabilidad import reportar_error

            reportar_error(exc, origen="worker")
        if una_vez:
            return
        parar.wait(pausa)


def main(argv: list[str] | None = None) -> None:
    """Punto de entrada de la línea de comandos."""
    parser = argparse.ArgumentParser(description="Worker de trabajos en segundo plano.")
    parser.add_argument("--una-vez", action="store_true", help="Una vuelta y sale.")
    parser.add_argument("--pausa", type=float, default=5.0, help="Segundos entre vueltas.")
    parser.add_argument(
        "--sin-programacion", action="store_true",
        help="No revisa las tareas recurrentes (el programador corre aparte).",
    )
    args = parser.parse_args(argv)

    from app.config import settings
    from app.db.session import SesionLocal, crear_tablas
    from app.logging_config import setup_logging

    setup_logging(proceso="worker")
    if settings.ENTORNO != "produccion":
        crear_tablas()
    correr(
        SesionLocal, pausa=args.pausa, una_vez=args.una_vez,
        con_programacion=not args.sin_programacion,
    )


if __name__ == "__main__":
    main()
