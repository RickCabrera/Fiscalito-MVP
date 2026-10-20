"""
Envío de documentos al cliente del despacho por correo y WhatsApp (P5-05).

- `ContactoCliente`: personas del cliente a las que se les mandan documentos, con su
  consentimiento EXPRESO para WhatsApp (fecha y usuario que lo registró). Sin consentimiento no
  sale nada por WhatsApp.
- `DocumentoCliente`: declaraciones, acuses y otros PDF/XML que el despacho sube al expediente
  del cliente para poder mandarlos (los demás documentos —CFDI, constancias de retención,
  opinión de cumplimiento, recibos de nómina— ya viven en sus módulos).
- `EnvioDocumento`: un documento a un destino por un canal, con estado y reintentos.
  pendiente → enviado | fallido (se reintenta hasta 3 veces) ; rebotado lo marca el aviso del
  proveedor. Mismo ciclo que `envios_recibo` (P4-13).
"""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, ConMarcasDeTiempo
from app.db.tipos import FechaUTC

TIPOS_SUBIDOS = ("declaracion", "acuse", "otro")


class ContactoCliente(ConMarcasDeTiempo, Base):
    """Contacto del cliente (correo, celular y consentimiento de WhatsApp)."""

    __tablename__ = "contactos_cliente"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    despacho_id: Mapped[str] = mapped_column(ForeignKey("despachos.id", ondelete="CASCADE"))
    cliente_id: Mapped[int] = mapped_column(
        ForeignKey("clientes.id", ondelete="CASCADE"), index=True)
    nombre: Mapped[str] = mapped_column(String(200))
    puesto: Mapped[str] = mapped_column(String(120), default="")
    correo: Mapped[str] = mapped_column(String(320), default="")
    # Con lada internacional, sólo dígitos (p. ej. 5215512345678).
    telefono: Mapped[str] = mapped_column(String(20), default="")
    consentimiento_whatsapp: Mapped[bool] = mapped_column(default=False)
    consentimiento_en: Mapped[datetime | None] = mapped_column(FechaUTC(), nullable=True)
    consentimiento_por: Mapped[str] = mapped_column(String(128), default="")
    activo: Mapped[bool] = mapped_column(default=True)


class DocumentoCliente(ConMarcasDeTiempo, Base):
    """Archivo subido al expediente del cliente (declaración, acuse u otro)."""

    __tablename__ = "documentos_cliente"
    __table_args__ = (Index("ix_doc_cliente_tipo", "cliente_id", "tipo"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    despacho_id: Mapped[str] = mapped_column(ForeignKey("despachos.id", ondelete="CASCADE"))
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id", ondelete="CASCADE"))
    tipo: Mapped[str] = mapped_column(String(12))  # declaracion | acuse | otro
    descripcion: Mapped[str] = mapped_column(String(300), default="")
    periodo: Mapped[str] = mapped_column(String(7), default="")  # YYYY-MM opcional
    nombre_archivo: Mapped[str] = mapped_column(String(200))
    mime: Mapped[str] = mapped_column(String(60))
    ruta: Mapped[str] = mapped_column(String(400))
    sha256: Mapped[str] = mapped_column(String(64))
    tamano: Mapped[int] = mapped_column(Integer, default=0)
    creado_por: Mapped[str] = mapped_column(String(128), default="")


class EnvioDocumento(ConMarcasDeTiempo, Base):
    """Un documento enviado (o por enviar) a un contacto del cliente por un canal."""

    __tablename__ = "envios_documento"
    __table_args__ = (Index("ix_envio_doc_cliente", "cliente_id", "estado"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    despacho_id: Mapped[str] = mapped_column(String(128), index=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id", ondelete="CASCADE"))
    contacto_id: Mapped[int | None] = mapped_column(
        ForeignKey("contactos_cliente.id", ondelete="SET NULL"), nullable=True)
    canal: Mapped[str] = mapped_column(String(10))  # correo | whatsapp
    destino: Mapped[str] = mapped_column(String(320))
    # factura | cfdi | retencion | opinion | constancia | declaracion | acuse | otro |
    # recibo_nomina
    tipo_documento: Mapped[str] = mapped_column(String(20))
    ref: Mapped[str] = mapped_column(String(40))
    descripcion: Mapped[str] = mapped_column(String(300), default="")
    mensaje: Mapped[str] = mapped_column(Text, default="")
    estado: Mapped[str] = mapped_column(String(12), default="pendiente", index=True)
    intentos: Mapped[int] = mapped_column(Integer, default=0)
    id_mensaje: Mapped[str] = mapped_column(String(200), default="", index=True)
    error: Mapped[str] = mapped_column(String(500), default="")
    enviado_en: Mapped[datetime | None] = mapped_column(FechaUTC(), nullable=True)
    creado_por: Mapped[str] = mapped_column(String(128), default="")
    datos: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
