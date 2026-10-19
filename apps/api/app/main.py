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

from app.acceso.dependencias import PROTEGIDO
from app.auditoria import AuditoriaMiddleware
from app.config import settings
from app.exceptions import FiscalAgentError, LimiteExcedido
from app.logging_config import setup_logging
from app.routes import (
    agente,
    asistencia,
    auditoria,
    boveda,
    calendario,
    cartera,
    comparador,
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
    # P0-02: el checador puede mandar su token en `X-Token-Dispositivo`.
    allow_headers=["Content-Type", "Authorization", "X-Token-Dispositivo"],
    # Que el front pueda leer cuánto esperar tras un 429.
    expose_headers=["Retry-After"],
)

@app.exception_handler(FiscalAgentError)
async def fiscal_error_handler(request: Request, exc: FiscalAgentError) -> JSONResponse:
    """Manejador global para excepciones de dominio fiscal."""
    encabezados = (
        {"Retry-After": str(exc.reintentar_en)} if isinstance(exc, LimiteExcedido) else None
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"exito": False, "error": exc.message},
        headers=encabezados,
    )


# P0-02: TODO /api/v1 exige la sesión de Firebase (y el límite por usuario). Un router nuevo
# se agrega a esta lista y queda protegido; `tests/test_acceso_rutas.py` recorre todas las
# rutas y falla si alguna responde sin token. Las excepciones públicas se declaran en
# `app/acceso/dependencias.RUTAS_PUBLICAS` y se montan abajo, aparte.
ROUTERS_PROTEGIDOS = (
    declaraciones.router,
    calendario.router,
    comparador.router,
    diot.router,
    retenciones.router,
    multi_periodo.router,
    estado_cuenta.router,
    agente.router,
    asistencia.router,
    nomina.router,
    despacho.router,
    # R-07: la cartera ya exigía su propio token; aquí además entra al límite por usuario.
    cartera.router,
    # Plan P: bóveda de CFDI (P0-03), e.firma/CSD (P0-05), trabajos (P0-04), auditoría (P0-07).
    boveda.router,
    credenciales.router,
    trabajos.router,
    auditoria.router,
    # P1: descarga masiva del SAT (P1-01/02) y verificaciones SAT (P1-03/04/05).
    sat_descarga.router,
    sat_verificacion.router,
)

app.include_router(health.router)
for _router in ROUTERS_PROTEGIDOS:
    app.include_router(_router, prefix="/api/v1", dependencies=PROTEGIDO)

# Públicas (sin sesión de Firebase): cada una se autentica por dentro.
# - El push del checador: token de dispositivo (o la sesión, para el simulador).
app.include_router(asistencia.router_publico, prefix="/api/v1")

# Plan P: en desarrollo, crea las tablas que falten (en producción manda Alembic).
if settings.ENTORNO != "produccion":
    from app.db.session import crear_tablas

    crear_tablas()

logger.info("Fiscal Agent API inicializada correctamente")
