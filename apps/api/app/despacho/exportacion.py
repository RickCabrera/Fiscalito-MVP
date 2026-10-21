"""
Exportar todo lo de un despacho a un ZIP (P6-01): un JSON por tabla + los archivos del
almacenamiento (XML de la bóveda, PDF, acuses) + `manifiesto.json`.

Lo usan la exportación que pide el dueño (`POST /despacho/exportar`, en segundo plano) y el
respaldo programado (`app/despacho/respaldos.py`). Las columnas cifradas (CLABE, número de
cuenta) salen EN CLARO: es el despacho sacando sus propios datos. Las credenciales
(`credenciales_cliente.key_cifrada`, `password_cifrada`) salen cifradas con la llave maestra:
sin ella no sirven a nadie, y el despacho tiene los archivos originales de su e.firma.
"""

from __future__ import annotations

import base64
import io
import json
import logging
import zipfile
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import ahora
from app.despacho.alcance import tablas_del_despacho
from app.integraciones.almacenamiento import Almacenamiento, obtener_almacenamiento

logger = logging.getLogger(__name__)

VERSION_EXPORTACION = 1


def _json(valor: Any) -> Any:
    if isinstance(valor, (datetime, date)):
        return valor.isoformat()
    if isinstance(valor, Decimal):
        return str(valor)
    if isinstance(valor, (bytes, bytearray)):
        return {"$base64": base64.b64encode(bytes(valor)).decode("ascii")}
    return str(valor)


def _es_ruta(nombre: str) -> bool:
    return nombre == "ruta" or nombre.startswith("ruta_")


def exportar_despacho(
    db: Session, despacho_id: str, *, almacen: Almacenamiento | None = None
) -> tuple[bytes, dict[str, Any]]:
    """El ZIP (bytes) y su manifiesto {tablas: {nombre: renglones}, archivos, faltantes}."""
    almacen = almacen or obtener_almacenamiento()
    buffer = io.BytesIO()
    conteos: dict[str, int] = {}
    rutas: list[str] = []
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for tabla, condicion in tablas_del_despacho(despacho_id):
            filas = db.execute(select(tabla).where(condicion)).mappings().all()
            renglones = [dict(f) for f in filas]
            conteos[tabla.name] = len(renglones)
            zf.writestr(
                f"tablas/{tabla.name}.json",
                json.dumps(renglones, ensure_ascii=False, default=_json, indent=1),
            )
            for columna in tabla.c:
                if _es_ruta(columna.name):
                    rutas.extend(
                        str(r[columna.name]) for r in renglones if r.get(columna.name)
                    )
        archivos, faltantes = 0, []
        for ruta in sorted(set(rutas)):
            try:
                zf.writestr(f"archivos/{ruta}", almacen.leer(ruta))
                archivos += 1
            except Exception:  # noqa: BLE001 — un archivo perdido no cancela la exportación
                faltantes.append(ruta)
        manifiesto = {
            "version": VERSION_EXPORTACION,
            "despacho_id": despacho_id,
            "generado_en": ahora().isoformat(),
            "tablas": conteos,
            "archivos": archivos,
            "archivos_faltantes": faltantes,
        }
        zf.writestr("manifiesto.json", json.dumps(manifiesto, ensure_ascii=False, indent=1))
    if faltantes:
        logger.warning("Exportación de %s: %s archivos no estaban en el almacén",
                       despacho_id, len(faltantes))
    return buffer.getvalue(), manifiesto
