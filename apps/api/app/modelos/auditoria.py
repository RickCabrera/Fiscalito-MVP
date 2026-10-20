"""
Bitácora de auditoría (P0-07): quién hizo qué, a qué cliente y cuándo.

LA BITÁCORA SOBREVIVE AL CLIENTE
--------------------------------
`cliente_id` se pone en NULL si el cliente se borra (no en cascada) y la clave se copia
aparte en `cliente_clave`: borrar un cliente no puede borrar el rastro de quién lo borró.
Lo que sí cae en cascada es el despacho entero, que es el dueño de la bitácora.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, ahora
from app.db.tipos import FechaUTC


class EventoAuditoria(Base):
    """Un renglón de la bitácora."""

    __tablename__ = "eventos_auditoria"
    __table_args__ = (
        Index("ix_auditoria_despacho_fecha", "despacho_id", "fecha"),
        Index("ix_auditoria_despacho_cliente", "despacho_id", "cliente_clave"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    despacho_id: Mapped[str] = mapped_column(ForeignKey("despachos.id", ondelete="CASCADE"))
    uid: Mapped[str] = mapped_column(String(128))
    cliente_id: Mapped[int | None] = mapped_column(
        ForeignKey("clientes.id", ondelete="SET NULL"), nullable=True
    )
    cliente_clave: Mapped[str | None] = mapped_column(String(120), nullable=True)
    # "trabajo.reintentar", "cliente.alta"… o "http.POST" cuando lo escribe el middleware.
    accion: Mapped[str] = mapped_column(String(80))
    entidad: Mapped[str] = mapped_column(String(80), default="")
    entidad_id: Mapped[str] = mapped_column(String(200), default="")
    detalle: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    ip: Mapped[str] = mapped_column(String(64), default="")
    fecha: Mapped[datetime] = mapped_column(FechaUTC(), default=ahora)
