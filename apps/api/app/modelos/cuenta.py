"""
Cuenta del despacho (P6-01): el rastro que sobrevive al borrado.

`bajas_despacho` NO tiene llave foránea a `despachos` a propósito: es la lápida que queda
cuando el despacho (y su bitácora, que cuelga de él) ya no existen. Guarda quién pidió el
borrado, cuándo y cuántos renglones se fueron por tabla; ningún dato personal.
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
