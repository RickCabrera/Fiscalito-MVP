"""
Respaldos programados y exportación en segundo plano (P6-01).

RESPALDO = EL MISMO ZIP QUE LA EXPORTACIÓN, UNO POR DESPACHO Y POR DÍA
----------------------------------------------------------------------
La tarea recurrente `respaldos_despachos` (03:30, `app/trabajos/programacion.py`) encola un
trabajo `despacho.respaldar` por despacho. Cada uno escribe
`respaldos/<despacho>/<AAAA-MM-DD>.zip` en el almacenamiento (adaptador `almacenamiento`:
disco en desarrollo, S3/R2 en producción) y mantiene `respaldos/<despacho>/indice.json` con
la lista de respaldos; los de más de `FISCALITO_RESPALDOS_RETENCION_DIAS` días (default 30)
se borran. El almacenamiento no sabe listar, por eso existe el índice. Idempotente: el ZIP
del día se sobrescribe y el índice no duplica.

`FISCALITO_RESPALDOS_ACTIVOS=0` apaga la tarea (p. ej. en un entorno de pruebas).

La exportación que pide el dueño (`despacho.exportar`) escribe
`exportaciones/<despacho>/<trabajo_id>.zip` y la ruta se descarga con enlace firmado
(`app/routes/despacho_cuenta.py`). No entra al índice de respaldos ni a su retención: la
borra `despacho.purgar_exportaciones` pasados `DIAS_EXPORTACION` días.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import ahora
from app.despacho.exportacion import exportar_despacho
from app.integraciones.almacenamiento import Almacenamiento, obtener_almacenamiento
from app.modelos.nucleo import Despacho
from app.modelos.trabajos import Trabajo
from app.trabajos.cola import encolar, manejador

logger = logging.getLogger(__name__)

RETENCION_DEFAULT_DIAS = 30
DIAS_EXPORTACION = 7


def retencion_dias() -> int:
    crudo = os.environ.get("FISCALITO_RESPALDOS_RETENCION_DIAS", "").strip()
    return int(crudo) if crudo.isdigit() else RETENCION_DEFAULT_DIAS


def respaldos_activos() -> bool:
    return os.environ.get("FISCALITO_RESPALDOS_ACTIVOS", "1").strip().lower() not in (
        "0", "no", "false", "off"
    )


def ruta_indice(despacho_id: str) -> str:
    return f"respaldos/{despacho_id}/indice.json"


def ruta_respaldo(despacho_id: str, momento: datetime) -> str:
    return f"respaldos/{despacho_id}/{momento.date().isoformat()}.zip"


def ruta_exportacion(despacho_id: str, trabajo_id: int) -> str:
    return f"exportaciones/{despacho_id}/{trabajo_id}.zip"


def leer_indice(almacen: Almacenamiento, despacho_id: str) -> list[dict[str, Any]]:
    ruta = ruta_indice(despacho_id)
    if not almacen.existe(ruta):
        return []
    try:
        datos = json.loads(almacen.leer(ruta).decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        logger.warning("Índice de respaldos ilegible en %s; se reconstruye", ruta)
        return []
    return [d for d in datos if isinstance(d, dict) and d.get("ruta")]


def encolar_respaldos(db: Session, ranura: datetime) -> list[Trabajo]:
    """Un trabajo `despacho.respaldar` por despacho (lo llama el programador)."""
    if not respaldos_activos():
        return []
    trabajos = []
    for despacho_id in db.scalars(select(Despacho.id)):
        trabajos.append(encolar(
            db, "despacho.respaldar", {"despacho_id": despacho_id, "ranura": ranura.isoformat()},
            despacho_id=despacho_id, ejecutar_en=ranura,
            clave_unica=f"prog:respaldo:{despacho_id}:{ranura.date().isoformat()}",
            max_intentos=3,
        ))
    return trabajos


def respaldar(
    db: Session, despacho_id: str, *, momento: datetime | None = None,
    almacen: Almacenamiento | None = None,
) -> dict[str, Any]:
    """Escribe el respaldo del día, actualiza el índice y aplica la retención."""
    almacen = almacen or obtener_almacenamiento()
    momento = momento or ahora()
    zip_bytes, manifiesto = exportar_despacho(db, despacho_id, almacen=almacen)
    ruta = ruta_respaldo(despacho_id, momento)
    # Carrera con `/despacho/borrar` (revisor P6): si el despacho ya no existe, no se escribe
    # un respaldo póstumo de lo que se acaba de borrar.
    if db.get(Despacho, despacho_id) is None:
        return {"omitido": "el despacho ya no existe"}
    almacen.guardar(zip_bytes, ruta)
    indice = [e for e in leer_indice(almacen, despacho_id) if e["ruta"] != ruta]
    indice.append({"ruta": ruta, "fecha": momento.isoformat(), "bytes": len(zip_bytes),
                   "tablas": sum(manifiesto["tablas"].values()),
                   "archivos": manifiesto["archivos"]})
    limite = momento - timedelta(days=retencion_dias())
    vigentes, borrados = [], 0
    for entrada in sorted(indice, key=lambda e: e["fecha"]):
        fecha = datetime.fromisoformat(entrada["fecha"])
        if fecha < limite and entrada["ruta"] != ruta:
            almacen.borrar(entrada["ruta"])
            borrados += 1
        else:
            vigentes.append(entrada)
    almacen.guardar(json.dumps(vigentes, ensure_ascii=False, indent=1).encode(),
                    ruta_indice(despacho_id))
    return {"ruta": ruta, "bytes": len(zip_bytes), "respaldos_vigentes": len(vigentes),
            "respaldos_borrados": borrados, "retencion_dias": retencion_dias()}


@manejador("despacho.respaldar")
def _respaldar(db: Session, trabajo: Trabajo) -> dict[str, Any]:
    despacho_id = str(trabajo.carga.get("despacho_id") or trabajo.despacho_id or "")
    if not despacho_id or db.get(Despacho, despacho_id) is None:
        return {"omitido": "el despacho ya no existe"}
    ranura = trabajo.carga.get("ranura")
    momento = datetime.fromisoformat(ranura) if ranura else None
    return respaldar(db, despacho_id, momento=momento)


@manejador("despacho.exportar")
def _exportar(db: Session, trabajo: Trabajo) -> dict[str, Any]:
    despacho_id = str(trabajo.despacho_id or "")
    if not despacho_id or db.get(Despacho, despacho_id) is None:
        raise RuntimeError("El despacho ya no existe.")
    almacen = obtener_almacenamiento()
    zip_bytes, manifiesto = exportar_despacho(db, despacho_id, almacen=almacen)
    ruta = almacen.guardar(zip_bytes, ruta_exportacion(despacho_id, trabajo.id))
    return {"ruta": ruta, "bytes": len(zip_bytes), "tablas": manifiesto["tablas"],
            "archivos": manifiesto["archivos"],
            "archivos_faltantes": len(manifiesto["archivos_faltantes"]),
            "vence_en": (ahora() + timedelta(days=DIAS_EXPORTACION)).isoformat()}


def encolar_purga_exportaciones(db: Session, ranura: datetime) -> Trabajo:
    """Lo llama el programador: borra del almacén las exportaciones vencidas."""
    return encolar(db, "despacho.purgar_exportaciones", {}, ejecutar_en=ranura,
                   clave_unica=f"prog:purgar_exportaciones:{ranura.isoformat()}", max_intentos=3)


@manejador("despacho.purgar_exportaciones")
def _purgar_exportaciones(db: Session, trabajo: Trabajo) -> dict[str, Any]:
    """ZIP de exportaciones con más de DIAS_EXPORTACION días: fuera del almacén. Idempotente."""
    limite = ahora() - timedelta(days=DIAS_EXPORTACION)
    almacen = obtener_almacenamiento()
    purgadas = 0
    for t in db.scalars(select(Trabajo).where(
        Trabajo.tipo == "despacho.exportar", Trabajo.estado == "hecho",
        Trabajo.terminado_en < limite,
    )):
        resultado = dict(t.resultado or {})
        if resultado.get("ruta") and not resultado.get("purgada"):
            almacen.borrar(resultado["ruta"])
            resultado["purgada"] = True
            t.resultado = resultado
            purgadas += 1
    return {"purgadas": purgadas}
