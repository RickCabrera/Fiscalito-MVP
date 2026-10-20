"""Dashboard del despacho (P5-02): la pantalla de entrada en una sola llamada."""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends

from app.dashboard import servicio
from app.tenancy import Contexto, contexto_actual

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard")
def dashboard(hoy: date | None = None, ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    """Tarjetas del despacho para los clientes que el usuario ve (ver `app/dashboard`)."""
    return servicio.dashboard(ctx, hoy)
