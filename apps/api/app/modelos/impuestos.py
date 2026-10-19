"""
Criterios fiscales del despacho por cliente (P3-02, P3-03, P3-07; DP-3).

Vive en su propia tabla y no en `Cliente.datos`: ese JSON es un `ClienteCarteraSchema`
validado que el front reescribe completo en cada guardado, y pydantic descarta lo que no
declara. Un criterio fiscal guardado ahí se borraría la siguiente vez que alguien edite la
ficha del cliente.

`datos` es un `ConfigImpuestosSchema` (`app/schemas/impuestos.py`) serializado; sin renglón,
rigen los defaults documentados en ese esquema.
"""

from typing import Any

from sqlalchemy import JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, ConMarcasDeTiempo


class ConfigImpuestosCliente(ConMarcasDeTiempo, Base):
    """Criterio del despacho para los cálculos de impuestos de un cliente."""

    __tablename__ = "config_impuestos_cliente"

    cliente_id: Mapped[int] = mapped_column(
        ForeignKey("clientes.id", ondelete="CASCADE"), primary_key=True
    )
    datos: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
