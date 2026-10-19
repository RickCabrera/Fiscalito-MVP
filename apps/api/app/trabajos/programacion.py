"""
Tareas recurrentes (P0-04): qué se encola solo y cada cuánto.

Cada tarea dice CADA CUÁNTO (`cada`, un intervalo) o A QUÉ HORA (`hora`, diaria, en
America/Mexico_City) y trae una función que ENCOLA, no que trabaja: el trabajo de verdad
corre en la cola con sus reintentos y su estado visible.

UNA RANURA SE RECLAMA UNA SOLA VEZ
----------------------------------
Cada vuelta del worker calcula la ranura vigente de cada tarea (el inicio del intervalo
actual, o la última vez que dio la hora diaria) y la compara con `ejecuciones_programadas`.
Si ya se reclamó, no hace nada; si no, la reclama con una actualización condicional y
encola en la MISMA transacción. Así reiniciar el worker no repite la tarea del día, y dos
workers a la vez no la duplican. La clave única del trabajo (`prog:<nombre>:<ranura>`) es
una segunda red.

Si el worker estuvo caído cuando dio la hora, la tarea corre al volver (una vez, no una
por cada ranura perdida).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import ahora as _ahora
from app.modelos.trabajos import EjecucionProgramada
from app.trabajos.cola import encolar

logger = logging.getLogger(__name__)

ZONA = ZoneInfo("America/Mexico_City")
_EPOCA = datetime(2000, 1, 1, tzinfo=UTC)


@dataclass(frozen=True)
class TareaRecurrente:
    """Una tarea que el worker encola sola. Lleva `cada` o `hora`, no las dos."""

    nombre: str
    encolar: Callable[[Session, datetime], object]
    cada: timedelta | None = None
    hora: time | None = None

    def __post_init__(self) -> None:
        if (self.cada is None) == (self.hora is None):
            raise ValueError(f"La tarea '{self.nombre}' lleva `cada` o `hora`, una de las dos.")
        if self.cada is not None and self.cada <= timedelta(0):
            raise ValueError(f"La tarea '{self.nombre}' necesita un intervalo positivo.")

    def ranura(self, momento: datetime) -> datetime:
        """Inicio (en UTC) de la ranura vigente en `momento`."""
        if self.cada is not None:
            pasos = (momento - _EPOCA) // self.cada
            return _EPOCA + pasos * self.cada
        assert self.hora is not None
        local = momento.astimezone(ZONA)
        hoy = datetime.combine(local.date(), self.hora, tzinfo=ZONA)
        if local < hoy:
            hoy = datetime.combine(local.date() - timedelta(days=1), self.hora, tzinfo=ZONA)
        return hoy.astimezone(UTC)


def _encolar_purga(db: Session, ranura: datetime) -> object:
    return encolar(
        db,
        "mantenimiento.purgar_trabajos",
        {},
        ejecutar_en=ranura,
        clave_unica=f"prog:purgar_trabajos:{ranura.isoformat()}",
        max_intentos=3,
    )


# La lista que revisa el worker. Cada dominio agrega aquí las suyas.
TAREAS: list[TareaRecurrente] = [
    TareaRecurrente("purgar_trabajos", _encolar_purga, hora=time(3, 0)),
]


def _reclamar(db: Session, nombre: str, ranura: datetime) -> bool:
    """Marca la ranura como tomada. False si ya estaba (o si otro worker ganó)."""
    previa = db.get(EjecucionProgramada, nombre)
    if previa is None:
        try:
            with db.begin_nested():
                db.add(EjecucionProgramada(nombre=nombre, ultima_ejecucion=ranura))
                db.flush()
            return True
        except IntegrityError:
            return False
    if previa.ultima_ejecucion >= ranura:
        return False
    cambio = db.execute(
        update(EjecucionProgramada)
        .where(
            EjecucionProgramada.nombre == nombre,
            EjecucionProgramada.ultima_ejecucion < ranura,
        )
        .values(ultima_ejecucion=ranura)
        .execution_options(synchronize_session=False)
    )
    return cambio.rowcount == 1


def revisar_programacion(
    sesionador: sessionmaker,
    *,
    ahora: datetime | None = None,
    tareas: list[TareaRecurrente] | None = None,
) -> list[str]:
    """Encola las tareas cuya ranura vigente no se ha reclamado. Devuelve sus nombres."""
    momento = ahora or _ahora()
    encoladas: list[str] = []
    for tarea in TAREAS if tareas is None else tareas:
        ranura = tarea.ranura(momento)
        with sesionador() as db:
            try:
                if not _reclamar(db, tarea.nombre, ranura):
                    db.rollback()
                    continue
                tarea.encolar(db, ranura)
                db.commit()
                encoladas.append(tarea.nombre)
            except Exception:  # noqa: BLE001 — una tarea rota no detiene a las demás
                db.rollback()
                logger.exception("No se pudo encolar la tarea recurrente '%s'", tarea.nombre)
    return encoladas
