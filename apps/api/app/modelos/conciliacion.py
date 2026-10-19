"""
Conciliación bancaria (plan P, P2-06): cuentas bancarias del cliente, plantillas de
importación, estados de cuenta importados, sus movimientos normalizados y las
conciliaciones (qué movimientos del banco quedaron casados con qué movimientos de pólizas o
CFDI de la bóveda).

TODO CUELGA DE `clientes.id`
----------------------------
Igual que la contabilidad: se llega aquí sólo desde un cliente obtenido con `cliente_o_404`,
y todo id que llega en la URL se busca junto con `cliente_id`.

SIGNOS
------
El estado de cuenta se guarda como lo escribe el banco: `cargo` = retiro (sale dinero),
`abono` = depósito (entra dinero). En libros es al revés para la cuenta de bancos (un
depósito es un CARGO a bancos). El emparejador compara importes con signo (+ entra,
− sale) para no confundirlos.

UNA PARTIDA SE CONCILIA UNA SOLA VEZ
------------------------------------
`partidas_conciliacion` tiene llaves únicas por movimiento bancario, por movimiento de póliza
y por comprobante: el mismo renglón no puede quedar en dos conciliaciones. Deshacer una
conciliación borra sus partidas (en cascada) y los renglones vuelven a quedar pendientes.
"""

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, ConMarcasDeTiempo

DINERO = Numeric(18, 2)


class CuentaBancaria(ConMarcasDeTiempo, Base):
    """Una cuenta de banco del cliente, ligada a su cuenta contable (afectable)."""

    __tablename__ = "cuentas_bancarias"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cliente_id: Mapped[int] = mapped_column(
        ForeignKey("clientes.id", ondelete="CASCADE"), index=True
    )
    # Clave del banco en el catálogo c_Banco del SAT (Anexo 24), p. ej. "012" BBVA.
    banco: Mapped[str] = mapped_column(String(3))
    nombre: Mapped[str] = mapped_column(String(120), default="")
    numero: Mapped[str] = mapped_column(String(30), default="")
    clabe: Mapped[str] = mapped_column(String(18), default="")
    moneda: Mapped[str] = mapped_column(String(3), default="MXN")
    cuenta_contable_id: Mapped[int] = mapped_column(
        ForeignKey("cuentas_contables.id", ondelete="RESTRICT"), index=True
    )
    # Criterio del despacho (DP-3): días de tolerancia entre la fecha del banco y la de la
    # póliza, y puntaje mínimo para conciliar en automático.
    ventana_dias: Mapped[int] = mapped_column(Integer, default=3)
    umbral: Mapped[int] = mapped_column(Integer, default=60)
    activa: Mapped[bool] = mapped_column(Boolean, default=True)


