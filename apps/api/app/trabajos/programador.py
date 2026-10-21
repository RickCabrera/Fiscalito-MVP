"""
Programador de tareas recurrentes como proceso propio:
`python -m app.trabajos.programador [--una-vez] [--pausa 30]`.

El worker (`app.trabajos.worker`) revisa la programación por default; este comando existe
para desplegarla como servicio aparte (P6-03: mismo contenedor, distinto comando) y correr
el worker con `--sin-programacion`. Sólo ENCOLA: el trabajo corre en el worker. Cada vuelta
deja su latido (`GET /health`).
"""

from __future__ import annotations

import argparse
import logging
import signal
import threading

from sqlalchemy.orm import sessionmaker

from app.observabilidad import latir, reportar_error
from app.trabajos.programacion import revisar_programacion

logger = logging.getLogger(__name__)


def correr(sesionador: sessionmaker, *, pausa: float = 30.0, una_vez: bool = False) -> None:
    """Loop del programador hasta recibir una señal (o una sola vuelta con `una_vez`)."""
    parar = threading.Event()

    def _senal(numero: int, _marco: object) -> None:
        logger.info("Señal %s: el programador termina.", numero)
        parar.set()

    if threading.current_thread() is threading.main_thread():
        signal.signal(signal.SIGINT, _senal)
        signal.signal(signal.SIGTERM, _senal)

    while not parar.is_set():
        try:
            encoladas = revisar_programacion(sesionador)
            latir(sesionador, "programador")
            if encoladas:
                logger.info("Programador: encoló %s.", ", ".join(encoladas))
        except Exception as exc:  # noqa: BLE001 — la base pudo caerse; se reintenta
            logger.exception("Vuelta del programador fallida")
            reportar_error(exc, origen="programador")
        if una_vez:
            return
        parar.wait(pausa)


def main(argv: list[str] | None = None) -> None:
    """Punto de entrada de la línea de comandos."""
    parser = argparse.ArgumentParser(description="Programador de tareas recurrentes.")
    parser.add_argument("--una-vez", action="store_true", help="Una vuelta y sale.")
    parser.add_argument("--pausa", type=float, default=30.0, help="Segundos entre vueltas.")
    args = parser.parse_args(argv)

    from app.config import settings
    from app.db.session import SesionLocal, crear_tablas
    from app.logging_config import setup_logging

    setup_logging(proceso="programador")
    if settings.ENTORNO != "produccion":
        crear_tablas()
    correr(SesionLocal, pausa=args.pausa, una_vez=args.una_vez)


if __name__ == "__main__":
    main()
