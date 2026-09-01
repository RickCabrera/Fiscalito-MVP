"""
Tipos del orquestador de nomina (D-06).

Viven aparte de `periodo.py` porque juntos pasaban de 340 lineas y la casa
trabaja con un limite de 300 por archivo. Aqui **no hay logica**: son las
formas de entrada y salida de `calcular_periodo`, con el fundamento de cada
campo, que es lo que hace largo el archivo y lo que no se recorta.

`periodo.py` los re-exporta, asi que quien importe de alli sigue funcionando.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from app.constants import ZonaSalarioMinimo
from app.nomina_engine.cuotas import Consolidado, CuotasEmpleado, DiasDelPeriodo
from app.nomina_engine.integracion import SBCAcotado
from app.nomina_engine.recibo import Recibo


@dataclass(frozen=True)
class EmpleadoPeriodo:
    """
    Un empleado de la plantilla del periodo.

    `salario_diario_integrado` es **dato de entrada**, no se deriva de la
    antiguedad (§D9): los factores implicitos del caso real son distintos entre
    empleados y no monotonos con la antiguedad.
    """

    empleado_no: str
    nombre: str
    salario_diario: Decimal
    salario_diario_integrado: Decimal
    zona: ZonaSalarioMinimo = ZonaSalarioMinimo.GENERAL


@dataclass(frozen=True)
class IncidenciasPeriodo:
    """
    Lo que el cierre del checador dice de un empleado.

    OJO CON LA ASIMETRIA, y esta escrita porque en F1-09 deja de ser cosmetica:

    - `DiasDelPeriodo` se construye con **`dias_ausentismo`**, que es el campo
      que `schemas/asistencia.py` declara para eso.
    - `dias_pagados` se descuenta con **`faltas`**.

    Hoy los dos numeros son iguales porque toda ausencia cuenta como falta.
    En F1-09 divergen: una incapacidad o unas vacaciones **no** son ausentismo
    injustificado, y las vacaciones **si se pagan**.

    `dias_periodo` son los **dias naturales**, nunca `dias_laborables` ni
    `dias_cotizados`. Ese ultimo es informativo y tomarlo como base de cuotas
    contradice a `cuotas.py` (Art. 31 LSS, §D3).
    """

    empleado_no: str
    dias_periodo: int
    faltas: int
    dias_ausentismo: int
    dias_incapacidad: int = 0


@dataclass(frozen=True)
class ReciboPeriodo:
    """El resultado de un empleado, con el rastro de como se llego."""

    empleado_no: str
    nombre: str
    sbc: SBCAcotado
    dias: DiasDelPeriodo
    dias_pagados: int
    es_salario_minimo: bool
    recibo: Recibo
    cuotas: CuotasEmpleado


@dataclass(frozen=True)
class ResultadoPeriodo:
    """
    Nomina del periodo.

    `porcion_*` es lo **devengado en este periodo**, no el entero del Art. 39.
    Ver el encabezado del modulo.
    """

    recibos: tuple[ReciboPeriodo, ...]
    porcion_mensual: Consolidado
    porcion_bimestral: Consolidado
    advertencias: tuple[str, ...] = field(default_factory=tuple)

    # Los totales del periodo cruzan las dos periodicidades de entero, y los
    # consumen la ruta (para el prompt del LLM) y la tool del agente. Viven
    # aqui y no en cada consumidor porque sumarlos a mano en dos lugares es
    # como se llega a que el chat y el PDF digan cosas distintas.

    @property
    def total_obrero(self) -> Decimal:
        return self.porcion_mensual.total_obrero + self.porcion_bimestral.total_obrero

    @property
    def total_patron(self) -> Decimal:
        return self.porcion_mensual.total_patron + self.porcion_bimestral.total_patron

    @property
    def total_neto(self) -> Decimal:
        return sum((r.recibo.total for r in self.recibos), start=Decimal("0.00"))

    @property
    def total_isr(self) -> Decimal:
        return sum(
            (r.recibo.total_impuestos_retenidos for r in self.recibos),
            start=Decimal("0.00"),
        )

    @property
    def total_percepciones(self) -> Decimal:
        return sum(
            (r.recibo.total_percepciones for r in self.recibos), start=Decimal("0.00")
        )
