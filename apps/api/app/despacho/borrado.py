"""
Borrar un despacho entero (P6-01): todas sus tablas, sus archivos del almacén y su despacho.

POR QUÉ NO SE CONFÍA SÓLO EN `ON DELETE CASCADE`
-------------------------------------------------
Las llaves foráneas cascan desde `despachos`, pero (1) SQLite sólo las aplica con el PRAGMA
encendido, (2) `cuentas_contables.padre_id` y `cuentas_bancarias.cuenta_contable_id` son
RESTRICT y en Postgres se revisan renglón por renglón dentro del mismo DELETE, y (3) los
archivos del almacén no saben de cascadas. Así que se borra tabla por tabla, hijas antes que
padres (`sorted_tables` al revés), con el mismo alcance que la exportación, y las cuentas
contables de las hojas a la raíz. Al final cae `despachos` y queda la lápida en
`bajas_despacho`.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.despacho.alcance import tablas_del_despacho
from app.integraciones.almacenamiento import Almacenamiento, obtener_almacenamiento
from app.modelos.cuenta import BajaDespacho
from app.modelos.nucleo import Despacho
from app.modelos.trabajos import Trabajo

logger = logging.getLogger(__name__)


def _rutas_del_despacho(db: Session, despacho_id: str) -> list[str]:
    rutas: set[str] = set()
    for tabla, condicion in tablas_del_despacho(despacho_id):
        columnas = [c for c in tabla.c if c.name == "ruta" or c.name.startswith("ruta_")]
        for columna in columnas:
            for (valor,) in db.execute(select(columna).where(condicion)):
                if valor:
                    rutas.add(str(valor))
    return sorted(rutas)


def _borrar_cuentas_contables(db: Session, condicion: Any) -> int:
    """De las hojas a la raíz: `padre_id` es RESTRICT."""
    tabla = Base.metadata.tables["cuentas_contables"]
    total = 0
    while True:
        con_hijos = select(tabla.c.padre_id).where(
            tabla.c.padre_id.is_not(None), condicion
        )
        borrados = db.execute(
            delete(tabla).where(condicion, tabla.c.id.not_in(con_hijos))
        ).rowcount
        total += borrados
        if borrados == 0:
            return total


def borrar_despacho(
    db: Session,
    despacho_id: str,
    *,
    uid: str,
    almacen: Almacenamiento | None = None,
) -> tuple[dict[str, Any], list[str]]:
    """
    Borra todos los renglones del despacho y deja la lápida, dentro de la transacción de `db`
    (sin commit). Devuelve ({tabla: renglones borrados, "archivos": n}, rutas a borrar del
    almacén con `borrar_archivos` una vez confirmada la transacción).
    """
    from app.despacho.respaldos import leer_indice, ruta_indice

    almacen = almacen or obtener_almacenamiento()
    despacho = db.get(Despacho, despacho_id)
    nombre = despacho.nombre if despacho is not None else ""
    rutas = _rutas_del_despacho(db, despacho_id)
    # Los respaldos también son datos del despacho: se van con él (y su índice).
    rutas += [e["ruta"] for e in leer_indice(almacen, despacho_id)] + [ruta_indice(despacho_id)]
    # Y los ZIP de exportación (su ruta vive en el resultado del trabajo, no en una columna).
    for resultado in db.scalars(select(Trabajo.resultado).where(
        Trabajo.despacho_id == despacho_id, Trabajo.tipo == "despacho.exportar"
    )):
        if resultado and resultado.get("ruta"):
            rutas.append(str(resultado["ruta"]))
    conteos: dict[str, int] = {}
    for tabla, condicion in reversed(tablas_del_despacho(despacho_id)):
        if tabla.name == "cuentas_contables":
            conteos[tabla.name] = _borrar_cuentas_contables(db, condicion)
            continue
        conteos[tabla.name] = db.execute(delete(tabla).where(condicion)).rowcount
    db.expunge_all()  # el ORM ya no debe recordar nada de lo borrado
    rutas = sorted({r for r in rutas if almacen.existe(r)})
    db.add(BajaDespacho(despacho_id=despacho_id, nombre=nombre, uid=uid,
                        borrado={**conteos, "archivos": len(rutas)}))
    db.flush()
    logger.warning("Despacho %s borrado por %s: %s", despacho_id, uid,
                   {k: v for k, v in conteos.items() if v})
    return {**conteos, "archivos": len(rutas)}, rutas


def borrar_archivos(rutas: list[str], almacen: Almacenamiento | None = None) -> int:
    """
    Borra del almacén los archivos del despacho. Se llama DESPUÉS del commit (la ruta lo
    agenda como tarea de fondo): si la transacción fallara, los renglones seguirían ahí y sus
    archivos también.
    """
    almacen = almacen or obtener_almacenamiento()
    borrados = 0
    for ruta in rutas:
        try:
            almacen.borrar(ruta)
            borrados += 1
        except Exception:  # noqa: BLE001 — un archivo que no se deja borrar queda en el log
            logger.exception("No se pudo borrar %s del almacén", ruta)
    return borrados
