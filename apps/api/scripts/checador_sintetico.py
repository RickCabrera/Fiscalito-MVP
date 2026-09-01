"""
Generador de checadas sinteticas para la demo del checador (D-05).

**Logica pura: no toca la red, no imprime, no lee argumentos.** El CLI que la
usa es `scripts/simular_checador.py`; vive aparte porque juntos pasaban de 470
lineas. Se carga por ruta, no por import: `scripts/` no es paquete y
`pip install -e .` solo empaqueta `app*`.

PRIVACIDAD — POR QUE LA RUTA DE FIXTURES NO ES CONFIGURABLE
-----------------------------------------------------------
`plantilla_desde_fixtures()` resuelve la ruta desde `__file__` y **no acepta
parametro ni flag**. Apuntada a "03. CFDI DE NOMINA/" leeria nombre, RFC y CURP
de personas reales y los devolveria para que el CLI los POSTee o los imprima.
Las fixtures de S-04 son sinteticas; esa carpeta no.

DECISIONES PROVISIONALES (nocturno) — las tres estan en docs/nocturno-log.md
---------------------------------------------------------------------------
1. El periodo por default es la **ultima quincena ya terminada** (ver
   `quincena()`).
2. El horario es el **default del servidor** (`HorarioLaboral()`: 08:00-17:00,
   15 min, L-V). Nadie confirmo que sea el del cliente real: no esta en
   `docs/decisiones-nomina.md` ni en `PLAN_NOMINA` §5. La demo le va a ensenar
   al cliente tres retardos calculados contra un horario que nadie valido.
3. `E-01` aparece en 4 de las 9 semanas de las fixtures y `E-02` en 3 (altas y
   bajas del caso real). Aqui los 9 se tratan como **plantilla completa** de la
   quincena: la demo es de salario fijo y un cliente, y las bajas son F1-09.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path

from app.asistencia.hikvision import MAJOR_ACCESO, MINORS_AUTENTICACION_VALIDA
from app.exceptions import FiscalValidationError
from app.schemas.asistencia import HorarioLaboral, Periodo

# El MinMoe de la demo autentica por rostro. Se valida contra el conjunto del
# adaptador para que restringirlo alla (p. ej. a solo tarjeta) rompa aqui en vez
# de generar eventos que el endpoint filtraria en silencio.
MINOR_ROSTRO = 75
if MINOR_ROSTRO not in MINORS_AUTENTICACION_VALIDA:
    raise RuntimeError(
        f"minor {MINOR_ROSTRO} ya no cuenta como checada en el adaptador Hikvision."
    )

RUTA_FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "nomina"
# El numero de empleado y el nombre viven en NODOS DISTINTOS del CFDI:
# `NumEmpleado` en `nomina12:Receptor` y `Nombre` en `cfdi:Receptor`. Leer el
# nombre del nodo de nomina devuelve cadena vacia sin error.
NS = {
    "cfdi": "http://www.sat.gob.mx/cfd/4",
    "n": "http://www.sat.gob.mx/nomina12",
}

# Zona del centro de Mexico. Fija todo el ano: no hay horario de verano desde
# 2022. El endpoint EXIGE offset, y una zona equivocada corre todas las horas.
OFFSET_DEFAULT = "-06:00"

# Serial alto por dos razones, las dos reales: re-correr el simulador el dia de
# la demo sin reiniciar la API (el dedupe del almacen es por (empleado, serial)
# y nadie va a reiniciar el proceso enfrente del cliente), y no colisionar con
# los serials del aparato de D-08, que arrancan bajos (~575 en la doc ISAPI).
SERIAL_BASE_DEFAULT = 900_001

MINUTOS_ANTES_MAX = 15  # que tan temprano puede llegar quien no va tarde
MARGEN_RETARDO_MIN = 3  # colchon para que el jitter jamas toque el limite
SEGUNDOS_JITTER_SALIDA = 20 * 60

_EPOCA = date(2000, 1, 1)





@dataclass(frozen=True)
class EmpleadoDemo:
    """Un empleado de la plantilla, tal como lo dan las fixtures de S-04."""

    numero: str
    nombre: str


@dataclass(frozen=True)
class Falta:
    """
    Un dia sembrado como falta.

    OJO: un dia de falta emite **CERO eventos** de ese empleado, ni entrada ni
    salida. `cerrar_periodo()` marca el dia como trabajado con >= 1 checada de
    cualquier tipo, asi que dejar la salida de las 17:00 haria que el empleado
    no faltara y el numero sembrado no aparecera en la tabla.
    """

    empleado: str
    dia_laborable: int  # 1-based dentro del periodo


@dataclass(frozen=True)
class Retardo:
    """Una entrada tarde. `minutos_tarde` se mide desde `hora_entrada`."""

    empleado: str
    dia_laborable: int
    minutos_tarde: int


@dataclass(frozen=True)
class Siembra:
    """Las incidencias que el backlog pide ver en la tabla de la demo."""

    faltas: tuple[Falta, ...]
    retardos: tuple[Retardo, ...]


SIEMBRA_DEMO = Siembra(
    faltas=(Falta("E-05", 2), Falta("E-08", 5)),
    retardos=(Retardo("E-02", 1, 35), Retardo("E-06", 3, 22), Retardo("E-09", 7, 48)),
)


def plantilla_desde_fixtures() -> tuple[EmpleadoDemo, ...]:
    """
    Los 9 empleados de S-04, leidos de las fixtures. Ver PRIVACIDAD arriba.

    El par `NumEmpleado -> Nombre` es estable en las 9 semanas, asi que el
    dedupe por numero no colapsa dos identidades.
    """
    encontrados: dict[str, str] = {}
    for ruta in sorted(RUTA_FIXTURES.glob("semana-*/*.xml")):
        raiz = ET.parse(ruta).getroot()
        receptor = raiz.find(".//n:Nomina/n:Receptor", NS)
        persona = raiz.find("cfdi:Receptor", NS)
        if receptor is None or persona is None:
            continue
        numero, nombre = receptor.get("NumEmpleado"), persona.get("Nombre", "")
        if not numero or not nombre:
            raise FiscalValidationError(
                f"{ruta.name}: falta NumEmpleado o Nombre. El panel de la demo "
                f"muestra el nombre, y sin él la checada sale anónima."
            )
        encontrados.setdefault(numero, nombre)
    if not encontrados:
        raise FiscalValidationError(
            f"No se encontraron fixtures de nómina en {RUTA_FIXTURES}."
        )
    return tuple(EmpleadoDemo(n, encontrados[n]) for n in sorted(encontrados))


def dias_laborables(periodo: Periodo, horario: HorarioLaboral) -> tuple[date, ...]:
    """Dias laborables del periodo, en orden. El fin de semana no genera nada."""
    total = (periodo.fin - periodo.inicio).days + 1
    dias = (periodo.inicio + timedelta(days=n) for n in range(total))
    return tuple(d for d in dias if d.weekday() in horario.dias_laborables)


def ventana_entrada_normal(horario: HorarioLaboral) -> tuple[time, time]:
    """
    Rango de entrada de quien **no** va tarde, derivado del horario.

    No hay literales de hora en el script a proposito: si alguien baja la
    tolerancia a 10 minutos, un 08:12 hardcodeado fabricaria un retardo por
    empleado y por dia. El extremo superior queda estrictamente por debajo del
    limite, que `incidencias.py` compara con `>` estricto.
    """
    base = datetime.combine(_EPOCA, horario.hora_entrada)
    limite = base + timedelta(minutes=horario.tolerancia_minutos)
    temprano = base - timedelta(minutes=MINUTOS_ANTES_MAX)
    tarde = limite - timedelta(minutes=MARGEN_RETARDO_MIN)
    if tarde <= temprano or tarde >= limite:
        raise FiscalValidationError(
            f"No cabe una entrada puntual con tolerancia de "
            f"{horario.tolerancia_minutos} min: la ventana quedaria "
            f"[{temprano.time()}, {tarde.time()}]."
        )
    if datetime.combine(_EPOCA, horario.hora_salida) <= limite:
        raise FiscalValidationError(
            f"La hora de salida ({horario.hora_salida}) no puede caer antes del "
            f"límite de retardo ({limite.time()}): la jornada quedaría invertida."
        )
    return temprano.time(), tarde.time()


def _jitter(indice: int, dia: date, modulo: int) -> int:
    """
    Desplazamiento en segundos, determinista y sin RNG.

    Determinista importa mas que realista: la demo se ensaya varias veces y la
    tabla de incidencias tiene que dar lo mismo siempre.
    """
    return (indice * 7919 + dia.toordinal() * 104_729) % modulo


def _momento(dia: date, hora: time, offset: str, desplazamiento: int = 0) -> str:
    """Instante ISO 8601 **con offset**, que es lo que el endpoint exige."""
    base = datetime.combine(dia, hora) + timedelta(seconds=desplazamiento)
    return f"{base.isoformat(timespec='seconds')}{offset}"


def _checada(empleado: EmpleadoDemo, momento: str, entrada: bool) -> dict:
    """Un renglon de `InfoList` con la forma exacta del dispositivo."""
    return {
        "major": MAJOR_ACCESO,
        "minor": MINOR_ROSTRO,
        "time": momento,
        "employeeNoString": empleado.numero,
        "name": empleado.nombre,
        "attendanceStatus": "checkIn" if entrada else "checkOut",
        "currentVerifyMode": "face",
    }


def _validar_siembra(siembra: Siembra, laborables: int, horario: HorarioLaboral) -> None:
    """Nada se siembra en silencio: un dia o un retardo imposible levanta."""
    for marca in (*siembra.faltas, *siembra.retardos):
        if not 1 <= marca.dia_laborable <= laborables:
            raise FiscalValidationError(
                f"La siembra de {marca.empleado} pide el día laborable "
                f"#{marca.dia_laborable} y el periodo sólo tiene {laborables}."
            )
    entrada = datetime.combine(_EPOCA, horario.hora_entrada)
    salida = datetime.combine(_EPOCA, horario.hora_salida)
    for retardo in siembra.retardos:
        if retardo.minutos_tarde <= horario.tolerancia_minutos:
            raise FiscalValidationError(
                f"El retardo sembrado de {retardo.empleado} (+{retardo.minutos_tarde} "
                f"min) no supera la tolerancia de {horario.tolerancia_minutos} min: "
                f"el motor no lo contaría como retardo."
            )
        # Un retardo enorme pondria la entrada DESPUES de la salida y generaria
        # un dia invertido sin que nada levante. Hoy `SIEMBRA_DEMO` es constante
        # y no llega ahi, pero el guardia de "nada se siembra en silencio" tiene
        # que cubrirlo: es la misma clase de error que el de arriba.
        if entrada + timedelta(minutes=retardo.minutos_tarde) >= salida:
            raise FiscalValidationError(
                f"El retardo sembrado de {retardo.empleado} (+{retardo.minutos_tarde} "
                f"min) pone la entrada en o después de la salida "
                f"({horario.hora_salida}): la jornada quedaría invertida."
            )


def generar_checadas(
    empleados: Sequence[EmpleadoDemo],
    periodo: Periodo,
    horario: HorarioLaboral | None = None,
    offset: str = OFFSET_DEFAULT,
    siembra: Siembra = SIEMBRA_DEMO,
    serial_base: int = SERIAL_BASE_DEFAULT,
) -> tuple[dict, ...]:
    """
    Las checadas de toda la quincena, en orden cronologico.

    Los `serialNo` se asignan **despues** de ordenar, para que crezcan con el
    tiempo igual que los del aparato.
    """
    horario = horario or HorarioLaboral()
    laborables = dias_laborables(periodo, horario)
    _validar_siembra(siembra, len(laborables), horario)
    temprano, tarde = ventana_entrada_normal(horario)
    ancho = int(
        (
            datetime.combine(_EPOCA, tarde) - datetime.combine(_EPOCA, temprano)
        ).total_seconds()
    )

    sin_checar = {(f.empleado, f.dia_laborable) for f in siembra.faltas}
    tardes = {(r.empleado, r.dia_laborable): r.minutos_tarde for r in siembra.retardos}

    eventos: list[dict] = []
    for indice, empleado in enumerate(empleados):
        for numero_dia, dia in enumerate(laborables, start=1):
            if (empleado.numero, numero_dia) in sin_checar:
                continue  # falta: cero eventos, ni entrada ni salida
            minutos_tarde = tardes.get((empleado.numero, numero_dia))
            if minutos_tarde is None:
                hora_entrada, corrimiento = temprano, _jitter(indice, dia, ancho)
            else:
                hora_entrada = (
                    datetime.combine(_EPOCA, horario.hora_entrada)
                    + timedelta(minutes=minutos_tarde)
                ).time()
                corrimiento = _jitter(indice, dia, 60)
            eventos.append(
                _checada(empleado, _momento(dia, hora_entrada, offset, corrimiento), True)
            )
            eventos.append(
                _checada(
                    empleado,
                    _momento(
                        dia,
                        horario.hora_salida,
                        offset,
                        _jitter(indice + 1, dia, SEGUNDOS_JITTER_SALIDA),
                    ),
                    False,
                )
            )

    eventos.sort(key=lambda e: (e["time"], e["employeeNoString"]))
    for serial, evento in enumerate(eventos, start=serial_base):
        evento["serialNo"] = serial
    return tuple(eventos)


def envolver(infolist: Sequence[dict]) -> dict:
    """El sobre `AcsEvent`, identico al del dispositivo."""
    return {
        "AcsEvent": {
            "responseStatusStrg": "OK",
            "numOfMatches": len(infolist),
            "totalMatches": len(infolist),
            "InfoList": list(infolist),
        }
    }


def repartir(
    eventos: Sequence[dict], periodo: Periodo, horario: HorarioLaboral, limite: int | None
) -> tuple[tuple[dict, ...], tuple[dict, ...]]:
    """
    Parte los eventos en `(lote, en_vivo)`.

    En vivo va **solo el ultimo dia laborable** (18 eventos, ~90 s a 5 s cada
    uno). Mandar los 194 gota a gota serian 16 minutos antes de poder cerrar la
    quincena, y el backlog pide `--en-vivo` para el efecto en pantalla, no para
    esperar un cuarto de hora. `--limite` mueve el corte; nunca **descarta**
    eventos, o la tabla de incidencias cambiaria.
    """
    ultimo = dias_laborables(periodo, horario)[-1]
    cuantos = (
        limite
        if limite is not None  # `or` haria que --limite 0 significara "default"
        else sum(1 for e in eventos if e["time"].startswith(ultimo.isoformat()))
    )
    if not 0 < cuantos <= len(eventos):
        raise FiscalValidationError(
            f"El límite en vivo debe estar entre 1 y {len(eventos)}: {cuantos}."
        )
    return tuple(eventos[:-cuantos]), tuple(eventos[-cuantos:])