class PlantillaEstadoCuenta(ConMarcasDeTiempo, Base):
    """Mapeo de columnas guardado para importar CSV/XLSX de un banco."""

    __tablename__ = "plantillas_estado_cuenta"
    __table_args__ = (UniqueConstraint("cliente_id", "nombre", name="uq_plantilla_nombre"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cliente_id: Mapped[int] = mapped_column(
        ForeignKey("clientes.id", ondelete="CASCADE"), index=True
    )
    nombre: Mapped[str] = mapped_column(String(80))
    banco: Mapped[str] = mapped_column(String(3), default="")
    # csv | xlsx
    formato: Mapped[str] = mapped_column(String(4), default="csv")
    mapeo: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class EstadoCuenta(ConMarcasDeTiempo, Base):
    """Un archivo de estado de cuenta importado."""

    __tablename__ = "estados_cuenta"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cliente_id: Mapped[int] = mapped_column(
        ForeignKey("clientes.id", ondelete="CASCADE"), index=True
    )
    cuenta_bancaria_id: Mapped[int] = mapped_column(
        ForeignKey("cuentas_bancarias.id", ondelete="CASCADE"), index=True
    )
    archivo: Mapped[str] = mapped_column(String(200), default="")
    # csv | xlsx | ofx | pdf
    formato: Mapped[str] = mapped_column(String(4))
    sha256: Mapped[str] = mapped_column(String(64))
    desde: Mapped[date | None] = mapped_column(Date)
    hasta: Mapped[date | None] = mapped_column(Date)
    saldo_inicial: Mapped[Decimal | None] = mapped_column(DINERO)
    saldo_final: Mapped[Decimal | None] = mapped_column(DINERO)
    nuevos: Mapped[int] = mapped_column(Integer, default=0)
    duplicados: Mapped[int] = mapped_column(Integer, default=0)
    advertencias: Mapped[list[Any]] = mapped_column(JSON, default=list)
    creado_por: Mapped[str] = mapped_column(String(128), default="")


class MovimientoBancario(Base):
    """Un renglón normalizado del estado de cuenta."""

    __tablename__ = "movimientos_bancarios"
    __table_args__ = (
        UniqueConstraint("cuenta_bancaria_id", "huella", name="uq_movbanco_huella"),
        Index("ix_movbanco_cuenta_fecha", "cuenta_bancaria_id", "fecha"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cliente_id: Mapped[int] = mapped_column(
        ForeignKey("clientes.id", ondelete="CASCADE"), index=True
    )
    cuenta_bancaria_id: Mapped[int] = mapped_column(
        ForeignKey("cuentas_bancarias.id", ondelete="CASCADE")
    )
    estado_cuenta_id: Mapped[int] = mapped_column(
        ForeignKey("estados_cuenta.id", ondelete="CASCADE"), index=True
    )
    fecha: Mapped[date] = mapped_column(Date)
    concepto: Mapped[str] = mapped_column(String(300), default="")
    referencia: Mapped[str] = mapped_column(String(100), default="")
    cargo: Mapped[Decimal] = mapped_column(DINERO, default=Decimal("0"))
    abono: Mapped[Decimal] = mapped_column(DINERO, default=Decimal("0"))
    saldo: Mapped[Decimal | None] = mapped_column(DINERO)
    # Orden dentro del archivo (para el saldo corrido y para desempatar fechas iguales).
    renglon: Mapped[int] = mapped_column(Integer, default=0)
    # sha256 de (fecha, concepto, referencia, cargo, abono, saldo, n-ésima repetición):
    # importar dos veces el mismo estado no duplica.
    huella: Mapped[str] = mapped_column(String(64))


class Conciliacion(ConMarcasDeTiempo, Base):
    """Un emparejamiento: uno o varios movimientos del banco contra uno o varios de libros."""

    __tablename__ = "conciliaciones"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cliente_id: Mapped[int] = mapped_column(
        ForeignKey("clientes.id", ondelete="CASCADE"), index=True
    )
    cuenta_bancaria_id: Mapped[int] = mapped_column(
        ForeignKey("cuentas_bancarias.id", ondelete="CASCADE"), index=True
    )
    # automatica | manual | poliza (póliza creada desde el movimiento bancario)
    tipo: Mapped[str] = mapped_column(String(10))
    puntaje: Mapped[int] = mapped_column(Integer, default=0)
    motivo: Mapped[str] = mapped_column(String(300), default="")
    creado_por: Mapped[str] = mapped_column(String(128), default="")


class PartidaConciliacion(Base):
    """Un renglón conciliado: banco, movimiento de póliza o CFDI (uno de los tres)."""

    __tablename__ = "partidas_conciliacion"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    conciliacion_id: Mapped[int] = mapped_column(
        ForeignKey("conciliaciones.id", ondelete="CASCADE"), index=True
    )
    movimiento_bancario_id: Mapped[int | None] = mapped_column(
        ForeignKey("movimientos_bancarios.id", ondelete="CASCADE"), unique=True
    )
    movimiento_poliza_id: Mapped[int | None] = mapped_column(
        ForeignKey("movimientos_poliza.id", ondelete="CASCADE"), unique=True
    )
    comprobante_id: Mapped[int | None] = mapped_column(
        ForeignKey("comprobantes.id", ondelete="CASCADE"), unique=True
    )
