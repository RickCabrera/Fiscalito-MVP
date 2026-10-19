"""
Contabilidad por cliente (plan P, P2-01 a P2-04): catálogo, configuración de pólizas
automáticas, pólizas con sus movimientos, saldos iniciales y periodos cerrados.

TODO CUELGA DE `clientes.id`
----------------------------
Ninguna tabla lleva `despacho_id`: se llega a ellas sólo desde un cliente obtenido con
`cliente_o_404`, que ya filtró por despacho. Un id de cuenta o de póliza que llega en la URL
se busca SIEMPRE junto con `cliente_id` (ver `app/contabilidad/*`), así que adivinar ids de
otro despacho da 404.

DINERO
------
`Numeric(18, 2)` y `Decimal`. Un movimiento lleva cargo O abono (el otro en cero); la póliza
cuadra (Σ cargos = Σ abonos) por construcción en el generador y por validación en la captura
manual.
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
    UniqueConstraint,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, ConMarcasDeTiempo

DINERO = Numeric(18, 2)


class CuentaContable(ConMarcasDeTiempo, Base):
    """Una cuenta del catálogo de un cliente, ligada al código agrupador del SAT."""

    __tablename__ = "cuentas_contables"
    __table_args__ = (UniqueConstraint("cliente_id", "numero", name="uq_cuenta_cliente_numero"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cliente_id: Mapped[int] = mapped_column(
        ForeignKey("clientes.id", ondelete="CASCADE"), index=True
    )
    numero: Mapped[str] = mapped_column(String(40))
    nombre: Mapped[str] = mapped_column(String(200))
    # 1 = cuenta de mayor; cada subcuenta es el nivel de su padre + 1.
    nivel: Mapped[int] = mapped_column(Integer)
    # deudora | acreedora
    naturaleza: Mapped[str] = mapped_column(String(9))
    # activo | pasivo | capital | ingreso | costo | gasto | orden
    tipo: Mapped[str] = mapped_column(String(8))
    padre_id: Mapped[int | None] = mapped_column(
        ForeignKey("cuentas_contables.id", ondelete="RESTRICT"), index=True
    )
    codigo_agrupador: Mapped[str] = mapped_column(String(10))
    # Sólo las cuentas afectables reciben movimientos; una cuenta con subcuentas no lo es.
    afectable: Mapped[bool] = mapped_column(Boolean, default=True)


class ConfigContable(ConMarcasDeTiempo, Base):
    """Configuración de pólizas automáticas del cliente (P2-02). Una por cliente."""

    __tablename__ = "config_contable"

    cliente_id: Mapped[int] = mapped_column(
        ForeignKey("clientes.id", ondelete="CASCADE"), primary_key=True
    )
    automatica_ingresos: Mapped[bool] = mapped_column(Boolean, default=True)
    automatica_egresos: Mapped[bool] = mapped_column(Boolean, default=True)
    automatica_pagos: Mapped[bool] = mapped_column(Boolean, default=True)
    automatica_nomina: Mapped[bool] = mapped_column(Boolean, default=True)
    # Una factura PUE con forma de pago que mueve dinero registra el cobro/pago en la misma
    # póliza (cargo a bancos contra clientes, o proveedores contra bancos).
    pue_registra_cobro: Mapped[bool] = mapped_column(Boolean, default=True)
    # rol → número de cuenta (ver `app/contabilidad/config.py`, ROLES).
    cuentas: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    # forma de pago del SAT (c_FormaPago) → número de cuenta de caja/bancos.
    formas_pago: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    # Concepto de egreso con base ≥ tope (y sin regla que lo asigne) va a activo fijo.
    # 0 = desactivado.
    tope_activo: Mapped[Decimal] = mapped_column(DINERO, default=Decimal("0"))
    uso_s01_no_deducible: Mapped[bool] = mapped_column(Boolean, default=True)
    efectivo_no_deducible: Mapped[bool] = mapped_column(Boolean, default=False)
    # Retenciones de facturas PPD en cuentas "pendientes" hasta el pago (la obligación de
    # retener nace con el pago). Default true: es la regla legal (revisión P2).
    retenciones_al_pago: Mapped[bool] = mapped_column(Boolean, default=True,
                                                      server_default=true())
    plantilla_concepto: Mapped[str] = mapped_column(String(200), default="")
    # Día 1 de un mes: los saldos iniciales cuentan para periodos que empiezan ese día o
    # después. None = cuentan siempre.
    fecha_saldos_iniciales: Mapped[date | None] = mapped_column(Date)


class ReglaEgreso(ConMarcasDeTiempo, Base):
    """Regla de asignación de cuenta a los conceptos de egreso, por prioridad (P2-02)."""

    __tablename__ = "reglas_egreso"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cliente_id: Mapped[int] = mapped_column(
        ForeignKey("clientes.id", ondelete="CASCADE"), index=True
    )
    prioridad: Mapped[int] = mapped_column(Integer, default=100)
    # rfc | clave | prefijo | uso | descripcion
    criterio: Mapped[str] = mapped_column(String(12))
    valor: Mapped[str] = mapped_column(String(200))
    cuenta_numero: Mapped[str] = mapped_column(String(40))
    activa: Mapped[bool] = mapped_column(Boolean, default=True)


class Poliza(ConMarcasDeTiempo, Base):
    """Póliza contable (P2-03). Folio consecutivo por cliente, tipo y mes."""

    __tablename__ = "polizas"
    __table_args__ = (
        UniqueConstraint("cliente_id", "tipo", "anio", "mes", "numero", name="uq_poliza_folio"),
        # Idempotencia del generador: una póliza por CFDI (y una reversa por CFDI).
        UniqueConstraint("cliente_id", "clave_origen", name="uq_poliza_origen"),
        Index("ix_poliza_cliente_fecha", "cliente_id", "fecha"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id", ondelete="CASCADE"))
    # ingreso | egreso | diario
    tipo: Mapped[str] = mapped_column(String(8))
    anio: Mapped[int] = mapped_column(Integer)
    mes: Mapped[int] = mapped_column(Integer)
    numero: Mapped[int] = mapped_column(Integer)
    fecha: Mapped[date] = mapped_column(Date)
    concepto: Mapped[str] = mapped_column(String(500), default="")
    # automatica | manual | cierre | apertura (P2-08: cierre anual, ver `cierre.py`)
    origen: Mapped[str] = mapped_column(String(10), default="manual")
    # activa | cancelada
    estado: Mapped[str] = mapped_column(String(10), default="activa", index=True)
    uuid_cfdi: Mapped[str | None] = mapped_column(String(36), index=True)
    tipo_cfdi: Mapped[str] = mapped_column(String(1), default="")
    # "cfdi:<UUID>" (o "cfdi:<UUID>@AAAA-MM-DD": complemento partido por fecha de pago) o
    # "reversa:<…>"; None en pólizas manuales.
    clave_origen: Mapped[str | None] = mapped_column(String(60))
    reversa_de_id: Mapped[int | None] = mapped_column(
        ForeignKey("polizas.id", ondelete="SET NULL")
    )
    # Total del CFDI (en MXN) − lo que la póliza movió contra la contraparte.
    diferencia: Mapped[Decimal] = mapped_column(DINERO, default=Decimal("0"))
    advertencias: Mapped[list[Any]] = mapped_column(JSON, default=list)
    editada: Mapped[bool] = mapped_column(Boolean, default=False)
    cancelada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    motivo_cancelacion: Mapped[str] = mapped_column(String(300), default="")
    creado_por: Mapped[str] = mapped_column(String(128), default="")


class MovimientoPoliza(Base):
    """Un renglón de la póliza: cargo o abono a una cuenta afectable."""

    __tablename__ = "movimientos_poliza"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    poliza_id: Mapped[int] = mapped_column(
        ForeignKey("polizas.id", ondelete="CASCADE"), index=True
    )
    cuenta_id: Mapped[int] = mapped_column(
        ForeignKey("cuentas_contables.id", ondelete="RESTRICT"), index=True
    )
    orden: Mapped[int] = mapped_column(Integer, default=0)
    concepto: Mapped[str] = mapped_column(String(300), default="")
    cargo: Mapped[Decimal] = mapped_column(DINERO, default=Decimal("0"))
    abono: Mapped[Decimal] = mapped_column(DINERO, default=Decimal("0"))
    uuid_cfdi: Mapped[str] = mapped_column(String(36), default="")
    rfc_tercero: Mapped[str] = mapped_column(String(13), default="")


class SaldoInicial(ConMarcasDeTiempo, Base):
    """Saldo con el que arranca una cuenta afectable al empezar a llevar la contabilidad."""

    __tablename__ = "saldos_iniciales"

    cuenta_id: Mapped[int] = mapped_column(
        ForeignKey("cuentas_contables.id", ondelete="CASCADE"), primary_key=True
    )
    cliente_id: Mapped[int] = mapped_column(
        ForeignKey("clientes.id", ondelete="CASCADE"), index=True
    )
    deudor: Mapped[Decimal] = mapped_column(DINERO, default=Decimal("0"))
    acreedor: Mapped[Decimal] = mapped_column(DINERO, default=Decimal("0"))


class PeriodoCerrado(Base):
    """Mes cerrado del cliente: no acepta pólizas nuevas, ediciones ni cancelaciones."""

    __tablename__ = "periodos_cerrados"

    cliente_id: Mapped[int] = mapped_column(
        ForeignKey("clientes.id", ondelete="CASCADE"), primary_key=True
    )
    anio: Mapped[int] = mapped_column(Integer, primary_key=True)
    mes: Mapped[int] = mapped_column(Integer, primary_key=True)
    cerrado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    cerrado_por: Mapped[str] = mapped_column(String(128), default="")


class HistorialPeriodo(Base):
    """
    Bitácora de cierres y reaperturas del cliente (P2-08), para la pantalla de periodos.

    `mes = 0` marca un evento del ejercicio (cierre anual o su reversa). La bitácora general
    (`eventos_auditoria`) también recibe cada evento; ésta es la vista por cliente y periodo.
    """

    __tablename__ = "historial_periodos"
    __table_args__ = (Index("ix_historial_periodo_cliente", "cliente_id", "anio", "mes"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id", ondelete="CASCADE"))
    anio: Mapped[int] = mapped_column(Integer)
    mes: Mapped[int] = mapped_column(Integer)
    # cerrar | reabrir | cierre_anual | deshacer_cierre_anual
    accion: Mapped[str] = mapped_column(String(24))
    motivo: Mapped[str] = mapped_column(String(500), default="")
    uid: Mapped[str] = mapped_column(String(128), default="")
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True))
