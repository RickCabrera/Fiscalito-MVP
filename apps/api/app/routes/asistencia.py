"""
Endpoints de asistencia (checador).

**DEMO** — ver `docs/D-DEMO-CHECADOR.md`:

- sin autenticacion: el push del Hikvision no sabe mandar un ID token de
  Firebase, y la auth del dispositivo esta mandada a F3;
- almacenamiento **en memoria del proceso**, que se pierde al reiniciar;
- no desplegar. Produccion esta apagada por decision de Ricardo (S-08).

El `cliente` viaja como **query param con default**, no en el cuerpo: la URL
que se configura en el dispositivo es fija y el cuerpo lo arma el aparato, asi
que no hay forma de meterle un campo. `POST /asistencia/eventos` sin
parametros funciona y cae en el cliente de la demo.
"""

from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, Query, Request

from app.asistencia.almacen import almacen
from app.asistencia.hikvision import parse_acs_event
from app.asistencia.incidencias import cerrar_periodo
from app.constants import CLIENTE_DEMO
from app.exceptions import FiscalValidationError
from app.schemas.asistencia import (
    CerrarPeriodoRequest,
    CerrarPeriodoResponse,
    EventosRecibidosResponse,
    EventosResponse,
    FuenteChecada,
)

router = APIRouter(tags=["Asistencia (demo)"])

_AVISO = "DEMO — sin autenticación, almacenamiento en memoria, no desplegar. "


async def _cuerpo_json(request: Request) -> dict:
    """
    Lee el cuerpo como JSON, venga como `application/json` o como multipart.

    El Hikvision manda `multipart/form-data` cuando adjunta la foto del
    reconocimiento: ahi el evento va en una parte y la imagen en otra. Solo se
    lee la parte JSON; la foto **no se guarda** (es un dato biometrico y no
    hace falta para calcular nada).

    Se revisan **todas** las partes, con y sin `filename`. Starlette convierte
    una parte en `str` solo cuando su Content-Disposition NO trae filename; con
    filename llega como `UploadFile`. Varios firmwares mandan la parte del
    evento con `Content-Type: application/json` **y** filename, asi que mirar
    solo las de tipo `str` rechazaria el batch entero contra el aparato real.
    """
    tipo = request.headers.get("content-type", "")
    if tipo.startswith("multipart/form-data"):
        formulario = await request.form()
        for valor in formulario.values():
            if isinstance(valor, str):
                crudo: bytes | str = valor
            else:
                crudo = await valor.read()
            try:
                contenido = json.loads(crudo)
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue  # la parte de la imagen no decodifica: se salta
            if isinstance(contenido, dict):
                return contenido
        raise FiscalValidationError(
            "El multipart no trae ninguna parte con un objeto JSON de evento."
        )
    try:
        contenido = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise FiscalValidationError("El cuerpo no es JSON válido.") from exc
    if not isinstance(contenido, dict):
        raise FiscalValidationError("El cuerpo debe ser un objeto JSON.")
    return contenido


@router.post(
    "/asistencia/eventos",
    response_model=EventosRecibidosResponse,
    summary=_AVISO + "Recibir checadas del checador",
    description=_AVISO
    + "Acepta el cuerpo `AcsEvent` tal como lo manda el Hikvision (JSON o "
    "multipart con la foto) o el simulador. Deduplica por (empleado, serialNo).",
)
async def recibir_eventos(
    request: Request,
    cliente: str = Query(default=CLIENTE_DEMO, description="Id del cliente"),
    fuente: FuenteChecada = Query(default=FuenteChecada.HIKVISION),
) -> EventosRecibidosResponse:
    payload = await _cuerpo_json(request)
    eventos = parse_acs_event(payload, fuente=fuente)
    aceptados, duplicados = almacen.agregar(cliente, eventos)
    return EventosRecibidosResponse(
        cliente=cliente,
        recibidos=aceptados,
        duplicados=duplicados,
        total_en_memoria=almacen.total(cliente),
    )


@router.get(
    "/asistencia/eventos",
    response_model=EventosResponse,
    summary=_AVISO + "Consultar checadas para el panel en vivo",
    description=_AVISO
    + "Devuelve los eventos en memoria, ordenados cronológicamente. `desde` es "
    "inclusivo. Un cliente sin eventos devuelve una lista vacía, no 404.",
)
async def consultar_eventos(
    cliente: str = Query(default=CLIENTE_DEMO),
    desde: datetime | None = Query(default=None, description="Inclusivo"),
) -> EventosResponse:
    return EventosResponse(cliente=cliente, eventos=almacen.eventos(cliente, desde))


@router.post(
    "/asistencia/cerrar-periodo",
    response_model=CerrarPeriodoResponse,
    summary=_AVISO + "Cerrar el periodo y calcular incidencias",
    description=_AVISO
    + "Días trabajados, faltas y retardos a partir de las checadas del periodo. "
    "`dias_cotizados` es informativo: la base de cuotas del IMSS la determina "
    "`DiasDelPeriodo` según el ramo (§D3).",
)
async def cerrar(req: CerrarPeriodoRequest) -> CerrarPeriodoResponse:
    incidencias, desconocidos = cerrar_periodo(
        almacen.eventos(req.cliente),
        req.empleados,
        req.periodo,
        req.horario,
    )
    return CerrarPeriodoResponse(
        cliente=req.cliente,
        periodo=req.periodo,
        incidencias=incidencias,
        empleados_desconocidos=desconocidos,
    )
