"""
Bóveda de CFDI (plan P, P0-03): una tabla única de comprobantes por cliente.

UNO POR UUID Y CLIENTE
----------------------
El UUID del timbre identifica al comprobante en todo el SAT, pero el mismo CFDI puede estar
en la bóveda de dos clientes del mismo despacho (uno lo emitió y el otro lo recibió), así que
la unicidad es `(cliente_id, uuid)`. El UUID se guarda en MAYÚSCULAS para que dos copias con
distinta capitalización no cuenten como dos comprobantes.

EL XML ORIGINAL NO VIVE EN LA BASE
----------------------------------
Va al adaptador de almacenamiento (`app/integraciones/almacenamiento.py`) byte por byte, y
aquí sólo queda `ruta_xml` y su `sha256`. Las columnas son lo que se filtra y se suma; lo
demás (conceptos, impuestos por tasa, complemento de pago, nómina) va en `datos` (JSON).
"""

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, ConMarcasDeTiempo

DINERO = Numeric(18, 2)


class Comprobante(ConMarcasDeTiempo, Base):
    """Un CFDI (I, E, P, N, T) en la bóveda de un cliente."""

    __tablename__ = "comprobantes"
    __table_args__ = (
        UniqueConstraint("cliente_id", "uuid", name="uq_comprobante_cliente_uuid"),
        Index("ix_comprobante_cliente_fecha", "cliente_id", "fecha"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cliente_id: Mapped[int] = mapped_column(
        ForeignKey("clientes.id", ondelete="CASCADE"), index=True
    )
    uuid: Mapped[str] = mapped_column(String(36))
    version: Mapped[str] = mapped_column(String(5))
    # I ingreso · E egreso · P pago · N nómina · T traslado
    tipo: Mapped[str] = mapped_column(String(1), index=True)
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=False))
    fecha_timbrado: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    serie: Mapped[str] = mapped_column(String(40), default="")
    folio: Mapped[str] = mapped_column(String(60), default="")

    rfc_emisor: Mapped[str] = mapped_column(String(13), index=True)
    nombre_emisor: Mapped[str] = mapped_column(String(300), default="")
    rfc_receptor: Mapped[str] = mapped_column(String(13), index=True)
    nombre_receptor: Mapped[str] = mapped_column(String(300), default="")
    # emitido | recibido — respecto del RFC del cliente al importar.
    direccion: Mapped[str] = mapped_column(String(10), index=True)

    subtotal: Mapped[Decimal] = mapped_column(DINERO, default=Decimal("0"))
    descuento: Mapped[Decimal] = mapped_column(DINERO, default=Decimal("0"))
    total: Mapped[Decimal] = mapped_column(DINERO, default=Decimal("0"))
    moneda: Mapped[str] = mapped_column(String(5), default="MXN")
    tipo_cambio: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    metodo_pago: Mapped[str] = mapped_column(String(3), default="")
    forma_pago: Mapped[str] = mapped_column(String(3), default="")
    uso_cfdi: Mapped[str] = mapped_column(String(5), default="")

    iva_trasladado: Mapped[Decimal] = mapped_column(DINERO, default=Decimal("0"))
    iva_retenido: Mapped[Decimal] = mapped_column(DINERO, default=Decimal("0"))
    isr_retenido: Mapped[Decimal] = mapped_column(DINERO, default=Decimal("0"))
    ieps: Mapped[Decimal] = mapped_column(DINERO, default=Decimal("0"))

    # vigente | cancelado | desconocido (P1-03 lo llena con el servicio del SAT).
    estatus_sat: Mapped[str] = mapped_column(String(12), default="desconocido", index=True)
    fecha_estatus: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # manual (subido por el despacho) | sat (descarga masiva, P1-01).
    origen: Mapped[str] = mapped_column(String(10), default="manual")

    ruta_xml: Mapped[str] = mapped_column(String(400))
    sha256: Mapped[str] = mapped_column(String(64))
    datos: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
