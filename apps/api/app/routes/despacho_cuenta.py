"""
`/api/v1/despacho/exportar` y `/api/v1/despacho/borrar` — derechos sobre los datos (P6-01).

Sólo el rol `dueno`. Contrato: `docs/api-contract.md` §"Cuenta del despacho".

- `POST /despacho/exportar` encola `despacho.exportar` (segundo plano) y devuelve el trabajo.
- `GET /despacho/exportar/{trabajo_id}` dice cómo va; ya hecho, trae el enlace firmado.
- `GET /despacho/exportaciones/{trabajo_id}/descarga?vence=&firma=` (PÚBLICA, HMAC con
  `FISCALITO_ENLACES_SECRETO`, vigencia de 7 días) baja el ZIP. Firma mala o vencida = 404.
- `POST /despacho/borrar` con `{"confirmacion": "BORRAR MI DESPACHO"}` borra TODO, sin vuelta
  atrás, y deja la lápida en `bajas_despacho`.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import time
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

import app.despacho.respaldos  # noqa: F401 — registra los manejadores
from app.auditoria import estado_actual, registrar
from app.db.session import obtener_db
from app.despacho.borrado import borrar_archivos, borrar_despacho
from app.despacho.respaldos import DIAS_EXPORTACION
from app.exceptions import FiscalAgentError
from app.integraciones.almacenamiento import obtener_almacenamiento
from app.modelos.trabajos import Trabajo
from app.nomina_envio.enlaces import secreto
from app.tenancy import Contexto, contexto_actual, exigir_rol
from app.trabajos import encolar

router = APIRouter(prefix="/despacho", tags=["Cuenta del despacho"])
router_publico = APIRouter(prefix="/despacho", tags=["Cuenta del despacho"])

FRASE_BORRADO = "BORRAR MI DESPACHO"
VIGENCIA_SEGUNDOS = DIAS_EXPORTACION * 24 * 3600


class BorrarIn(BaseModel):
    confirmacion: str = Field(max_length=100)


def _firma(trabajo_id: int, vence: int) -> str:
    return hmac.new(secreto(), f"exportacion:{trabajo_id}:{vence}".encode(),
                    hashlib.sha256).hexdigest()


def url_firmada(trabajo_id: int, ahora: float | None = None) -> str:
    vence = int((ahora or time.time()) + VIGENCIA_SEGUNDOS)
    base = os.environ.get("FISCALITO_URL_PUBLICA_API", "http://localhost:8000").rstrip("/")
    return (f"{base}/api/v1/despacho/exportaciones/{trabajo_id}/descarga"
            f"?vence={vence}&firma={_firma(trabajo_id, vence)}")


def _trabajo_json(t: Trabajo) -> dict[str, Any]:
    r = t.resultado or {}
    hecho = t.estado == "hecho" and not r.get("purgada")
    return {"id": t.id, "estado": t.estado, "error": t.error,
            "creado_en": t.creado_en.isoformat() if t.creado_en else None,
            "bytes": r.get("bytes"), "tablas": r.get("tablas"), "archivos": r.get("archivos"),
            "url": url_firmada(t.id) if hecho else None,
            "vence_en": r.get("vence_en") if hecho else None}


@router.post("/exportar", summary="Exportar todos los datos del despacho (ZIP, segundo plano)")
def exportar(ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    exigir_rol(ctx, "dueno")
    t = encolar(ctx.db, "despacho.exportar", {}, despacho_id=ctx.despacho_id,
                clave_unica=f"exportar:{ctx.despacho_id}", max_intentos=3)
    registrar(ctx, "despacho.exportar", "trabajo", t.id)
    return {"exito": True, "trabajo": _trabajo_json(t)}


@router.get("/exportar/{trabajo_id}", summary="Estado de una exportación y su enlace")
def estado_exportacion(trabajo_id: int, ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    exigir_rol(ctx, "dueno")
    t = ctx.db.get(Trabajo, trabajo_id)
    if t is None or t.despacho_id != ctx.despacho_id or t.tipo != "despacho.exportar":
        raise FiscalAgentError(f"No existe la exportación {trabajo_id}.", status_code=404)
    return {"exito": True, "trabajo": _trabajo_json(t)}


@router.post("/borrar", summary="Borrar la cuenta del despacho y todos sus datos")
def borrar(cuerpo: BorrarIn, tareas: BackgroundTasks,
           ctx: Contexto = Depends(contexto_actual)) -> dict[str, Any]:
    exigir_rol(ctx, "dueno")
    if cuerpo.confirmacion.strip() != FRASE_BORRADO:
        raise FiscalAgentError(
            f'Para borrar escribe exactamente "{FRASE_BORRADO}".', status_code=422)
    conteos, rutas = borrar_despacho(ctx.db, ctx.despacho_id, uid=ctx.uid)
    # Los archivos, después del commit (las tareas de fondo corren tras cerrar la sesión).
    tareas.add_task(borrar_archivos, rutas)
    # La bitácora del despacho se fue con él; la constancia queda en `bajas_despacho`. Que el
    # middleware de auditoría no intente escribir un renglón de un despacho que ya no existe.
    estado = estado_actual()
    if estado is not None:
        estado.registrados += 1
    return {"exito": True, "borrado": conteos}


@router_publico.get("/exportaciones/{trabajo_id}/descarga",
                    summary="Descarga del ZIP de exportación (enlace firmado)")
def descargar(trabajo_id: int, vence: int = Query(...), firma: str = Query(...),
              db: Session = Depends(obtener_db)) -> Response:
    no_existe = FiscalAgentError("No existe el archivo.", status_code=404)
    if vence < time.time() or not hmac.compare_digest(_firma(trabajo_id, vence), firma or ""):
        raise no_existe
    t = db.get(Trabajo, trabajo_id)
    ruta = (t.resultado or {}).get("ruta") if t is not None and t.estado == "hecho" else None
    if t is None or t.tipo != "despacho.exportar" or not ruta or t.resultado.get("purgada"):
        raise no_existe
    datos = obtener_almacenamiento().leer(ruta)
    return Response(datos, media_type="application/zip", headers={
        "Content-Disposition": f'attachment; filename="fiscalito-exportacion-{trabajo_id}.zip"'})
