"""
CFDI de Retenciones e información de pagos emitidos por un cliente a sus terceros (P3-04).

No va en `comprobantes` (la bóveda de CFDI 3.3/4.0): el CFDI de retenciones es otro estándar
(`retenciones:Retenciones`), sin conceptos ni `TipoDeComprobante`, y la bóveda lo rechazaría al
parsearlo. El XML timbrado sí vive en el mismo almacenamiento que la bóveda (`ruta_xml`), con
su `sha256`, igual que un CFDI.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, ConMarcasDeTiempo
from app.db.tipos import FechaUTC

DINERO = Numeric(18, 2)


class CfdiRetencion(ConMarcasDeTiempo, Base):
    """Un CFDI de retenciones timbrado (o cancelado) de un cliente a un tercero."""

    __tablename__ = "cfdi_retenciones"
    __table_args__ = (
        UniqueConstraint("cliente_id", "uuid", name="uq_cfdi_retencion_uuid"),
        Index("ix_cfdi_retencion_periodo", "cliente_id", "ejercicio", "mes_ini"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cliente_id: Mapped[int] = mapped_column(
        ForeignKey("clientes.id", ondelete="CASCADE"), index=True
    )
    uuid: Mapped[str] = mapped_column(String(36))
    rfc_tercero: Mapped[str] = mapped_column(String(13), index=True)
    nombre_tercero: Mapped[str] = mapped_column(String(300), default="")
    ejercicio: Mapped[int] = mapped_column(Integer)
    mes_ini: Mapped[int] = mapped_column(Integer)
    mes_fin: Mapped[int] = mapped_column(Integer)
    cve_retenc: Mapped[str] = mapped_column(String(2))
    monto_operacion: Mapped[Decimal] = mapped_column(DINERO, default=Decimal("0"))
    isr_retenido: Mapped[Decimal] = mapped_column(DINERO, default=Decimal("0"))
    iva_retenido: Mapped[Decimal] = mapped_column(DINERO, default=Decimal("0"))
    # timbrado | cancelacion_en_proceso | cancelado
    estado: Mapped[str] = mapped_column(String(24), default="timbrado")
    pac: Mapped[str] = mapped_column(String(20))
    # El falso del PAC: el comprobante NO tiene validez fiscal.
    es_prueba: Mapped[bool] = mapped_column(default=False)
    fecha_timbrado: Mapped[datetime] = mapped_column(FechaUTC())
    ruta_xml: Mapped[str] = mapped_column(String(400))
    sha256: Mapped[str] = mapped_column(String(64))
    motivo_cancelacion: Mapped[str] = mapped_column(String(2), default="")
    ruta_acuse: Mapped[str] = mapped_column(String(400), default="")
    creado_por: Mapped[str] = mapped_column(String(128), default="")
    datos: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
