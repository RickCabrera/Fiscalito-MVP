"""
Qué renglones de cada tabla son de un despacho (P6-01).

SE DERIVA DEL ESQUEMA, NO DE UNA LISTA A MANO
---------------------------------------------
Exportar y borrar un despacho tienen que cubrir TODAS sus tablas, incluidas las que se agreguen
después. Por eso el alcance se calcula desde `Base.metadata`: una tabla es del despacho si
tiene columna `despacho_id` (igual al id), si es `despachos` (su propio renglón), o si alguna
llave foránea apunta a una tabla que a su vez es del despacho (clientes → comprobantes →
verificaciones_cfdi…). Una tabla sin camino es GLOBAL (listas 69-B, ejecuciones programadas)
y no entra. `tests/plan_p/test_cuenta_despacho.py` recorre el metadata y falla si una tabla
con `cliente_id` o `despacho_id` queda fuera.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import ColumnElement, Table, select

import app.modelos  # noqa: F401 — registra todas las tablas
from app.db.base import Base

TABLAS_GLOBALES_CONOCIDAS = frozenset({
    "cargas_lista_sat", "contribuyentes_lista_sat", "ejecuciones_programadas",
})
# Tiene `despacho_id` pero es la lápida que sobrevive al borrado: ni se exporta ni se borra.
TABLAS_EXCLUIDAS = frozenset({"bajas_despacho"})


def _filtro(tabla: Table, despacho_id: str, memo: dict[str, Any], en_curso: set[str]) -> Any:
    """Condición SQL (o None si la tabla no es del despacho)."""
    if tabla.name in memo:
        return memo[tabla.name]
    if tabla.name == "despachos":
        memo[tabla.name] = tabla.c.id == despacho_id
        return memo[tabla.name]
    if "despacho_id" in tabla.c:
        memo[tabla.name] = tabla.c.despacho_id == despacho_id
        return memo[tabla.name]
    en_curso.add(tabla.name)
    condiciones: list[ColumnElement[bool]] = []
    for fk in tabla.foreign_keys:
        padre = fk.column.table
        if padre.name == tabla.name or padre.name in en_curso:
            continue  # autorreferencia o ciclo: no define pertenencia
        cond_padre = _filtro(padre, despacho_id, memo, en_curso)
        if cond_padre is None:
            continue
        pk_padre = list(padre.primary_key.columns)[0]
        condiciones.append(fk.parent.in_(select(pk_padre).where(cond_padre)))
    en_curso.discard(tabla.name)
    resultado = condiciones[0] if condiciones else None
    # Varias FK que llevan al despacho (p. ej. `facturas.cliente_id` y `cliente_receptor_id`):
    # basta con que una pertenezca. Las de `SET NULL` dejan el renglón al borrar el otro lado.
    if len(condiciones) > 1:
        from sqlalchemy import or_

        resultado = or_(*condiciones)
    memo[tabla.name] = resultado
    return resultado


def tablas_del_despacho(despacho_id: str) -> list[tuple[Table, Any]]:
    """[(tabla, condición)] en orden de dependencias (padres primero) para ese despacho."""
    memo: dict[str, Any] = {}
    salida: list[tuple[Table, Any]] = []
    for tabla in Base.metadata.sorted_tables:
        if tabla.name in TABLAS_EXCLUIDAS:
            continue
        cond = _filtro(tabla, despacho_id, memo, set())
        if cond is not None:
            salida.append((tabla, cond))
    return salida


def tablas_globales() -> list[str]:
    """Las tablas que no pertenecen a ningún despacho."""
    con_dueno = {t.name for t, _ in tablas_del_despacho("x")}
    return [t.name for t in Base.metadata.sorted_tables if t.name not in con_dueno]
