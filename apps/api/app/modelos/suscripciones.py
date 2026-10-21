"""
Suscripción del despacho, pagos y eventos de webhook (P5-08).

- `Suscripcion`: una por despacho (PK = `despacho_id`). El PLAN vigente NO vive aquí sino en
  `despachos.plan` (lo que leen todos los límites); aquí vive el estado del cobro y su periodo.
- `PagoSuscripcion`: historial de cobros (pagados y fallidos) que reporta el proveedor.
- `EventoPagoRecibido`: cada evento de webhook ya procesado, único por (proveedor, evento):
  es lo que hace idempotente al webhook (los proveedores reintentan).
"""

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, ConMarcasDeTiempo
from app.db.tipos import FechaUTC

# prueba | activa | morosa | vencida | cancelada. El estado EFECTIVO (que considera la fecha)
# lo calcula `app/suscripciones/vigencia.py`; éste es el último que se guardó.
ESTADOS = ("prueba", "activa", "morosa", "vencida", "cancelada")


class Suscripcion(ConMarcasDeTiempo, Base):
    __tablename__ = "suscripciones"

    despacho_id: Mapped[str] = mapped_column(
        ForeignKey("despachos.id", ondelete="CASCADE"), primary_key=True)
    estado: Mapped[str] = mapped_column(String(20), default="prueba")
    proveedor: Mapped[str] = mapped_column(String(30), default="")
    cliente_externo: Mapped[str] = mapped_column(String(200), default="")
    suscripcion_externa: Mapped[str] = mapped_column(String(200), default="", index=True)
    # Plan pedido cuyo primer pago aún no se confirma (el proveedor devolvió "incomplete").
    plan_pendiente: Mapped[str] = mapped_column(String(40), default="")
    inicio_periodo: Mapped[datetime] = mapped_column(FechaUTC())
    fin_periodo: Mapped[datetime] = mapped_column(FechaUTC())
    cancelada_en: Mapped[datetime | None] = mapped_column(FechaUTC(), nullable=True)


class PagoSuscripcion(ConMarcasDeTiempo, Base):
    __tablename__ = "pagos_suscripcion"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    despacho_id: Mapped[str] = mapped_column(
        ForeignKey("despachos.id", ondelete="CASCADE"), index=True)
    evento_id: Mapped[str] = mapped_column(String(200))
    estado: Mapped[str] = mapped_column(String(20))  # pagado | fallido
    plan: Mapped[str] = mapped_column(String(40), default="")
    monto: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    moneda: Mapped[str] = mapped_column(String(3), default="")
    fin_periodo: Mapped[datetime | None] = mapped_column(FechaUTC(), nullable=True)


class EventoPagoRecibido(ConMarcasDeTiempo, Base):
    __tablename__ = "eventos_pago"
    __table_args__ = (UniqueConstraint("proveedor", "evento_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    proveedor: Mapped[str] = mapped_column(String(30))
    evento_id: Mapped[str] = mapped_column(String(200))
    tipo: Mapped[str] = mapped_column(String(100), default="")
    despacho_id: Mapped[str | None] = mapped_column(
        ForeignKey("despachos.id", ondelete="SET NULL"), nullable=True, index=True)
    resultado: Mapped[str] = mapped_column(String(40), default="")
    datos: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
