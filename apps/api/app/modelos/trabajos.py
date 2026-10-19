"""
Cola de trabajos en segundo plano (P0-04) y bitácora del programador.

LA COLA VIVE EN LA BASE, NO EN REDIS
------------------------------------
Un servicio menos que pagar, respaldar y vigilar. El volumen esperado (descargas del SAT,
recordatorios, recálculos por cliente) son miles de trabajos al día, no millones: Postgres
los despacha sin despeinarse con `FOR UPDATE SKIP LOCKED`, y SQLite en desarrollo con una
actualización condicional. Ver `app/trabajos/cola.py`.

`clave_unica` Y SU ÍNDICE PARCIAL
---------------------------------
Dos trabajos con la misma `clave_unica` no pueden estar vivos (pendiente/corriendo) a la
vez; uno terminado no estorba a uno nuevo. Postgres y SQLite soportan índices parciales,
así que la regla la sostiene la base y no sólo `encolar` (que además la consulta antes,
para devolver el existente sin depender de capturar el error).
"""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, ConMarcasDeTiempo, ahora
from app.db.tipos import FechaUTC

ESTADOS = ("pendiente", "corriendo", "hecho", "fallido", "cancelado")
ESTADOS_VIVOS = ("pendiente", "corriendo")

_SOLO_VIVOS = text("clave_unica IS NOT NULL AND estado IN ('pendiente', 'corriendo')")


class Trabajo(ConMarcasDeTiempo, Base):
    """Una unidad de trabajo que corre fuera del request."""

    __tablename__ = "trabajos"
    __table_args__ = (
        Index("ix_trabajos_estado_ejecutar", "estado", "ejecutar_en"),
        Index("ix_trabajos_despacho_cliente", "despacho_id", "cliente_id"),
        Index(
            "ux_trabajos_clave_viva",
            "clave_unica",
            unique=True,
            postgresql_where=_SOLO_VIVOS,
            sqlite_where=_SOLO_VIVOS,
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # Nulos para trabajos de sistema (mantenimiento, programador): no son de ningún despacho
    # y por eso ninguna ruta del despacho los enseña.
    despacho_id: Mapped[str | None] = mapped_column(
        ForeignKey("despachos.id", ondelete="CASCADE"), nullable=True
    )
    cliente_id: Mapped[int | None] = mapped_column(
        ForeignKey("clientes.id", ondelete="CASCADE"), nullable=True
    )
    tipo: Mapped[str] = mapped_column(String(80))
    carga: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    estado: Mapped[str] = mapped_column(String(20), default="pendiente")
    intentos: Mapped[int] = mapped_column(Integer, default=0)
    max_intentos: Mapped[int] = mapped_column(Integer, default=5)
    ejecutar_en: Mapped[datetime] = mapped_column(FechaUTC(), default=ahora)
    iniciado_en: Mapped[datetime | None] = mapped_column(FechaUTC(), nullable=True)
    terminado_en: Mapped[datetime | None] = mapped_column(
        FechaUTC(), nullable=True
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    resultado: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    clave_unica: Mapped[str | None] = mapped_column(String(200), nullable=True)


class EjecucionProgramada(Base):
    """
    Última vez que el programador encoló cada tarea recurrente.

    Sin esta tabla, reiniciar el worker repetiría la tarea del día (o la saltaría). Con
    ella, cada ranura de tiempo se reclama una sola vez aunque haya dos workers.
    """

    __tablename__ = "ejecuciones_programadas"

    nombre: Mapped[str] = mapped_column(String(120), primary_key=True)
    ultima_ejecucion: Mapped[datetime] = mapped_column(FechaUTC())
