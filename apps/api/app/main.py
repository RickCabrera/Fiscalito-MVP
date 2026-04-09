"""
Fiscal Agent API — Motor de inteligencia fiscal
Servicio independiente que calcula declaraciones ISR/IVA,
analiza CFDIs y asesora sobre regimen fiscal mexicano.

Autor: Ricardo Cabrera
"""

import logging
import time

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.exceptions import FiscalAgentError
from app.logging_config import setup_logging
from app.routes import declaraciones, health, calendario, comparador, diot, retenciones, multi_periodo, estado_cuenta, agente
from app.config import settings

# Inicializar logging estructurado al arrancar la aplicacion
setup_logging()

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware que registra metodo, ruta, status y tiempo de cada request."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Procesa el request y registra metricas basicas."""
        start_time = time.perf_counter()
        response = await call_next(request)
        process_time_ms = (time.perf_counter() - start_time) * 1000

        logger.info(
            "HTTP %s %s -> %d (%.1fms)",
            request.method,
            request.url.path,
            response.status_code,
            process_time_ms,
        )
        return response


app = FastAPI(
    title="Fiscal Agent API",
    description="Motor de inteligencia fiscal para el ecosistema Fiscalito",
    version="0.1.0",
    contact={"name": "Ricardo Cabrera"},
)

cors_origins: list[str] = [
    origin.strip()
    for origin in settings.CORS_ORIGINS.split(",")
    if origin.strip()
]

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=cors_origins != ["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

@app.exception_handler(FiscalAgentError)
async def fiscal_error_handler(request: Request, exc: FiscalAgentError) -> JSONResponse:
    """Manejador global para excepciones de dominio fiscal."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"exito": False, "error": exc.message},
    )


app.include_router(health.router)
app.include_router(declaraciones.router, prefix="/api/v1")
app.include_router(calendario.router, prefix="/api/v1")
app.include_router(comparador.router, prefix="/api/v1")
app.include_router(diot.router, prefix="/api/v1")
app.include_router(retenciones.router, prefix="/api/v1")
app.include_router(multi_periodo.router, prefix="/api/v1")
app.include_router(estado_cuenta.router, prefix="/api/v1")
app.include_router(agente.router, prefix="/api/v1")

logger.info("Fiscal Agent API inicializada correctamente")
