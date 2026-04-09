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
