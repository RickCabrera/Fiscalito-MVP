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
    agenda,
    agente,
    alertas,
    asistencia,
    asistente,
    auditoria,
    boveda,
    calculadoras,
    calculadoras_laborales,
    calculos_cliente,
    calendario,
    cartera,
    cobranza,
    comparador,
    conciliacion,
    contabilidad,
    contabilidad_electronica,
    contabilidad_reportes,
    credenciales,
    dashboard,
    declaraciones,
    despacho,
    diot,
    diot_cliente,
    equipo,
    estado_cuenta,
    health,
    impuestos,
    impuestos_anual,
    multi_periodo,
    nomina,
    nomina_anual,
    nomina_calculos,
    nomina_cuotas,
    nomina_dispersion,
    nomina_envio,
    nomina_historial,
    nomina_imss,
    nomina_periodo,
    nomina_timbrado,
    retenciones,
    retenciones_cfdi,
    sat_descarga,
    sat_verificacion,
    trabajos,
    whatsapp,
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
    origin.strip() for origin in settings.CORS_ORIGINS.split(",") if origin.strip()
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
    # P4: nómina con plantilla de la cartera, historial y extraordinarias.
    nomina_periodo.router,
    nomina_historial.router,
    # P4-12 dispersión bancaria y P4-13 envío de recibos.
    nomina_dispersion.router,
    nomina_envio.router,
    nomina_calculos.router,
    nomina_anual.router,
    # P4-09 movimientos IMSS, P4-10 cuotas y cédulas, P4-11 timbrado de nómina.
    nomina_imss.router,
    nomina_cuotas.router,
    nomina_timbrado.router,
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
    calculos_cliente.router,
    contabilidad.router,
    impuestos.router,
    calculadoras.router,
    calculadoras_laborales.router,
    # P2-05/P2-08: reportes contables y cierre de periodo y de ejercicio.
    contabilidad_reportes.router,
    # P2-06 conciliación bancaria y P2-07 contabilidad electrónica (Anexo 24).
    conciliacion.router,
    contabilidad_electronica.router,
    # P3-01 personas morales y P3-06 anual con papeles de trabajo.
    impuestos_anual.router,
    # P3-04 CFDI de retenciones, P3-05 DIOT 2025, P3-09 alertas, P3-10 calendario y agenda.
    retenciones_cfdi.router,
    diot_cliente.router,
    alertas.router,
    agenda.router,
    # P5-01 equipo del despacho, P5-02 dashboard, P5-03 cuentas por cobrar.
    equipo.router,
    dashboard.router,
    cobranza.router,
    # P5-06 bot de WhatsApp (contactos y bitácora) y P5-07 asistente IA (chat y voz).
    whatsapp.router,
    asistente.router,
)

app.include_router(health.router)
for _router in ROUTERS_PROTEGIDOS:
    app.include_router(_router, prefix="/api/v1", dependencies=PROTEGIDO)

# Públicas (sin sesión de Firebase): cada una se autentica por dentro.
# - El push del checador: token de dispositivo (o la sesión, para el simulador).
app.include_router(asistencia.router_publico, prefix="/api/v1")
# - P4-13: descarga del recibo para WhatsApp, con enlace firmado (HMAC) y vigencia.
app.include_router(nomina_envio.router_publico, prefix="/api/v1")
# - P5-06: webhook del bot (firma del proveedor) y descarga del documento (enlace firmado).
app.include_router(whatsapp.router_publico, prefix="/api/v1")

# Plan P: en desarrollo, crea las tablas que falten (en producción manda Alembic).
if settings.ENTORNO != "produccion":
    from app.db.session import crear_tablas

    crear_tablas()

logger.info("Fiscal Agent API inicializada correctamente")
