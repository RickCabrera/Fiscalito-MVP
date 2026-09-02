"""
Schemas de asistencia: checadas del reloj biometrico e incidencias del periodo.

DEMO — ver `docs/D-DEMO-CHECADOR.md`. El modelo es independiente del
fabricante: `hikvision.py` es un adaptador que produce `EventoChecada`, y
cualquier otro checador seria otro adaptador con la misma salida.
"""

from __future__ import annotations

from datetime import date, datetime, time
from enum import Enum

from pydantic import BaseModel, Field


class TipoChecada(str, Enum):
    """Entrada o salida. Sale de `attendanceStatus` del dispositivo."""

    ENTRADA = "entrada"
    SALIDA = "salida"


class FuenteChecada(str, Enum):
    """De donde vino el evento. `csv` queda para el plan C (import manual)."""

    HIKVISION = "hikvision"
    SIMULADO = "simulado"
    CSV = "csv"


class EventoChecada(BaseModel):
    """
    Una checada normalizada.

    `timestamp` conserva el offset que trae el dispositivo: el dia y la hora de
    la checada se interpretan **en la hora local del evento**, no en UTC. Sin
    eso, una entrada a las 08:02-06:00 se leeria como 14:02 y saldria retardo
    todos los dias.

    `raw` guarda el objeto original para poder auditar que mando el aparato.
    Puede contener el **nombre de la persona**: vive en memoria y no debe
    escribirse a disco ni a logs.
    """

    empleado_no: str = Field(description="employeeNo del dispositivo = id del empleado")
    timestamp: datetime = Field(description="Instante de la checada, con offset")
    tipo: TipoChecada
    fuente: FuenteChecada
    serial_no: int | None = Field(
        default=None,
        description="serialNo consecutivo DEL EVENTO, para deduplicar reintentos. "
        "**No identifica al aparato**: dos dispositivos del mismo cliente producen "
        "series indistinguibles, asi que este modelo no permite atribuir una checada "
        "a un dispositivo concreto. La descripcion anterior decia 'serialNo del "
        "dispositivo' y es justo la frase que llevaria a construir 'checadas por "
        "aparato' sobre una premisa falsa (lo encontro R-04 al escribir la pantalla "
        "de dispositivos, que por esto NO afirma cuantas checadas mando cada equipo).",
    )
    raw: dict | None = Field(default=None, description="Evento original del dispositivo")


class HorarioLaboral(BaseModel):
    """
    Horario contra el que se miden retardos y faltas.

    `dias_laborables` usa la convencion de `datetime.weekday()`: 0 = lunes.
    Default de lunes a viernes.
    """

    hora_entrada: time = Field(default=time(8, 0))
    hora_salida: time = Field(default=time(17, 0))
    tolerancia_minutos: int = Field(default=15, ge=0, le=120)
    dias_laborables: tuple[int, ...] = Field(default=(0, 1, 2, 3, 4))


class DiaTrabajado(BaseModel):
    """Detalle de un dia del periodo, para que la pantalla pueda explicarlo."""

    dia: date
    laborable: bool
    checadas: int
    trabajado: bool
    falta: bool
    retardo: bool
    primera_entrada: time | None = None


class IncidenciasEmpleado(BaseModel):
    """
    Incidencias de un empleado en el periodo.

    OJO con `dias_cotizados`: es **informativo para la pantalla de la demo**.
    La base de las cuotas del IMSS la determina
    `nomina_engine.cuotas.DiasDelPeriodo` **segun el ramo** — el ausentismo no
    reduce Enfermedades y Maternidad (Art. 31 LSS, §D3) — y ese objeto se
    construye con `dias_periodo` y `dias_ausentismo`, que por eso se exponen
    aqui. Tomar `dias_cotizados` como base de cuotas contradice a `cuotas.py`.

    LIMITACION CONOCIDA: hoy **toda** ausencia cuenta como falta. Vacaciones,
    permisos e incapacidades no se distinguen, y legalmente no son ausentismo
    injustificado. Es F1-09.
    """

    empleado_no: str
    dias_periodo: int = Field(description="Dias naturales del periodo; va a DiasDelPeriodo")
    dias_laborables: int
    dias_trabajados: int
    faltas: int
    dias_ausentismo: int = Field(description="= faltas; va a DiasDelPeriodo")
    retardos: int
    dias_cotizados: int = Field(
        description="Informativo. La base de cuotas la decide DiasDelPeriodo por ramo (§D3)"
    )
    detalle: tuple[DiaTrabajado, ...] = ()


class Periodo(BaseModel):
    """Periodo cerrado, inclusivo en los dos extremos."""

    inicio: date
    fin: date


class EventosRecibidosResponse(BaseModel):
    exito: bool = True
    cliente: str
    recibidos: int = Field(description="Eventos aceptados de este payload")
    duplicados: int = Field(description="Descartados por (empleado_no, serialNo) repetido")
    total_en_memoria: int


class EventosResponse(BaseModel):
    exito: bool = True
    cliente: str
    eventos: tuple[EventoChecada, ...]


class CerrarPeriodoRequest(BaseModel):
    cliente: str
    empleados: tuple[str, ...] = Field(description="employeeNo de los empleados del cliente")
    periodo: Periodo
    horario: HorarioLaboral = Field(default_factory=HorarioLaboral)


class CerrarPeriodoResponse(BaseModel):
    exito: bool = True
    cliente: str
    periodo: Periodo
    incidencias: tuple[IncidenciasEmpleado, ...]
    empleados_desconocidos: tuple[str, ...] = Field(
        default=(),
        description="Checadas de employeeNo que no esta en `empleados`. Si la pantalla no "
        "lo muestra, un alta mal hecha en el dispositivo se ve como falta de todos.",
    )
