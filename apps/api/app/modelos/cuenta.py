"""
Cuenta del despacho (P6-01): el rastro que sobrevive al borrado.

`bajas_despacho` NO tiene llave foránea a `despachos` a propósito: es la lápida que queda
cuando el despacho (y su bitácora, que cuelga de él) ya no existen. Guarda quién pidió el
borrado (uid y nombre del despacho, que en una persona física es un dato personal), cuándo y
cuántos renglones se fueron por tabla. Se retiene como evidencia del ejercicio del derecho de
cancelación (LFPDPPP); plazo de retención: decisión pendiente de Ricardo (§P6 en
`docs/decisiones-contables.md`).
"""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, ahora
from app.db.tipos import FechaUTC


class BajaDespacho(Base):
    """Constancia de que un despacho borró su cuenta."""

    __tablename__ = "bajas_despacho"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    despacho_id: Mapped[str] = mapped_column(String(128), index=True)
    nombre: Mapped[str] = mapped_column(String(300), default="")
    uid: Mapped[str] = mapped_column(String(128))
    fecha: Mapped[datetime] = mapped_column(FechaUTC(), default=ahora)
    borrado: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
