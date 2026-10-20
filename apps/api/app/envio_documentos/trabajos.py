"""Manejador del trabajo `documentos.enviar` (P5-05). Idempotente: ver `servicio.py`."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.envio_documentos import servicio
from app.modelos.trabajos import Trabajo
from app.trabajos.cola import manejador


@manejador(servicio.TIPO_TRABAJO)
def enviar_documentos(db: Session, trabajo: Trabajo) -> dict[str, Any]:
    return servicio.enviar_lote(db, trabajo.despacho_id or "", int(trabajo.carga["cliente_id"]))
