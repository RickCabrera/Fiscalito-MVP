"""
Facturación CFDI 4.0 emitida desde Fiscalito (P5-04).

- `Factura`: un CFDI de ingreso (I), egreso (E) o pago (P) que EMITE un cliente del despacho
  (`cliente_id` = emisor). Cuando el emisor es el propio despacho (su "cliente propio", ver
  `ConfigFacturacion`) y factura sus honorarios, `cliente_receptor_id` apunta al cliente de la
  cartera que recibe y `cargo_id` al cargo de cuentas por cobrar (P5-03) que ampara.
  El XML timbrado entra a la bóveda del emisor (`comprobantes`, origen `emision`) y, si el
  receptor es otro cliente del despacho, también a la suya como recibido.
- `DocumentoPagoFactura`: cada factura PPD que liquida (en parte) un CFDI de pago. El saldo de
  una PPD se calcula de aquí (pagos NO cancelados), no se guarda.
- `FolioFactura`: consecutivo por emisor y serie (folio interno, único por emisor+serie).
- `ConfigFacturacion`: cuál cliente de la cartera es el propio despacho (su RFC, CSD y CP).
"""

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, ConMarcasDeTiempo
from app.db.tipos import FechaUTC

DINERO = Numeric(18, 2)
ESTADOS_FACTURA = ("timbrado", "cancelacion_en_proceso", "cancelado")


class Factura(ConMarcasDeTiempo, Base):
    """Un CFDI emitido (I/E/P), timbrado por el PAC de `FISCALITO_PAC`."""

    __tablename__ = "facturas"
    __table_args__ = (
        UniqueConstraint("cliente_id", "uuid", name="uq_factura_uuid"),
        UniqueConstraint("cliente_id", "serie", "folio", name="uq_factura_serie_folio"),
        Index("ix_factura_despacho_fecha", "despacho_id", "fecha_emision"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    despacho_id: Mapped[str] = mapped_column(ForeignKey("despachos.id", ondelete="CASCADE"))
    cliente_id: Mapped[int] = mapped_column(
        ForeignKey("clientes.id", ondelete="CASCADE"), index=True)
    cliente_receptor_id: Mapped[int | None] = mapped_column(
        ForeignKey("clientes.id", ondelete="SET NULL"), nullable=True, index=True)
    cargo_id: Mapped[int | None] = mapped_column(
        ForeignKey("cargos_cobranza.id", ondelete="SET NULL"), nullable=True)
    tipo: Mapped[str] = mapped_column(String(1))  # I | E | P
    serie: Mapped[str] = mapped_column(String(25), default="")
    folio: Mapped[str] = mapped_column(String(40))
    uuid: Mapped[str] = mapped_column(String(36))
    rfc_receptor: Mapped[str] = mapped_column(String(13), index=True)
    nombre_receptor: Mapped[str] = mapped_column(String(300), default="")
    metodo_pago: Mapped[str] = mapped_column(String(3), default="")
    forma_pago: Mapped[str] = mapped_column(String(2), default="")
    uso_cfdi: Mapped[str] = mapped_column(String(4), default="")
    subtotal: Mapped[Decimal] = mapped_column(DINERO, default=Decimal("0"))
    descuento: Mapped[Decimal] = mapped_column(DINERO, default=Decimal("0"))
    traslados: Mapped[Decimal] = mapped_column(DINERO, default=Decimal("0"))
    retenciones: Mapped[Decimal] = mapped_column(DINERO, default=Decimal("0"))
    # En un CFDI de pago, el monto pagado (el atributo Total del comprobante es 0).
    total: Mapped[Decimal] = mapped_column(DINERO, default=Decimal("0"))
    # timbrado | cancelacion_en_proceso | cancelado
    estado: Mapped[str] = mapped_column(String(24), default="timbrado", index=True)
    pac: Mapped[str] = mapped_column(String(20), default="")
    es_prueba: Mapped[bool] = mapped_column(default=False)
    fecha_emision: Mapped[datetime] = mapped_column(FechaUTC())
    fecha_timbrado: Mapped[datetime] = mapped_column(FechaUTC())
    ruta_xml: Mapped[str] = mapped_column(String(400))
    sha256: Mapped[str] = mapped_column(String(64))
    motivo_cancelacion: Mapped[str] = mapped_column(String(2), default="")
    folio_sustitucion: Mapped[str] = mapped_column(String(36), default="")
    ruta_acuse: Mapped[str] = mapped_column(String(400), default="")
    creado_por: Mapped[str] = mapped_column(String(128), default="")
    # Impuestos agrupados (para el complemento de pago), relacionados y la captura original.
    datos: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class DocumentoPagoFactura(ConMarcasDeTiempo, Base):
    """Una factura PPD liquidada (en parte) por un CFDI de pago."""

    __tablename__ = "documentos_pago_factura"
    __table_args__ = (
        UniqueConstraint("pago_id", "factura_id", name="uq_doc_pago_factura"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    pago_id: Mapped[int] = mapped_column(ForeignKey("facturas.id", ondelete="CASCADE"),
                                         index=True)
    factura_id: Mapped[int] = mapped_column(ForeignKey("facturas.id", ondelete="CASCADE"),
                                            index=True)
    num_parcialidad: Mapped[int] = mapped_column(Integer)
    saldo_anterior: Mapped[Decimal] = mapped_column(DINERO)
    importe_pagado: Mapped[Decimal] = mapped_column(DINERO)
    saldo_insoluto: Mapped[Decimal] = mapped_column(DINERO)


class FolioFactura(Base):
    """Siguiente folio por emisor y serie."""

    __tablename__ = "folios_factura"

    cliente_id: Mapped[int] = mapped_column(
        ForeignKey("clientes.id", ondelete="CASCADE"), primary_key=True)
    serie: Mapped[str] = mapped_column(String(25), primary_key=True)
    siguiente: Mapped[int] = mapped_column(Integer, default=1)


class ConfigFacturacion(ConMarcasDeTiempo, Base):
    """Configuración de facturación del despacho."""

    __tablename__ = "config_facturacion"

    despacho_id: Mapped[str] = mapped_column(
        ForeignKey("despachos.id", ondelete="CASCADE"), primary_key=True)
    # El cliente de la cartera que ES el despacho (emite sus honorarios con su CSD).
    cliente_propio_id: Mapped[int | None] = mapped_column(
        ForeignKey("clientes.id", ondelete="SET NULL"), nullable=True)
