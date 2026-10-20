"""
Bot de WhatsApp del despacho (P5-06): contactos por cliente y bitácora de conversación.

CONTACTO = NÚMERO + CLIENTE + CONSENTIMIENTO
--------------------------------------------
El bot sólo atiende números que el despacho registró como contacto de UN cliente suyo y con
consentimiento expreso (LFPDPPP: el titular aceptó recibir por WhatsApp sus documentos
fiscales). Un mismo número puede ser contacto de varias empresas —el dueño de dos negocios, o
el mismo cliente atendido por dos despachos—; en ese caso el bot pide el RFC antes de entregar
nada. Desactivar un contacto no lo borra: la bitácora sigue apuntando a él.

Es lo MÍNIMO de contactos que necesita el bot (P5-05 no existe aún en esta base): cuando
P5-05 traiga su libreta de contactos del cliente, ésta se le une o se migra.

BITÁCORA
--------
Un renglón por mensaje, entrante o saliente. El entrante es idempotente por el id del
proveedor (`direccion` + `id_externo` únicos): Meta reintenta el webhook y un reintento no
debe contestar dos veces. De un número NO registrado sólo se queda el número y el estado: su
texto espera en `detalle.texto_pendiente` hasta que el trabajo lo identifica y, al rechazarlo,
se borra (no hay consentimiento para guardarlo).
"""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, ConMarcasDeTiempo
from app.db.tipos import FechaUTC

ESTADOS_ENTRANTE = ("recibido", "respondido", "rechazado", "limitado", "error")


class ContactoWhatsApp(ConMarcasDeTiempo, Base):
    """Número de WhatsApp autorizado a pedir documentos de un cliente."""

    __tablename__ = "contactos_whatsapp"
    __table_args__ = (UniqueConstraint("cliente_id", "telefono", name="uq_contacto_wa"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    despacho_id: Mapped[str] = mapped_column(
        ForeignKey("despachos.id", ondelete="CASCADE"), index=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id", ondelete="CASCADE"))
    # E.164 mexicano (`+52` y 10 dígitos), normalizado al guardar.
    telefono: Mapped[str] = mapped_column(String(16), index=True)
    nombre: Mapped[str] = mapped_column(String(200), default="")
    consentimiento: Mapped[bool] = mapped_column(default=False)
    consentimiento_en: Mapped[datetime | None] = mapped_column(FechaUTC(), nullable=True)
    registrado_por: Mapped[str] = mapped_column(String(128), default="")
    activo: Mapped[bool] = mapped_column(default=True)


class MensajeWhatsApp(ConMarcasDeTiempo, Base):
    """Un mensaje de la conversación del bot (entrante o saliente)."""

    __tablename__ = "mensajes_whatsapp"
    __table_args__ = (
        UniqueConstraint("direccion", "id_externo", name="uq_mensaje_wa_externo"),
        Index("ix_mensaje_wa_cliente", "cliente_id", "id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # NULL mientras no se identifica (o si el número no está registrado).
    despacho_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    cliente_id: Mapped[int | None] = mapped_column(
        ForeignKey("clientes.id", ondelete="CASCADE"), nullable=True)
    contacto_id: Mapped[int | None] = mapped_column(
        ForeignKey("contactos_whatsapp.id", ondelete="SET NULL"), nullable=True)
    telefono: Mapped[str] = mapped_column(String(20), index=True)
    direccion: Mapped[str] = mapped_column(String(10))  # entrante | saliente
    id_externo: Mapped[str | None] = mapped_column(String(200), nullable=True)
    texto: Mapped[str] = mapped_column(Text, default="")
    intencion: Mapped[str] = mapped_column(String(40), default="")
    estado: Mapped[str] = mapped_column(String(12), default="recibido")
    detalle: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
