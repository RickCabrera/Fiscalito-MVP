"""
Calendario de vencimientos de la cartera y agenda semanal del despacho (P3-10).

- `EstadoObligacion`: lo que el despacho sabe de una obligación de un cliente (presentada,
  cuándo, por quién, cuánto declaró). Las obligaciones en sí NO se guardan: se generan del
  régimen y el RFC (`fiscal_engine/vencimientos.py`) y del calendario patronal; aquí sólo vive
  su estado, por `clave` (p. ej. `mensual:2026-03`, `patronal:cuotas_imss:marzo 2026`).
  Sin renglón = pendiente (o vencida si ya pasó la fecha).
- `TareaAgenda`: tarea del despacho (manual o generada desde una obligación), con responsable.
"""

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, Date, ForeignKey, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, ConMarcasDeTiempo

DINERO = Numeric(18, 2)


class EstadoObligacion(ConMarcasDeTiempo, Base):
    """Estado marcado (a mano o por una declaración registrada) de una obligación."""

    __tablename__ = "estados_obligacion"
    __table_args__ = (UniqueConstraint("cliente_id", "clave", name="uq_estado_obligacion"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cliente_id: Mapped[int] = mapped_column(
        ForeignKey("clientes.id", ondelete="CASCADE"), index=True
    )
    clave: Mapped[str] = mapped_column(String(120))
    # presentada | pendiente (pendiente explícito = se desmarcó una presentada)
    estado: Mapped[str] = mapped_column(String(12), default="presentada")
    # manual | declaracion
    origen: Mapped[str] = mapped_column(String(12), default="manual")
    fecha_presentacion: Mapped[date | None] = mapped_column(Date, nullable=True)
    ingresos_declarados: Mapped[Decimal | None] = mapped_column(DINERO, nullable=True)
    importe_pagado: Mapped[Decimal | None] = mapped_column(DINERO, nullable=True)
    numero_operacion: Mapped[str] = mapped_column(String(60), default="")
    responsable_uid: Mapped[str] = mapped_column(String(128), default="")
    nota: Mapped[str] = mapped_column(Text, default="")
    actualizado_por: Mapped[str] = mapped_column(String(128), default="")


class TareaAgenda(ConMarcasDeTiempo, Base):
    """Una tarea de la agenda del despacho."""

    __tablename__ = "tareas_agenda"
    __table_args__ = (
        UniqueConstraint("despacho_id", "cliente_id", "obligacion_clave",
                         name="uq_tarea_obligacion"),
        Index("ix_tarea_despacho_fecha", "despacho_id", "fecha"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    despacho_id: Mapped[str] = mapped_column(ForeignKey("despachos.id", ondelete="CASCADE"))
    cliente_id: Mapped[int | None] = mapped_column(
        ForeignKey("clientes.id", ondelete="CASCADE"), nullable=True
    )
    titulo: Mapped[str] = mapped_column(String(300))
    descripcion: Mapped[str] = mapped_column(Text, default="")
    responsable_uid: Mapped[str] = mapped_column(String(128), default="")
    fecha: Mapped[date] = mapped_column(Date)
    # pendiente | en_proceso | hecha
    estado: Mapped[str] = mapped_column(String(12), default="pendiente")
    # manual | obligacion
    origen: Mapped[str] = mapped_column(String(12), default="manual")
    obligacion_clave: Mapped[str | None] = mapped_column(String(120), nullable=True)
    creado_por: Mapped[str] = mapped_column(String(128), default="")
    datos: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
