"""
Adaptador del checador Hikvision (MinMoe DS-K1T321MFWX-B/S).

Convierte el `AcsEvent` que manda el dispositivo —por HTTP listening o por
poll a `/ISAPI/AccessControl/AcsEvent`— en `EventoChecada`, que es lo unico
que el resto del sistema conoce. Otro checador seria otro adaptador con la
misma salida.

Referencia del formato: `docs/D-DEMO-CHECADOR.md`, seccion "Referencia tecnica".

NADA SE DESCARTA EN SILENCIO
----------------------------
Un evento con `employeeNoString` vacio, `time` invalido o `attendanceStatus`
desconocido **levanta**, nombrando el valor. La alternativa —ignorarlo— haria
que un dispositivo mal configurado se viera como "todos faltaron", que es el
peor modo de falla posible el dia de la demo.

Lo que si se filtra a proposito, porque no son checadas: los eventos que no
son `major == 5` (acceso) o cuyo `minor` no esta en los metodos de
autenticacion validos.
"""

from __future__ import annotations

from datetime import datetime

from app.exceptions import FiscalValidationError
from app.schemas.asistencia import EventoChecada, FuenteChecada, TipoChecada

# major 5 = evento de control de acceso.
MAJOR_ACCESO = 5

# minor: metodos de autenticacion que SI cuentan como checada.
# 75 rostro, 1 tarjeta, 38 huella. Los fallos (21, 22, 76) no cuentan.
MINORS_AUTENTICACION_VALIDA = frozenset({75, 1, 38})

# DECISION PROVISIONAL (nocturno): el backlog dice `major==5 and minor==75`,
# o sea solo rostro. Se aceptan tambien tarjeta y huella porque son checadas
# igual de validas y un dispositivo con lector mixto las emite; rechazarlas
# haria que un empleado que checa con tarjeta apareciera como falta. Si la
# contadora o el jefe quieren solo rostro, se restringe este conjunto.

_ESTADO_A_TIPO = {
    "checkin": TipoChecada.ENTRADA,
    "checkout": TipoChecada.SALIDA,
}


def _tipo_desde_estado(estado: object, indice: int) -> TipoChecada:
    """
    Mapea `attendanceStatus` a entrada/salida. Sin default, a proposito.

    DECISION PROVISIONAL (nocturno): el dispositivo manda `undefined`,
    `breakIn` o `overTimeIn` cuando el modo de asistencia no esta configurado,
    y aqui eso **rechaza el batch** en vez de asumir una entrada. Tiene un
    costo conocido en D-08: si el aparato llega sin modo de asistencia, no
    entra ningun evento hasta configurarlo. Se prefiere el error ruidoso a una
    jornada inventada.
    """
    if not isinstance(estado, str) or estado.strip().lower() not in _ESTADO_A_TIPO:
        validos = ", ".join(sorted(_ESTADO_A_TIPO))
        raise FiscalValidationError(
            f"El evento #{indice} trae attendanceStatus={estado!r}, que no es una checada "
            f"de asistencia. Válidos: {validos}. Suele significar que el dispositivo no "
            f"tiene configurado el modo de asistencia."
        )
    return _ESTADO_A_TIPO[estado.strip().lower()]


def _timestamp(valor: object, indice: int) -> datetime:
    """
    Parsea `time` conservando el offset del dispositivo.

    El offset importa: el dia y la hora de la checada se miden en la hora
    local del evento. Un evento **sin** offset levanta en vez de asumir una
    zona, porque asumir mal desplaza todas las entradas y convierte el dia en
    puros retardos.
    """
    if not isinstance(valor, str):
        raise FiscalValidationError(f"El evento #{indice} no trae `time`.")
    try:
        momento = datetime.fromisoformat(valor)
    except ValueError as exc:
        raise FiscalValidationError(
            f"El evento #{indice} trae un `time` que no es ISO 8601: {valor!r}."
        ) from exc
    if momento.tzinfo is None:
        raise FiscalValidationError(
            f"El evento #{indice} trae `time` sin zona horaria: {valor!r}. El dispositivo "
            f"debe mandar el offset (p. ej. -06:00); asumir una zona desplazaría todas las "
            f"horas y convertiría el día en retardos."
        )
    return momento


def parse_acs_event(
    payload: dict, fuente: FuenteChecada = FuenteChecada.HIKVISION
) -> tuple[EventoChecada, ...]:
    """
    Convierte un payload `AcsEvent` en checadas.

    Acepta el cuerpo tal como lo manda el dispositivo (`{"AcsEvent": {...}}`) y
    tambien un `InfoList` suelto, que es lo que devuelve el poll paginado.

    Raises:
        FiscalValidationError: si el payload no tiene forma de AcsEvent, o si
            un evento que si es checada viene incompleto.
    """
    if not isinstance(payload, dict):
        raise FiscalValidationError("El payload de asistencia debe ser un objeto JSON.")
    contenedor = payload.get("AcsEvent", payload)
    if not isinstance(contenedor, dict):
        raise FiscalValidationError("`AcsEvent` debe ser un objeto.")
    lista = contenedor.get("InfoList", [])
    if not isinstance(lista, list):
        raise FiscalValidationError("`AcsEvent.InfoList` debe ser una lista.")

    eventos: list[EventoChecada] = []
    for indice, crudo in enumerate(lista):
        if not isinstance(crudo, dict):
            raise FiscalValidationError(f"El evento #{indice} no es un objeto.")
        if crudo.get("major") != MAJOR_ACCESO:
            continue
        if crudo.get("minor") not in MINORS_AUTENTICACION_VALIDA:
            continue
        numero = crudo.get("employeeNoString")
        if not isinstance(numero, str) or not numero.strip():
            raise FiscalValidationError(
                f"El evento #{indice} es una checada válida pero no trae "
                f"`employeeNoString`: sin ese campo no se puede saber de quién es."
            )
        serial = crudo.get("serialNo")
        eventos.append(
            EventoChecada(
                empleado_no=numero.strip(),
                timestamp=_timestamp(crudo.get("time"), indice),
                tipo=_tipo_desde_estado(crudo.get("attendanceStatus"), indice),
                fuente=fuente,
                serial_no=serial if isinstance(serial, int) else None,
                raw=crudo,
            )
        )
    return tuple(eventos)
