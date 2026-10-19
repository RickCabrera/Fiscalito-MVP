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

from app.auditoria import AuditoriaMiddleware
from app.config import settings
from app.exceptions import FiscalAgentError
from app.logging_config import setup_logging
from app.routes import (
    agente,
    asistencia,
    auditoria,
    boveda,
    calendario,
    cartera,
    comparador,
    contabilidad,
    credenciales,
    declaraciones,
    despacho,
    diot,
    estado_cuenta,
    health,
    multi_periodo,
    nomina,
    retenciones,
    sat_descarga,
    sat_verificacion,
    trabajos,
)

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
# P0-07: renglón de auditoría por cada escritura autenticada (red de seguridad).
app.add_middleware(AuditoriaMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=cors_origins != ["*"],
    # R-07: el CRUD de la cartera usa PUT y DELETE. Sin ellos el navegador
    # falla en el PREFLIGHT, y eso no se ve como un problema de permisos: se ve
    # como red caída, que manda a buscar el bug al lugar equivocado.
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
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
app.include_router(asistencia.router, prefix="/api/v1")
app.include_router(nomina.router, prefix="/api/v1")
app.include_router(despacho.router, prefix="/api/v1")
# R-07: el único router del repo que EXIGE autenticación. El resto de /api/v1
# sigue abierto (S-00b) y eso no cambia aquí.
app.include_router(cartera.router, prefix="/api/v1")
# Plan P, P0-03: bóveda de CFDI por cliente (contexto_actual + cliente_o_404).
app.include_router(boveda.router, prefix="/api/v1")
# P0-05: bóveda de e.firma y CSD por cliente (autenticada y multi-despacho).
app.include_router(credenciales.router, prefix="/api/v1")
# Plan P: trabajos en segundo plano (P0-04) y bitácora de auditoría (P0-07).
app.include_router(trabajos.router, prefix="/api/v1")
app.include_router(auditoria.router, prefix="/api/v1")
# P1-01/P1-02: descarga masiva del SAT por cliente (config, rangos, solicitudes, bitácora).
app.include_router(sat_descarga.router, prefix="/api/v1")
# P1-03/04/05: estatus de CFDI, listas 69-B y opinión de cumplimiento.
app.include_router(sat_verificacion.router, prefix="/api/v1")
# P2-01/02/03/04: catálogo, reglas de pólizas, pólizas y balanza por cliente.
app.include_router(contabilidad.router, prefix="/api/v1")

# Plan P: en desarrollo, crea las tablas que falten (en producción manda Alembic).
if settings.ENTORNO != "produccion":
    from app.db.session import crear_tablas

    crear_tablas()

logger.info("Fiscal Agent API inicializada correctamente")
