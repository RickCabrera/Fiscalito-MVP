"""Manejador del trabajo `whatsapp.responder` (P5-06). Idempotente: ver `servicio.py`."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.modelos.trabajos import Trabajo
from app.trabajos.cola import manejador
from app.whatsapp_bot import servicio


@manejador(servicio.TIPO_TRABAJO)
def responder(db: Session, trabajo: Trabajo) -> dict[str, Any]:
    return servicio.responder(db, int(trabajo.carga["mensaje_id"]))
