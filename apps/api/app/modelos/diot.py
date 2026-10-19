"""
Clasificación DIOT por proveedor, editable por el despacho (P3-05).

Sin renglón, la DIOT deduce el tipo de tercero y de operación de los datos del CFDI
(`app/diot/servicio.py`). Con renglón, manda lo capturado aquí. `datos` es un
`ConfigProveedorDiotSchema` (`app/schemas/diot_layout.py`) serializado.
"""

from typing import Any

from sqlalchemy import JSON, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, ConMarcasDeTiempo


class ConfigProveedorDiot(ConMarcasDeTiempo, Base):
    """Cómo se declara un proveedor de un cliente en la DIOT."""

    __tablename__ = "config_proveedor_diot"
    __table_args__ = (UniqueConstraint("cliente_id", "rfc", name="uq_config_diot_rfc"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cliente_id: Mapped[int] = mapped_column(
        ForeignKey("clientes.id", ondelete="CASCADE"), index=True
    )
    rfc: Mapped[str] = mapped_column(String(13))
    datos: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
