"""
Acciones del contador sobre la cola: reintentar y cancelar (P0-04).

Salieron de `cola.py` en P6-05 (tope de 300 líneas) sin cambiar comportamiento; `cola` las
reexporta.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.db.base import ahora as _ahora
from app.exceptions import FiscalAgentError
from app.modelos.trabajos import Trabajo
from app.trabajos.cola import _vivo_con_clave


def reintentar(db: Session, trabajo: Trabajo, *, ahora: datetime | None = None) -> Trabajo:
    """Un trabajo `fallido` o `cancelado` vuelve a la cola con sus intentos en cero."""
    if trabajo.estado not in ("fallido", "cancelado"):
        raise FiscalAgentError(
            f"Sólo se reintenta un trabajo fallido o cancelado; éste está '{trabajo.estado}'.",
            status_code=409,
        )
    if trabajo.clave_unica:
        otro = _vivo_con_clave(db, trabajo.clave_unica)
        if otro is not None and otro.id != trabajo.id:
            raise FiscalAgentError(
                "Ya hay otro trabajo igual en la cola; no se duplica.", status_code=409
            )
    trabajo.estado = "pendiente"
    trabajo.intentos = 0
    trabajo.ejecutar_en = ahora or _ahora()
    trabajo.iniciado_en = None
    trabajo.terminado_en = None
    db.flush()
    return trabajo


def cancelar(db: Session, trabajo: Trabajo, *, ahora: datetime | None = None) -> Trabajo:
    """
    Cancela un trabajo `pendiente`.

    Uno `corriendo` no se cancela: el manejador ya está escribiendo y cortarlo a media
    transacción no es algo que esta cola pueda garantizar.
    """
    # Condicional, como `_tomar`: si un worker lo reclamó entre la lectura y este UPDATE,
    # toca cero renglones y se responde 409 en vez de pisar un `corriendo`.
    cambio = db.execute(
        update(Trabajo)
        .where(Trabajo.id == trabajo.id, Trabajo.estado == "pendiente")
        .values(estado="cancelado", terminado_en=ahora or _ahora())
    )
    db.refresh(trabajo)
    if cambio.rowcount != 1:
        raise FiscalAgentError(
            f"Sólo se cancela un trabajo pendiente; éste está '{trabajo.estado}'.",
            status_code=409,
        )
    return trabajo
