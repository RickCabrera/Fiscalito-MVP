"""
Esquemas de personas morales y de la anual (P3-01, P3-06).

`DatosAnualesPMSchema` es lo que se captura por cliente y ejercicio porque no sale de la
bóveda ni de la contabilidad: coeficiente de utilidad, PTU pagada, pérdidas pendientes,
retenciones del sistema financiero, pagos efectivamente presentados, saldos para el ajuste
anual por inflación cuando no hay contabilidad, y ajustes de deducciones. Cada default está
documentado aquí y en `docs/api-contract.md` §Personas morales.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

MesNum = int


class PerdidaSchema(BaseModel):
    """Pérdida fiscal pendiente (Art. 57). `actualizada_a` 'AAAA-MM' o vacío si es histórica."""

    ejercicio: int = Field(ge=2000, le=2100)
    remanente: Decimal = Field(ge=0)
    actualizada_a: str | None = Field(
        default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$",
        description="Mes de su última actualización. Vacío: el monto es el histórico.",
    )


class EstimuloSchema(BaseModel):
    """Disminución configurable de la utilidad (estímulo), con fundamento."""

    concepto: str = Field(min_length=1, max_length=200)
    importe: Decimal = Field(ge=0)
    fundamento: str = Field(default="", max_length=200)
    desde_mes: int = Field(default=1, ge=1, le=12)
    en_provisionales: bool = True


def _por_mes(v: dict[int, Decimal]) -> dict[int, Decimal]:
    for mes, importe in v.items():
        if not 1 <= int(mes) <= 12:
            raise ValueError("Los meses van de 1 a 12.")
        if importe < 0:
            raise ValueError("Los importes no pueden ser negativos.")
    return {int(k): val for k, val in v.items()}


class DatosAnualesPMSchema(BaseModel):
    """
    Datos de un cliente persona moral para un ejercicio (P3-01).

    - `coeficiente_utilidad`: el que se aplica en los pagos de ESTE ejercicio (el de la anual
      del anterior, Art. 14 fr. I). Vacío: se calcula con `utilidad_fiscal_base` /
      `ingresos_nominales_base` si se capturan, o con la anual que el sistema pueda armar de
      los cinco ejercicios anteriores.
    - `ptu_pagada` y `mes_pago_ptu` (default mayo): Art. 14 fr. II / Art. 211.
    - `perdidas`: pendientes al inicio del ejercicio (Art. 57).
    - `retenciones_bancarias`: ISR retenido por el sistema financiero por mes (Art. 54).
    - `pagos_efectuados`: lo realmente pagado por mes; vacío = el determinado por el sistema.
    - `saldos_creditos` / `saldos_deudas`: 12 saldos de fin de mes para el ajuste anual por
      inflación cuando no hay contabilidad (Arts. 44-46).
    - `cuentas_creditos` / `cuentas_deudas`: códigos agrupadores (prefijos) que cuentan como
      créditos y deudas cuando sí hay contabilidad; vacío = el default documentado en
      `app/impuestos/personas_morales.py` (criterio del despacho).
    - `cuentas_no_deducibles`: prefijos de código agrupador o números de cuenta adicionales que
      no son deducibles.
    - `deduccion_inversiones`: deducción fiscal de inversiones del ejercicio (Arts. 31-38 o
      209); la depreciación contable no se deduce.
    - `deducciones_adicionales` / `no_deducibles_adicionales` / `ingresos_adicionales`:
      ajustes de conciliación contable-fiscal (p. ej. Art. 28 fr. XXX).
    - `fuente`: de dónde salen ingresos y deducciones: `auto` (contabilidad si hay pólizas en
      el ejercicio; si no, bóveda), `contabilidad` o `boveda`.
    - `factor_exentos_nomina` (default 0.47): parte deducible de los pagos exentos al
      trabajador cuando la deducción sale de la bóveda (Art. 28 fr. XXX: 47 % o 53 %).
    - `aai_en_resico` (default no): calcular ajuste anual por inflación en RESICO PM.
    - `no_deducibles_art28_xxx`: parte no deducible de los pagos exentos al trabajador (Art. 28
      fr. XXX) que el Art. 9 quinto párrafo resta de los ingresos para la renta gravable de PTU
      (sólo ahí). Vacío = se deriva: con contabilidad, de `cuentas_art28_xxx` (las cuentas
      donde el despacho registra ese no deducible; también se tratan como no deducibles); con
      bóveda, (1 − `factor_exentos_nomina`) × exentos de la nómina emitida. Con contabilidad y
      sin esas cuentas queda en cero y se avisa (no se baja la PTU sin dato).
    """

    coeficiente_utilidad: Decimal | None = Field(default=None, ge=0, le=1)
    utilidad_fiscal_base: Decimal | None = None
    ingresos_nominales_base: Decimal | None = Field(default=None, ge=0)
    anticipos_miembros_base: Decimal = Field(default=Decimal("0"), ge=0)
    ptu_pagada: Decimal = Field(default=Decimal("0"), ge=0)
    mes_pago_ptu: int = Field(default=5, ge=1, le=12)
    perdidas: list[PerdidaSchema] = Field(default_factory=list)
    retenciones_bancarias: dict[MesNum, Decimal] = Field(default_factory=dict)
    pagos_efectuados: dict[MesNum, Decimal] = Field(default_factory=dict)
    saldos_creditos: list[Decimal] = Field(default_factory=list, max_length=12)
    saldos_deudas: list[Decimal] = Field(default_factory=list, max_length=12)
    cuentas_creditos: list[str] = Field(default_factory=list)
    cuentas_deudas: list[str] = Field(default_factory=list)
    cuentas_no_deducibles: list[str] = Field(default_factory=list)
    deduccion_inversiones: Decimal = Field(default=Decimal("0"), ge=0)
    deducciones_adicionales: Decimal = Field(default=Decimal("0"), ge=0)
    no_deducibles_adicionales: Decimal = Field(default=Decimal("0"), ge=0)
    ingresos_adicionales: Decimal = Field(default=Decimal("0"), ge=0)
    estimulos: list[EstimuloSchema] = Field(default_factory=list)
    fuente: Literal["auto", "contabilidad", "boveda"] = "auto"
    factor_exentos_nomina: Decimal = Field(default=Decimal("0.47"), ge=0, le=1)
    aai_en_resico: bool = False
    no_deducibles_art28_xxx: Decimal | None = Field(default=None, ge=0)
    cuentas_art28_xxx: list[str] = Field(default_factory=list)

    @field_validator("retenciones_bancarias", "pagos_efectuados")
    @classmethod
    def _meses_validos(cls, v: dict[int, Decimal]) -> dict[int, Decimal]:
        return _por_mes(v)

    @model_validator(mode="after")
    def _saldos_pareados(self) -> DatosAnualesPMSchema:
        if len(self.saldos_creditos) != len(self.saldos_deudas):
            raise ValueError("saldos_creditos y saldos_deudas deben tener los mismos meses.")
        return self


class PagosProvisionalesPMRequest(BaseModel):
    """`POST /impuestos/clientes/{clave}/pm/pagos-provisionales`."""

    anio: int = Field(ge=2020, le=2100)
    mes: int = Field(ge=1, le=12)


class AnualRequest(BaseModel):
    """`POST /impuestos/clientes/{clave}/anual` y `.../anual/papeles`."""

    anio: int = Field(ge=2020, le=2100)
    pagos_provisionales: dict[MesNum, Decimal] = Field(
        default_factory=dict,
        description="Personas físicas: pagos realmente presentados por mes (vacío = los "
                    "determinados por el sistema). Personas morales: se capturan en sus datos "
                    "anuales.",
    )

    @field_validator("pagos_provisionales")
    @classmethod
    def _meses_validos(cls, v: dict[int, Decimal]) -> dict[int, Decimal]:
        return _por_mes(v)
