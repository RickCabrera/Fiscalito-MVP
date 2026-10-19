"""Health check endpoint."""

from fastapi import APIRouter
from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Modelo de respuesta del endpoint de salud."""
    status: str
    service: str
    version: str


router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Retorna el estado del servicio."""
    return HealthResponse(status="ok", service="fiscal-agent-api", version="0.1.0")


@router.get("/health/integraciones")
def health_integraciones() -> dict:
    """Qué implementación usa cada servicio externo y si falta configurar alguno (P0-06)."""
    from app.integraciones.registro import verificar_configuracion

    servicios = verificar_configuracion()
    return {
        "listo_para_produccion": all(s["configurado"] and not s["es_falso"] for s in servicios),
        "servicios": servicios,
    }
