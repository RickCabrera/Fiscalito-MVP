"""Base declarativa común de todos los modelos."""

from datetime import UTC, datetime

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def ahora() -> datetime:
    """Momento actual en UTC (todas las fechas de auditoría se guardan en UTC)."""
    return datetime.now(UTC)


class Base(DeclarativeBase):
    """Base de los modelos ORM."""


class ConMarcasDeTiempo:
    """Mixin: `creado_en` y `actualizado_en` automáticos."""

    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=ahora, onupdate=ahora
    )
