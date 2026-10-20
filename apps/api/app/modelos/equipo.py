"""
Invitaciones al equipo del despacho (P5-01).

El token de la invitación viaja SÓLO en el correo: aquí se guarda su SHA-256, así una copia
de la base no sirve para unirse a ningún despacho. Es de un solo uso (`aceptada_en`), vence a
los `DIAS_VIGENCIA_INVITACION` días y el dueño la puede revocar.
"""

from datetime import datetime

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, ConMarcasDeTiempo
from app.db.tipos import FechaUTC

ROLES = ("dueno", "contador", "auxiliar")
DIAS_VIGENCIA_INVITACION = 7


class Invitacion(ConMarcasDeTiempo, Base):
    """Invitación a un correo para unirse a un despacho con un rol."""

    __tablename__ = "invitaciones"
    __table_args__ = (Index("ix_invitacion_despacho", "despacho_id", "aceptada_en"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    despacho_id: Mapped[str] = mapped_column(ForeignKey("despachos.id", ondelete="CASCADE"))
    correo: Mapped[str] = mapped_column(String(320))
    rol: Mapped[str] = mapped_column(String(20))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expira_en: Mapped[datetime] = mapped_column(FechaUTC())
    creado_por: Mapped[str] = mapped_column(String(128))
    aceptada_en: Mapped[datetime | None] = mapped_column(FechaUTC(), nullable=True)
    aceptada_por: Mapped[str | None] = mapped_column(String(128), nullable=True)
    revocada: Mapped[bool] = mapped_column(default=False)
