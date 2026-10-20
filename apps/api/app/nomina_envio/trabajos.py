"""Manejador del trabajo `nomina.enviar_recibos` (P4-13). Idempotente: ver `servicio.py`."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.modelos.trabajos import Trabajo
from app.nomina_envio import servicio
from app.trabajos.cola import manejador


@manejador(servicio.TIPO_TRABAJO)
def enviar_recibos(db: Session, trabajo: Trabajo) -> dict[str, Any]:
    return servicio.enviar_lote(db, trabajo.despacho_id or "", int(trabajo.carga["periodo_id"]),
                                str(trabajo.carga["canal"]))
