"""Health check endpoint."""

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import obtener_db


class HealthResponse(BaseModel):
    """Modelo de respuesta del endpoint de salud."""
    status: str
    service: str
    version: str
    # P6-02: base de datos, último latido del worker y del programador, trabajos atorados.
    base_datos: str = "ok"
    procesos: dict[str, Any] | None = None


router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health(db: Session = Depends(obtener_db)) -> HealthResponse:
    """
    Estado del servicio. `status` es `ok` si la API responde y la base contesta; `degradado`
    si la base no contesta o el worker/programador no laten (P6-02). Siempre 200: el
    healthcheck de Railway mide que la API esté viva; lo demás se lee en el cuerpo.
    """
    from app.observabilidad import salud_procesos

    try:
        db.execute(text("SELECT 1"))
        procesos = salud_procesos(db)
        base = "ok"
    except Exception:  # noqa: BLE001 — la base caída se reporta, no se esconde en un 500
        procesos, base = None, "error"
    status = "ok" if base == "ok" and procesos is not None and procesos["sano"] else "degradado"
    return HealthResponse(
        status=status, service="fiscal-agent-api", version="0.1.0", base_datos=base,
        procesos=procesos,
    )


@router.get("/health/integraciones")
def health_integraciones() -> dict:
    """Qué implementación usa cada servicio externo y si falta configurar alguno (P0-06)."""
    from app.integraciones.registro import verificar_configuracion

    servicios = verificar_configuracion()
    return {
        "listo_para_produccion": all(s["configurado"] and not s["es_falso"] for s in servicios),
        "servicios": servicios,
    }
