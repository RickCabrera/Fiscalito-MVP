"""
Alertas fiscales del despacho por cliente (P3-09).

Las genera el motor de reglas (`app/alertas/reglas.py`) en un trabajo diario. `clave` hace
idempotente cada regla: la misma situación (p. ej. "la e.firma 12 vence en 7 días") produce
UNA alerta por cliente aunque el trabajo corra todos los días. Si la situación desaparece, el
motor la marca resuelta (`resuelta_por = "sistema"`); si el despacho la resolvió a mano, no se
reabre mientras la clave no cambie.

Las bitácoras de origen (alertas de descarga SAT de P1-02, cruces 69-B de P1-04) se quedan
donde están: aquí se INTEGRAN, con la clave del renglón de origen.
"""

from datetime import date, datetime
from typing import Any

from sqlalchemy import JSON, Date, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, ConMarcasDeTiempo
from app.db.tipos import FechaUTC

SEVERIDADES = ("alta", "media", "baja")


class AlertaFiscal(ConMarcasDeTiempo, Base):
    """Un aviso que el despacho tiene que atender sobre un cliente."""

    __tablename__ = "alertas_fiscales"
    __table_args__ = (
        UniqueConstraint("cliente_id", "clave", name="uq_alerta_fiscal_clave"),
        Index("ix_alerta_fiscal_despacho", "despacho_id", "resuelta", "severidad"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    despacho_id: Mapped[str] = mapped_column(ForeignKey("despachos.id", ondelete="CASCADE"))
    cliente_id: Mapped[int] = mapped_column(
        ForeignKey("clientes.id", ondelete="CASCADE"), index=True
    )
    # tope_resico | efos | cfdi_cancelado | credencial | opinion | descarga_sat |
    # vencimiento | diferencia_declarado | sin_polizas
    tipo: Mapped[str] = mapped_column(String(30), index=True)
    severidad: Mapped[str] = mapped_column(String(8))
    titulo: Mapped[str] = mapped_column(String(300))
    detalle: Mapped[str] = mapped_column(Text, default="")
    # Fecha del hecho (vencimiento, cancelación...), no de la alerta.
    fecha: Mapped[date] = mapped_column(Date)
    enlace: Mapped[str] = mapped_column(String(300), default="")
    clave: Mapped[str] = mapped_column(String(160))
    resuelta: Mapped[bool] = mapped_column(default=False)
    resuelta_por: Mapped[str] = mapped_column(String(128), default="")
    resuelta_en: Mapped[datetime | None] = mapped_column(FechaUTC(), nullable=True)
    datos: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
