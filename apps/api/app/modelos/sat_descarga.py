"""
Descarga masiva del SAT por cliente (plan P, P1-01 y P1-02).

- `SolicitudDescargaSat`: una solicitud al web service (un rango, una dirección, CFDI o
  metadata). Su `huella` (los parámetros) es única por cliente: pedir lo mismo dos veces
  devuelve la misma solicitud y NO manda otra al SAT, que además limita a dos las
  solicitudes de por vida con los mismos parámetros (código 5002).
- `MetadataCfdiSat`: un renglón de la metadata del SAT (UUID, emisor, receptor, monto,
  estatus, fecha de cancelación). Sirve para ver cancelados y CFDI que faltan en la bóveda.
- `ConfigDescargaSat`: qué bajar de cada cliente, desde cuándo y a qué hora.
- `AlertaDescargaSat`: avisos consultables (sin e.firma, solicitud atorada, error del SAT).
  Las alertas formales del despacho llegan en P3-09; ésta es la bitácora que leerán.

Las fechas del rango (`fecha_inicial`, `fecha_final`) son HORA LOCAL de la Ciudad de México sin
zona, igual que las manda el SAT y que el atributo `Fecha` del CFDI. Los momentos de proceso
(`proxima_verificacion`, `solicitada_en`…) son `FechaUTC`.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, ConMarcasDeTiempo
from app.db.tipos import FechaUTC

# pendiente → solicitada → en_proceso → (terminada | sin_datos | fallida | dividida)
ESTADOS_SOLICITUD = (
    "pendiente", "solicitada", "en_proceso", "descargando",
    "terminada", "sin_datos", "fallida", "dividida",
)
ESTADOS_VIVOS_SOLICITUD = ("pendiente", "solicitada", "en_proceso", "descargando")


class SolicitudDescargaSat(ConMarcasDeTiempo, Base):
    """Una solicitud de descarga masiva al SAT."""

    __tablename__ = "sat_solicitudes_descarga"
    __table_args__ = (
        UniqueConstraint("cliente_id", "huella", name="uq_sat_solicitud_huella"),
        Index("ix_sat_solicitud_cliente_rango", "cliente_id", "fecha_inicial", "fecha_final"),
        Index("ix_sat_solicitud_estado", "estado", "proxima_verificacion"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id", ondelete="CASCADE"))
    # emitidos | recibidos
    direccion: Mapped[str] = mapped_column(String(10))
    # cfdi | metadata
    tipo: Mapped[str] = mapped_column(String(10))
    # vigentes | cancelados | todos
    estado_comprobante: Mapped[str] = mapped_column(String(10), default="todos")
    fecha_inicial: Mapped[datetime] = mapped_column(DateTime(timezone=False))
    fecha_final: Mapped[datetime] = mapped_column(DateTime(timezone=False))
    rfc_contraparte: Mapped[str] = mapped_column(String(13), default="")
    tipo_comprobante: Mapped[str] = mapped_column(String(1), default="")
    huella: Mapped[str] = mapped_column(String(64))
    # diaria | manual | historica | division
    origen: Mapped[str] = mapped_column(String(12), default="manual")
    padre_id: Mapped[int | None] = mapped_column(
        ForeignKey("sat_solicitudes_descarga.id", ondelete="SET NULL"), nullable=True
    )

    id_solicitud: Mapped[str] = mapped_column(String(80), default="")
    estado: Mapped[str] = mapped_column(String(12), default="pendiente")
    # Último CodEstatus / CodigoEstadoSolicitud del SAT y su mensaje en español.
    codigo: Mapped[str] = mapped_column(String(10), default="")
    mensaje: Mapped[str] = mapped_column(Text, default="")
    estado_sat: Mapped[int] = mapped_column(Integer, default=0)
    numero_cfdis: Mapped[int] = mapped_column(Integer, default=0)
    paquetes: Mapped[list[str]] = mapped_column(JSON, default=list)
    paquetes_procesados: Mapped[list[str]] = mapped_column(JSON, default=list)
    xml_importados: Mapped[int] = mapped_column(Integer, default=0)
    duplicados: Mapped[int] = mapped_column(Integer, default=0)
    rechazados: Mapped[int] = mapped_column(Integer, default=0)
    metadata_registros: Mapped[int] = mapped_column(Integer, default=0)

    # Veces que se mandó al SAT (el SAT permite dos con los mismos parámetros).
    veces_solicitada: Mapped[int] = mapped_column(Integer, default=0)
    verificaciones: Mapped[int] = mapped_column(Integer, default=0)
    intentos: Mapped[int] = mapped_column(Integer, default=0)
    proxima_verificacion: Mapped[datetime | None] = mapped_column(FechaUTC(), nullable=True)
    solicitada_en: Mapped[datetime | None] = mapped_column(FechaUTC(), nullable=True)
    terminada_en: Mapped[datetime | None] = mapped_column(FechaUTC(), nullable=True)
    aviso_atorada: Mapped[bool] = mapped_column(Boolean, default=False)


class MetadataCfdiSat(ConMarcasDeTiempo, Base):
    """Un renglón de la metadata del SAT de un CFDI del cliente."""

    __tablename__ = "sat_metadata_cfdi"
    __table_args__ = (
        UniqueConstraint("cliente_id", "uuid", name="uq_sat_metadata_cliente_uuid"),
        Index("ix_sat_metadata_cliente_fecha", "cliente_id", "fecha_emision"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id", ondelete="CASCADE"))
    uuid: Mapped[str] = mapped_column(String(36))
    rfc_emisor: Mapped[str] = mapped_column(String(13), default="")
    nombre_emisor: Mapped[str] = mapped_column(String(300), default="")
    rfc_receptor: Mapped[str] = mapped_column(String(13), default="")
    nombre_receptor: Mapped[str] = mapped_column(String(300), default="")
    rfc_pac: Mapped[str] = mapped_column(String(13), default="")
    fecha_emision: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    fecha_certificacion: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    monto: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    # I E T N P (EfectoComprobante)
    efecto: Mapped[str] = mapped_column(String(1), default="")
    # vigente | cancelado
    estatus: Mapped[str] = mapped_column(String(12), default="vigente")
    fecha_cancelacion: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    # emitido | recibido
    direccion: Mapped[str] = mapped_column(String(10), default="")
    datos: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class ConfigDescargaSat(ConMarcasDeTiempo, Base):
    """Qué baja la sincronización diaria de un cliente."""

    __tablename__ = "sat_config_descarga"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cliente_id: Mapped[int] = mapped_column(
        ForeignKey("clientes.id", ondelete="CASCADE"), unique=True
    )
    activa: Mapped[bool] = mapped_column(Boolean, default=False)
    emitidos: Mapped[bool] = mapped_column(Boolean, default=True)
    recibidos: Mapped[bool] = mapped_column(Boolean, default=True)
    metadata_: Mapped[bool] = mapped_column("metadata", Boolean, default=True)
    cancelados: Mapped[bool] = mapped_column(Boolean, default=True)
    desde: Mapped[date | None] = mapped_column(Date, nullable=True)
    # HH:MM en America/Mexico_City.
    hora: Mapped[str] = mapped_column(String(5), default="02:00")
    # "" si corre; "efirma" si se pausó por falta de e.firma vigente.
    pausada_por: Mapped[str] = mapped_column(String(20), default="")
    ultimo_dia_encolado: Mapped[date | None] = mapped_column(Date, nullable=True)


class AlertaDescargaSat(ConMarcasDeTiempo, Base):
    """Aviso de la descarga del SAT que el despacho tiene que ver."""

    __tablename__ = "sat_alertas_descarga"
    __table_args__ = (Index("ix_sat_alerta_cliente", "cliente_id", "resuelta"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id", ondelete="CASCADE"))
    # sin_efirma | atorada | error_sat | agotada
    tipo: Mapped[str] = mapped_column(String(20))
    mensaje: Mapped[str] = mapped_column(Text, default="")
    solicitud_id: Mapped[int | None] = mapped_column(
        ForeignKey("sat_solicitudes_descarga.id", ondelete="SET NULL"), nullable=True
    )
    resuelta: Mapped[bool] = mapped_column(Boolean, default=False)
