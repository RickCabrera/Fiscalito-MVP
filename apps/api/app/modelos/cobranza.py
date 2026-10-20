"""
Cuentas por cobrar del despacho a sus clientes (P5-03).

- `HonorarioCliente`: la iguala mensual de un cliente y cómo se le cobra (día del cargo, días de
  crédito, contacto y recordatorios automáticos). Sin renglón = el cliente no tiene iguala.
- `CargoCobranza`: lo que el cliente debe — la iguala de un mes (generada sola) o un servicio
  extra (manual). `clave` hace idempotente la iguala: `iguala:YYYY-MM` una vez por cliente.
  `facturar` y `uuid_cfdi` son el gancho para P5-04 (facturación CFDI de los honorarios).
- `PagoCobranza`: lo que el cliente pagó (registro manual), opcionalmente ligado al CFDI que
  el despacho emitió y está en la bóveda (`cfdi_uuid`).
- `RecordatorioCobro`: bitácora de recordatorios por correo o WhatsApp, enviados o programados.

Los pagos NO se aplican a un cargo en particular: el saldo se reparte del cargo más viejo al
más nuevo (FIFO) al calcular la antigüedad (`app/cobranza/servicio.py`).
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, ConMarcasDeTiempo
from app.db.tipos import FechaUTC

DINERO = Numeric(18, 2)
TIPOS_CARGO = ("iguala", "servicio")
CANALES = ("correo", "whatsapp")


class HonorarioCliente(ConMarcasDeTiempo, Base):
    """Iguala y condiciones de cobro de un cliente."""

    __tablename__ = "honorarios_cliente"

    cliente_id: Mapped[int] = mapped_column(
        ForeignKey("clientes.id", ondelete="CASCADE"), primary_key=True
    )
    despacho_id: Mapped[str] = mapped_column(
        ForeignKey("despachos.id", ondelete="CASCADE"), index=True
    )
    iguala_mensual: Mapped[Decimal] = mapped_column(DINERO, default=Decimal("0"))
    concepto: Mapped[str] = mapped_column(String(300), default="Honorarios contables")
    # Día del mes en que se genera el cargo (1-28, para que exista en todos los meses).
    dia_cargo: Mapped[int] = mapped_column(default=1)
    # Vencimiento = fecha del cargo + días de crédito.
    dias_credito: Mapped[int] = mapped_column(default=10)
    activo: Mapped[bool] = mapped_column(default=True)
    # P5-04: los cargos de iguala nacen marcados para facturar.
    facturar: Mapped[bool] = mapped_column(default=False)
    correo: Mapped[str] = mapped_column(String(320), default="")
    telefono: Mapped[str] = mapped_column(String(20), default="")
    # Recordatorio automático cuando hay saldo vencido, cada `dias_entre_recordatorios`.
    recordatorio_automatico: Mapped[bool] = mapped_column(default=False)
    canal_recordatorio: Mapped[str] = mapped_column(String(10), default="correo")
    dias_entre_recordatorios: Mapped[int] = mapped_column(default=7)


class CargoCobranza(ConMarcasDeTiempo, Base):
    """Un cargo al cliente: iguala mensual o servicio extra."""

    __tablename__ = "cargos_cobranza"
    __table_args__ = (
        UniqueConstraint("cliente_id", "clave", name="uq_cargo_cobranza_clave"),
        Index("ix_cargo_cobranza_despacho", "despacho_id", "cliente_id", "fecha"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    despacho_id: Mapped[str] = mapped_column(ForeignKey("despachos.id", ondelete="CASCADE"))
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id", ondelete="CASCADE"))
    tipo: Mapped[str] = mapped_column(String(10))
    concepto: Mapped[str] = mapped_column(String(300))
    # YYYY-MM de la iguala; "" en un servicio.
    periodo: Mapped[str] = mapped_column(String(7), default="")
    # `iguala:YYYY-MM` (único por cliente); NULL en un servicio.
    clave: Mapped[str | None] = mapped_column(String(40), nullable=True)
    fecha: Mapped[date] = mapped_column(Date)
    vencimiento: Mapped[date] = mapped_column(Date)
    importe: Mapped[Decimal] = mapped_column(DINERO)
    cancelado: Mapped[bool] = mapped_column(default=False)
    facturar: Mapped[bool] = mapped_column(default=False)
    uuid_cfdi: Mapped[str | None] = mapped_column(String(36), nullable=True)
    creado_por: Mapped[str] = mapped_column(String(128), default="")


class PagoCobranza(ConMarcasDeTiempo, Base):
    """Un pago recibido de un cliente."""

    __tablename__ = "pagos_cobranza"
    __table_args__ = (Index("ix_pago_cobranza_despacho", "despacho_id", "cliente_id", "fecha"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    despacho_id: Mapped[str] = mapped_column(ForeignKey("despachos.id", ondelete="CASCADE"))
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id", ondelete="CASCADE"))
    fecha: Mapped[date] = mapped_column(Date)
    importe: Mapped[Decimal] = mapped_column(DINERO)
    forma_pago: Mapped[str] = mapped_column(String(40), default="")
    referencia: Mapped[str] = mapped_column(String(120), default="")
    cfdi_uuid: Mapped[str | None] = mapped_column(String(36), nullable=True)
    nota: Mapped[str] = mapped_column(Text, default="")
    creado_por: Mapped[str] = mapped_column(String(128), default="")


class RecordatorioCobro(ConMarcasDeTiempo, Base):
    """Recordatorio de cobro enviado o programado."""

    __tablename__ = "recordatorios_cobro"
    __table_args__ = (Index("ix_recordatorio_cliente", "cliente_id", "estado"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    despacho_id: Mapped[str] = mapped_column(ForeignKey("despachos.id", ondelete="CASCADE"))
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id", ondelete="CASCADE"))
    canal: Mapped[str] = mapped_column(String(10))
    destino: Mapped[str] = mapped_column(String(320), default="")
    # programado | enviado | fallido | omitido | cancelado
    estado: Mapped[str] = mapped_column(String(12), default="programado")
    # manual | automatico
    origen: Mapped[str] = mapped_column(String(12), default="manual")
    programado_para: Mapped[datetime] = mapped_column(FechaUTC())
    enviado_en: Mapped[datetime | None] = mapped_column(FechaUTC(), nullable=True)
    saldo: Mapped[Decimal] = mapped_column(DINERO, default=Decimal("0"))
    mensaje_id: Mapped[str] = mapped_column(String(200), default="")
    error: Mapped[str] = mapped_column(Text, default="")
    creado_por: Mapped[str] = mapped_column(String(128), default="")
