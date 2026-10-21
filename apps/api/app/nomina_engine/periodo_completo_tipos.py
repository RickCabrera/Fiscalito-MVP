"""
Tipos del orquestador de nómina completa (`periodo_completo.py`). Sin lógica.

Asimilados: c_TipoRegimen 05-11 del complemento de nómina 1.2 (catálogo en
`tests/xsd/catNomina.xsd`), fracciones del Art. 94 LISR.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from app.constants import ZonaSalarioMinimo
from app.nomina_engine.cuotas import CuotasEmpleado
from app.nomina_engine.recibo import Recibo

REGIMEN_SUELDOS = "02"
# c_TipoRegimen de asimilados (Art. 94 fr. II a VII LISR). Catálogo en tests/xsd/catNomina.xsd.
REGIMENES_ASIMILADOS = {
    "05": "Asimilados miembros de sociedades cooperativas de producción (fr. II)",
    "06": "Asimilados integrantes de sociedades y asociaciones civiles (fr. II)",
    "07": "Asimilados miembros de consejos (fr. III)",
    "08": "Asimilados comisionistas (fr. VI)",
    "09": "Asimilados honorarios (fr. IV y V)",
    "10": "Asimilados acciones (fr. VII)",
    "11": "Asimilados otros",
}


@dataclass(frozen=True)
class EmpleadoNomina:
    """Un empleado tal como sale de la cartera SQL."""

    empleado_no: str
    nombre: str
    salario_diario: Decimal
    salario_diario_integrado: Decimal
    zona: ZonaSalarioMinimo = ZonaSalarioMinimo.GENERAL
    fecha_alta: date | None = None
    fecha_baja: date | None = None
    tipo_regimen: str = REGIMEN_SUELDOS
    # P6-07: Art. 96 LISR, quinto párrafo. Honorarios a miembros de consejos, administradores,
    # comisarios y gerentes generales: retención no menor a la tasa máxima del Art. 152,
    # "salvo que exista, además, relación de trabajo con el retenedor", en cuyo caso se usa la
    # tarifa del segundo párrafo. Se marca por empleado, NO se deduce del c_TipoRegimen.
    es_consejero: bool = False
    consejero_es_trabajador: bool = False

    @property
    def es_asimilado(self) -> bool:
        return self.tipo_regimen in REGIMENES_ASIMILADOS

    @property
    def aplica_retencion_minima_consejero(self) -> bool:
        """Art. 96 quinto párrafo: consejero sin relación de trabajo con el retenedor."""
        # DECISIÓN PROVISIONAL (conservadora): el c_TipoRegimen 07 ES "miembros de consejos",
        # así que sin marca se aplica la mínima; sólo `consejero_es_trabajador` la quita.
        consejero = self.es_consejero or self.tipo_regimen == "07"
        return self.es_asimilado and consejero and not self.consejero_es_trabajador


@dataclass(frozen=True)
class Incidencia:
    empleado_no: str
    dias_periodo: int
    faltas: int = 0
    dias_ausentismo: int = 0
    dias_incapacidad: int = 0


@dataclass(frozen=True)
class ReciboCompleto:
    empleado_no: str
    nombre: str
    tipo_regimen: str
    sbc: Decimal
    sbc_piso_aplicado: bool
    sbc_tope_aplicado: bool
    es_salario_minimo: bool
    dias_periodo: int
    dias_en_periodo: int
    dias_pagados: int
    dias_ausentismo: int
    dias_incapacidad: int
    parcial: bool
    tarifa: str
    recibo: Recibo
    cuotas: CuotasEmpleado | None
    isr_causado: Decimal
    subsidio_causado: Decimal
    sbc_variable_integrable: Decimal
    detalle_sbc: tuple[tuple[str, Decimal, str], ...]
    avisos: tuple[str, ...] = field(default_factory=tuple)
