"""
Incidencias del periodo a partir de las checadas.

FUNCION PURA, A PROPOSITO
-------------------------
`cerrar_periodo()` recibe los eventos y no sabe de donde salieron. **No
importa `almacen.py`** — si algun dia lo hiciera, el corte entre "el motor" y
"el estado temporal de la demo" se habria perdido.

LA HORA ES LA DEL EVENTO, NO UTC
--------------------------------
Cada checada trae su offset (`2026-09-01T08:02:11-06:00`). El dia al que
pertenece y la hora contra la que se mide el retardo se leen **en esa hora
local**. Comparar el instante en UTC contra un `hora_entrada` naive
convertiria las 08:02 locales en 14:02 y sacaria retardo todos los dias.

REGLAS DE HOY, LITERALES DEL SPEC
---------------------------------
- Dia con >= 1 checada = trabajado.
- Dia laborable sin checada = falta.
- Primera **entrada** despues de `hora_entrada + tolerancia` = retardo.

El retardo se evalua solo sobre eventos de ENTRADA: si un dia solo tiene
salida, cuenta como trabajado pero **no** como retardo. Medirlo sobre "la
primera checada del dia" convertiria una salida a las 18:00 en retardo.

LIMITACIONES CONOCIDAS, no implementadas hoy (F1-09)
----------------------------------------------------
- **Turnos nocturnos**: una entrada a las 22:00 y su salida a las 06:00 caen
  en dos dias calendario y se cuentan como dos dias trabajados.
- **Vacaciones, permisos e incapacidades**: hoy TODA ausencia se cuenta como
  falta. Legalmente ni la incapacidad ni las vacaciones son ausentismo
  injustificado, y §D3 si las distingue. Es conservador para el patron
  (cobra de mas) pero incorrecto en cuanto haya una incapacidad.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta

from app.exceptions import FiscalValidationError
from app.schemas.asistencia import (
    DiaTrabajado,
    EventoChecada,
    HorarioLaboral,
    IncidenciasEmpleado,
    Periodo,
    TipoChecada,
)


def _dias_del_periodo(periodo: Periodo) -> list[date]:
    """
    Dias naturales del periodo, inclusivo en los dos extremos.

    Se calcula de las fechas y nunca de una constante: la quincena del 16 al
    31 son 16 dias, no 15.
    """
    if periodo.fin < periodo.inicio:
        raise FiscalValidationError(
            f"El periodo termina antes de empezar: {periodo.inicio} → {periodo.fin}."
        )
    total = (periodo.fin - periodo.inicio).days + 1
    return [periodo.inicio + timedelta(days=n) for n in range(total)]


def _hora_local(momento: datetime) -> time:
    """Hora de la checada en su propia zona, que es contra la que se mide."""
    return momento.timetz().replace(tzinfo=None)


def _limite_de_retardo(horario: HorarioLaboral) -> time:
    base = datetime.combine(date(2000, 1, 1), horario.hora_entrada)
    return (base + timedelta(minutes=horario.tolerancia_minutos)).time()


def cerrar_periodo(
    eventos: tuple[EventoChecada, ...] | list[EventoChecada],
    empleados: tuple[str, ...] | list[str],
    periodo: Periodo,
    horario: HorarioLaboral | None = None,
) -> tuple[tuple[IncidenciasEmpleado, ...], tuple[str, ...]]:
    """
    Calcula las incidencias de cada empleado en el periodo.

    Args:
        eventos: checadas de cualquier fuente. Las que caen fuera del periodo
            se ignoran.
        empleados: `employeeNo` de la plantilla del cliente. Una checada de un
            numero que no este aqui **no se descarta callando**: sale en el
            segundo valor del retorno.

    Returns:
        `(incidencias, empleados_desconocidos)`. Lo segundo importa: si el
        dispositivo tiene un alta con el `employeeNo` equivocado, sin esto la
        pantalla mostraria falta para todos y nadie sabria por que.
    """
    horario = horario or HorarioLaboral()
    dias = _dias_del_periodo(periodo)
    plantilla = list(dict.fromkeys(empleados))
    conocidos = set(plantilla)
    limite = _limite_de_retardo(horario)

    por_empleado: dict[str, dict[date, list[EventoChecada]]] = defaultdict(
        lambda: defaultdict(list)
    )
    desconocidos: set[str] = set()
    for evento in eventos:
        dia = evento.timestamp.date()
        if dia < periodo.inicio or dia > periodo.fin:
            continue
        if evento.empleado_no not in conocidos:
            desconocidos.add(evento.empleado_no)
            continue
        por_empleado[evento.empleado_no][dia].append(evento)

    incidencias: list[IncidenciasEmpleado] = []
    for empleado in plantilla:
        del_dia = por_empleado.get(empleado, {})
        detalle: list[DiaTrabajado] = []
        for dia in dias:
            checadas = del_dia.get(dia, [])
            laborable = dia.weekday() in horario.dias_laborables
            trabajado = bool(checadas)
            entradas = [
                _hora_local(c.timestamp) for c in checadas if c.tipo is TipoChecada.ENTRADA
            ]
            primera = min(entradas) if entradas else None
            detalle.append(
                DiaTrabajado(
                    dia=dia,
                    laborable=laborable,
                    checadas=len(checadas),
                    trabajado=trabajado,
                    falta=laborable and not trabajado,
                    retardo=primera is not None and primera > limite,
                    primera_entrada=primera,
                )
            )
        faltas = sum(1 for d in detalle if d.falta)
        incidencias.append(
            IncidenciasEmpleado(
                empleado_no=empleado,
                dias_periodo=len(dias),
                dias_laborables=sum(1 for d in detalle if d.laborable),
                dias_trabajados=sum(1 for d in detalle if d.trabajado),
                faltas=faltas,
                dias_ausentismo=faltas,
                retardos=sum(1 for d in detalle if d.retardo),
                dias_cotizados=len(dias) - faltas,
                detalle=tuple(detalle),
            )
        )
    return tuple(incidencias), tuple(sorted(desconocidos))
