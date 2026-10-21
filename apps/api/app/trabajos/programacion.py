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


def _sat(nombre: str) -> Callable[[Session, datetime], object]:
    """Importación perezosa: `programacion` no arrastra los adaptadores al importarse."""

    def encolar_sat(db: Session, ranura: datetime) -> object:
        from app.sat_verificacion import trabajos as sat

        return getattr(sat, nombre)(db, ranura)

    return encolar_sat


def _encolar_alertas(db: Session, ranura: datetime) -> object:
    from app.alertas.trabajos import encolar_diario

    return encolar_diario(db, ranura)


def _cobranza(nombre: str) -> Callable[[Session, datetime], object]:
    def encolar_cobranza(db: Session, ranura: datetime) -> object:
        from app.cobranza import trabajos as cobranza

        return getattr(cobranza, nombre)(db, ranura)

    return encolar_cobranza


def _encolar_respaldos(db: Session, ranura: datetime) -> object:
    from app.despacho.respaldos import encolar_respaldos

    return encolar_respaldos(db, ranura)


def _encolar_purga_exportaciones(db: Session, ranura: datetime) -> object:
    from app.despacho.respaldos import encolar_purga_exportaciones

    return encolar_purga_exportaciones(db, ranura)


# La lista que revisa el worker. Cada dominio agrega aquí las suyas.
TAREAS: list[TareaRecurrente] = [
    TareaRecurrente("purgar_trabajos", _encolar_purga, hora=time(3, 0)),
    # P6-01: respaldo lógico diario de cada despacho al almacenamiento (retención configurable).
    TareaRecurrente("respaldos_despachos", _encolar_respaldos, hora=time(3, 30)),
    TareaRecurrente("purgar_exportaciones", _encolar_purga_exportaciones, hora=time(4, 0)),
    # P1-03: estatus de CFDI — diario los del mes, semanal los del último año.
    TareaRecurrente("sat_estatus_mes", _sat("encolar_estatus_mes"), hora=time(2, 0)),
    TareaRecurrente("sat_estatus_anio", _sat("encolar_estatus_anio"), cada=timedelta(days=7)),
    # P1-04: listas 69-B / 69, diario (el SAT las actualiza en días hábiles).
    TareaRecurrente("sat_listas", _sat("encolar_listas"), hora=time(6, 30)),
    # P1-05: opinión/constancia mensual; la revisión es diaria y cada cliente decide su día.
    TareaRecurrente("sat_cumplimiento", _sat("encolar_cumplimiento_diario"), hora=time(7, 0)),
    # P3-09: alertas fiscales, después de listas (6:30) y opinión (7:00) para integrarlas.
    TareaRecurrente("alertas_fiscales", _encolar_alertas, hora=time(7, 30)),
    # P5-03: igualas del mes (cada cliente en su día de cargo) y recordatorios de cobro.
    TareaRecurrente("cobranza_cargos", _cobranza("encolar_cargos"), hora=time(6, 0)),
    TareaRecurrente("cobranza_recordatorios", _cobranza("encolar_recordatorios"),
                    hora=time(10, 0)),
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
            except Exception as exc:  # noqa: BLE001 — una tarea rota no detiene a las demás
                db.rollback()
                logger.exception("No se pudo encolar la tarea recurrente '%s'", tarea.nombre)
                from app.observabilidad import reportar_error

                reportar_error(exc, origen="programador", tarea=tarea.nombre,
                               ranura=ranura.isoformat())
    return encoladas
