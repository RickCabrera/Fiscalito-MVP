"""
IMSS del patrón (P4-09, P4-10): historial de SBC, movimientos afiliatorios, lotes de archivos
para IDSE/SUA y cédulas EMA/EBA importadas.

POR QUÉ UNA TABLA DE HISTORIAL Y NO UN CAMPO EN LA FICHA
--------------------------------------------------------
La ficha del empleado (`empleados.datos`) guarda el SBC VIGENTE. Las cuotas de un bimestre
pasado se calculan con el SBC que estuvo vigente cada día de ese bimestre (Art. 30 LSS), y
la conciliación contra la EMA/EBA necesita exactamente eso. Sin historial, cambiar el SBC hoy
reescribe en silencio las cuotas de hace tres meses.

`empleado_no` (y no un FK a `empleados.id`) es la llave: el empleado puede borrarse de la
cartera y su historial ante el IMSS tiene que sobrevivir (la baja ya se presentó con ese NSS).
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, Date, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, ConMarcasDeTiempo
from app.db.tipos import FechaUTC

DINERO = Numeric(18, 2)

# Tipo de salario del layout del IMSS (posición 117): 0 fijo, 1 variable, 2 mixto.
TIPOS_SALARIO = {"0": "fijo", "1": "variable", "2": "mixto"}
TIPOS_MOVIMIENTO = {"08": "alta o reingreso", "07": "modificación de salario", "02": "baja"}
ESTADOS_MOVIMIENTO = ("pendiente", "generado", "enviado", "acuse", "cancelado")


class HistorialSBC(ConMarcasDeTiempo, Base):
    """Un SBC con su fecha de efecto. El vigente en un día es el último con fecha <= día."""

    __tablename__ = "imss_historial_sbc"
    __table_args__ = (
        Index("ix_hsbc_cliente_empleado_fecha", "cliente_id", "empleado_no", "fecha"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id", ondelete="CASCADE"))
    empleado_no: Mapped[str] = mapped_column(String(60))
    fecha: Mapped[date] = mapped_column(Date)
    sbc: Mapped[Decimal] = mapped_column(DINERO)
    salario_diario: Mapped[Decimal | None] = mapped_column(DINERO, nullable=True)
    tipo_salario: Mapped[str] = mapped_column(String(1), default="0")
    # alta | reingreso | aumento | prestaciones | bimestre_variable | edicion_ficha | correccion
    motivo: Mapped[str] = mapped_column(String(40), default="")
    nota: Mapped[str] = mapped_column(String(500), default="")
    creado_por: Mapped[str] = mapped_column(String(128), default="")


class MovimientoImss(ConMarcasDeTiempo, Base):
    """Un aviso afiliatorio (08 alta/reingreso, 07 modificación, 02 baja) y su estado."""

    __tablename__ = "imss_movimientos"
    __table_args__ = (Index("ix_movimientos_cliente_estado", "cliente_id", "estado", "tipo"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id", ondelete="CASCADE"))
    empleado_no: Mapped[str] = mapped_column(String(60))
    tipo: Mapped[str] = mapped_column(String(2))
    fecha: Mapped[date] = mapped_column(Date)
    sbc: Mapped[Decimal | None] = mapped_column(DINERO, nullable=True)
    tipo_salario: Mapped[str] = mapped_column(String(1), default="0")
    causa_baja: Mapped[str] = mapped_column(String(1), default="")
    estado: Mapped[str] = mapped_column(String(12), default="pendiente")
    lote_id: Mapped[int | None] = mapped_column(
        ForeignKey("imss_lotes.id", ondelete="SET NULL"), nullable=True
    )
    acuse: Mapped[str] = mapped_column(String(120), default="")
    enviado_en: Mapped[datetime | None] = mapped_column(FechaUTC(), nullable=True)
    origen: Mapped[str] = mapped_column(String(40), default="")
    creado_por: Mapped[str] = mapped_column(String(128), default="")


class LoteImss(ConMarcasDeTiempo, Base):
    """Un archivo generado (IDSE por tipo de movimiento, o SUA) con su contenido ASCII."""

    __tablename__ = "imss_lotes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cliente_id: Mapped[int] = mapped_column(
        ForeignKey("clientes.id", ondelete="CASCADE"), index=True
    )
    # idse_08 | idse_07 | idse_02 | sua_trabajadores | sua_movimientos
    tipo: Mapped[str] = mapped_column(String(24))
    nombre_archivo: Mapped[str] = mapped_column(String(200))
    registros: Mapped[int] = mapped_column(Integer, default=0)
    contenido: Mapped[str] = mapped_column(Text, default="")
    sha256: Mapped[str] = mapped_column(String(64), default="")
    creado_por: Mapped[str] = mapped_column(String(128), default="")


class CedulaImss(ConMarcasDeTiempo, Base):
    """Una cédula EMA (mensual) o EBA (bimestral) importada y su conciliación."""

    __tablename__ = "imss_cedulas"
    __table_args__ = (Index("ix_cedulas_cliente_periodo", "cliente_id", "ejercicio", "periodo"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id", ondelete="CASCADE"))
    tipo: Mapped[str] = mapped_column(String(3))  # EMA | EBA
    ejercicio: Mapped[int] = mapped_column(Integer)
    # Mes (1-12) para la EMA; bimestre (1-6) para la EBA.
    periodo: Mapped[int] = mapped_column(Integer)
    nombre_archivo: Mapped[str] = mapped_column(String(200), default="")
    configuracion: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    filas: Mapped[list[Any]] = mapped_column(JSON, default=list)
    conciliacion: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    diferencias: Mapped[int] = mapped_column(Integer, default=0)
    creado_por: Mapped[str] = mapped_column(String(128), default="")


class CfdiNomina(ConMarcasDeTiempo, Base):
    """
    El CFDI de un recibo de nómina (P4-11): su estado de timbrado y cancelación.

    Un recibo puede tener más de uno en su vida (timbrado → cancelado → re-timbrado); el
    vigente se copia a `ReciboNomina.uuid_cfdi`.
    """

    __tablename__ = "nomina_cfdi"
    __table_args__ = (Index("ix_nomina_cfdi_periodo", "periodo_id", "estado"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id", ondelete="CASCADE"))
    periodo_id: Mapped[int] = mapped_column(
        ForeignKey("nomina_periodos.id", ondelete="CASCADE")
    )
    recibo_id: Mapped[int] = mapped_column(
        ForeignKey("nomina_recibos.id", ondelete="CASCADE"), index=True
    )
    empleado_no: Mapped[str] = mapped_column(String(60))
    # pendiente | timbrado | error | cancelado | cancelacion_en_proceso
    estado: Mapped[str] = mapped_column(String(24), default="pendiente")
    uuid: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    serie: Mapped[str] = mapped_column(String(25), default="")
    folio: Mapped[str] = mapped_column(String(40), default="")
    intentos: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, default="")
    pac: Mapped[str] = mapped_column(String(20), default="")
    es_prueba: Mapped[bool] = mapped_column(default=False)
    fecha_timbrado: Mapped[datetime | None] = mapped_column(FechaUTC(), nullable=True)
    ruta_xml: Mapped[str] = mapped_column(String(400), default="")
    sha256: Mapped[str] = mapped_column(String(64), default="")
    total: Mapped[Decimal] = mapped_column(DINERO, default=Decimal("0"))
    motivo_cancelacion: Mapped[str] = mapped_column(String(2), default="")
    folio_sustitucion: Mapped[str] = mapped_column(String(36), default="")
    ruta_acuse: Mapped[str] = mapped_column(String(400), default="")
    creado_por: Mapped[str] = mapped_column(String(128), default="")
