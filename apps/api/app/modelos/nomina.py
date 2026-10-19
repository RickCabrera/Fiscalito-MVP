"""
Historial de nóminas (P4-02): cada periodo calculado con sus recibos.

UNA NÓMINA VIEJA SE ABRE IGUAL A COMO SE CALCULÓ
------------------------------------------------
`resultado` guarda la respuesta completa del cálculo tal como salió, y
`parametros` las magnitudes con las que se hizo (UMA, salario mínimo, tarifa,
porcentaje del subsidio, versión del motor) y `criterios` los criterios del
cliente vigentes en ese momento. Abrir un periodo devuelve `resultado` sin
recalcular nada: si mañana cambia una tabla o un criterio, lo de hace tres meses
sigue diciendo lo mismo.

ESTADOS
-------
borrador → calculada al guardar el primer cálculo; se puede recalcular.
cerrada → bloquea edición y recálculo. timbrada → reservado para P4-11.
"""

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, Date, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, ConMarcasDeTiempo

DINERO = Numeric(18, 2)

TIPOS_NOMINA = ("ordinaria", "extraordinaria", "finiquito", "aguinaldo", "ptu", "asimilados")
ESTADOS_NOMINA = ("borrador", "calculada", "cerrada", "timbrada")


class NominaPeriodo(ConMarcasDeTiempo, Base):
    """Un periodo de nómina de un cliente."""

    __tablename__ = "nomina_periodos"
    __table_args__ = (Index("ix_nomina_cliente_inicio", "cliente_id", "inicio"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cliente_id: Mapped[int] = mapped_column(
        ForeignKey("clientes.id", ondelete="CASCADE"), index=True
    )
    despacho_id: Mapped[str] = mapped_column(String(128), index=True)
    tipo: Mapped[str] = mapped_column(String(20), default="ordinaria")
    periodicidad: Mapped[str] = mapped_column(String(2), default="04")
    inicio: Mapped[date] = mapped_column(Date)
    fin: Mapped[date] = mapped_column(Date)
    fecha_pago: Mapped[date] = mapped_column(Date)
    estado: Mapped[str] = mapped_column(String(12), default="calculada")
    empleados: Mapped[int] = mapped_column(default=0)
    total_percepciones: Mapped[Decimal] = mapped_column(DINERO, default=Decimal("0"))
    total_deducciones: Mapped[Decimal] = mapped_column(DINERO, default=Decimal("0"))
    total_isr: Mapped[Decimal] = mapped_column(DINERO, default=Decimal("0"))
    total_neto: Mapped[Decimal] = mapped_column(DINERO, default=Decimal("0"))
    criterios: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    parametros: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    entrada: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    resultado: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    calculado_por: Mapped[str] = mapped_column(String(128), default="")


class ReciboNomina(ConMarcasDeTiempo, Base):
    """Un recibo de un periodo guardado."""

    __tablename__ = "nomina_recibos"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    periodo_id: Mapped[int] = mapped_column(
        ForeignKey("nomina_periodos.id", ondelete="CASCADE"), index=True
    )
    empleado_no: Mapped[str] = mapped_column(String(60))
    nombre: Mapped[str] = mapped_column(String(300), default="")
    percepciones: Mapped[list[Any]] = mapped_column(JSON, default=list)
    deducciones: Mapped[list[Any]] = mapped_column(JSON, default=list)
    otros_pagos: Mapped[list[Any]] = mapped_column(JSON, default=list)
    total_percepciones: Mapped[Decimal] = mapped_column(DINERO, default=Decimal("0"))
    total_deducciones: Mapped[Decimal] = mapped_column(DINERO, default=Decimal("0"))
    isr: Mapped[Decimal] = mapped_column(DINERO, default=Decimal("0"))
    subsidio: Mapped[Decimal] = mapped_column(DINERO, default=Decimal("0"))
    cuota_obrera: Mapped[Decimal] = mapped_column(DINERO, default=Decimal("0"))
    neto: Mapped[Decimal] = mapped_column(DINERO, default=Decimal("0"))
    uuid_cfdi: Mapped[str | None] = mapped_column(String(36), default=None)
