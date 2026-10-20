"""
Envío de recibos de nómina al trabajador (P4-13): plantillas por despacho y estado por recibo.

UN RENGLÓN POR RECIBO Y CANAL
-----------------------------
`envios_recibo` es único por (recibo, canal). Volver a pedir "Enviar recibos" no crea otro
renglón: los ya `enviado` se quedan como están, y el trabajo en segundo plano sólo manda los
`pendiente` (y reintenta los `fallido` con intentos disponibles). Así reintentar no duplica.
Reenviar uno a propósito es explícito: lo regresa a `pendiente`.

ESTADOS
-------
pendiente → enviado | fallido. `rebotado` lo marca el aviso del proveedor (o el operador)
después de un `enviado` que no llegó.
"""

from datetime import datetime

from sqlalchemy import ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, ConMarcasDeTiempo
from app.db.tipos import FechaUTC

CANALES = ("correo", "whatsapp")
ESTADOS_ENVIO = ("pendiente", "enviado", "fallido", "rebotado")


class PlantillaRecibo(ConMarcasDeTiempo, Base):
    """Asunto y cuerpo del envío, por despacho y canal. Variables: {nombre} {periodo} {neto}."""

    __tablename__ = "plantillas_recibo"
    __table_args__ = (UniqueConstraint("despacho_id", "canal", name="uq_plantilla_recibo"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    despacho_id: Mapped[str] = mapped_column(String(128), index=True)
    canal: Mapped[str] = mapped_column(String(10))
    asunto: Mapped[str] = mapped_column(String(200), default="")
    cuerpo: Mapped[str] = mapped_column(Text, default="")
    # WhatsApp: nombre de la plantilla APROBADA por Meta (o Content SID de Twilio) e idioma.
    plantilla_whatsapp: Mapped[str] = mapped_column(String(120), default="")
    idioma: Mapped[str] = mapped_column(String(10), default="es_MX")


class EnvioRecibo(ConMarcasDeTiempo, Base):
    """El envío de un recibo por un canal, con su estado."""

    __tablename__ = "envios_recibo"
    __table_args__ = (
        UniqueConstraint("recibo_id", "canal", name="uq_envio_recibo_canal"),
        Index("ix_envio_periodo_canal", "periodo_id", "canal"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    despacho_id: Mapped[str] = mapped_column(String(128), index=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id", ondelete="CASCADE"))
    periodo_id: Mapped[int] = mapped_column(
        ForeignKey("nomina_periodos.id", ondelete="CASCADE")
    )
    recibo_id: Mapped[int] = mapped_column(ForeignKey("nomina_recibos.id", ondelete="CASCADE"))
    empleado_no: Mapped[str] = mapped_column(String(60))
    canal: Mapped[str] = mapped_column(String(10))
    destino: Mapped[str] = mapped_column(String(320), default="")
    estado: Mapped[str] = mapped_column(String(12), default="pendiente", index=True)
    intentos: Mapped[int] = mapped_column(Integer, default=0)
    id_mensaje: Mapped[str] = mapped_column(String(200), default="", index=True)
    error: Mapped[str] = mapped_column(String(500), default="")
    timbrado: Mapped[bool] = mapped_column(default=False)
    enviado_en: Mapped[datetime | None] = mapped_column(FechaUTC(), nullable=True)
