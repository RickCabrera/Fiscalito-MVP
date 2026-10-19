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

from sqlalchemy import JSON, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, ConMarcasDeTiempo


class ConfigImpuestosCliente(ConMarcasDeTiempo, Base):
    """Criterio del despacho para los cálculos de impuestos de un cliente."""

    __tablename__ = "config_impuestos_cliente"

    cliente_id: Mapped[int] = mapped_column(
        ForeignKey("clientes.id", ondelete="CASCADE"), primary_key=True
    )
    datos: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class DatosAnualesPM(ConMarcasDeTiempo, Base):
    """
    Datos de una persona moral por ejercicio que no salen de la bóveda ni de la contabilidad
    (P3-01): coeficiente de utilidad, PTU pagada, pérdidas, retenciones del sistema financiero,
    pagos efectuados, saldos para el ajuste anual por inflación. `datos` es un
    `DatosAnualesPMSchema` (`app/schemas/personas_morales.py`) serializado.
    """

    __tablename__ = "datos_anuales_pm"

    cliente_id: Mapped[int] = mapped_column(
        ForeignKey("clientes.id", ondelete="CASCADE"), primary_key=True
    )
    anio: Mapped[int] = mapped_column(Integer, primary_key=True)
    datos: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
