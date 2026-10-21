"""Esquemas de `/api/v1/trabajos` (P0-04) y `/api/v1/auditoria` (P0-07)."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class TrabajoSalida(BaseModel):
    """Un trabajo tal como lo ve el despacho. `cliente` es la clave pública, no el id."""

    id: int
    tipo: str
    estado: str
    cliente: str | None
    intentos: int
    max_intentos: int
    ejecutar_en: datetime
    iniciado_en: datetime | None
    terminado_en: datetime | None
    creado_en: datetime
    error: str | None
    resultado: dict[str, Any] | None
    carga: dict[str, Any]


class ListaTrabajos(BaseModel):
    exito: bool = True
    trabajos: list[TrabajoSalida]


class UnTrabajo(BaseModel):
    exito: bool = True
    trabajo: TrabajoSalida


class EncolarDiagnostico(BaseModel):
    """Cuerpo de `POST /trabajos/clientes/{clave}/diagnostico`."""

    fallar_intentos: int = 0


class EventoSalida(BaseModel):
    id: int
    fecha: datetime
    uid: str
    cliente: str | None
    accion: str
    entidad: str
    entidad_id: str
    detalle: dict[str, Any]
    ip: str


class PaginaAuditoria(BaseModel):
    exito: bool = True
    eventos: list[EventoSalida]
    total: int
    pagina: int
    por_pagina: int
