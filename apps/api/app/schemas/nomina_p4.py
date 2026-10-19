"""
Esquemas de la nómina completa (P4-01 a P4-08).

Variables por empleado, historial, y las calculadoras de aguinaldo, PTU,
finiquito y ajuste anual. Dinero en Decimal; JSON de entrada como string o número.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field

CERO = Decimal("0")


class IncapacidadSchema(BaseModel):
    tipo: Literal["01", "02", "03"] = Field(
        description="c_TipoIncapacidad: 01 riesgo de trabajo, 02 enfermedad general, 03 maternidad."
    )
    dias: int = Field(ge=0, le=31)


class InfonavitSchema(BaseModel):
    tipo: Literal["porcentaje", "cuota_fija", "factor"]
    valor: Decimal = Field(ge=0)
    valor_unidad_diario: Decimal | None = Field(
        default=None,
        description="Valor diario de la VSM/UMI vigente para el descuento por factor. "
        "FUENTE POR CONFIRMAR: lo publica el Infonavit; el motor no lo trae.",
    )


class PensionSchema(BaseModel):
    tipo: Literal["porcentaje", "monto"]
    valor: Decimal = Field(ge=0)
    base: Literal["neto", "bruto"] = "neto"


class PercepcionCapturadaSchema(BaseModel):
    clave: Literal["002", "010", "038", "049"]
    importe: Decimal = Field(ge=0)
    concepto: str = ""


class VariablesEmpleadoSchema(BaseModel):
    """Incidencias y variables capturadas por periodo (P4-05)."""

    empleado_no: str
    horas_dobles: Decimal = Field(default=CERO, ge=0)
    horas_triples: Decimal = Field(default=CERO, ge=0)
    horas_jornada: Decimal = Field(default=Decimal("8"), gt=0)
    domingos_trabajados: int = Field(default=0, ge=0)
    prima_dominical: Decimal = Field(default=Decimal("0.25"), ge=Decimal("0.25"), le=1)
    dias_vacaciones: int = Field(default=0, ge=0)
    prima_vacacional: Decimal = Field(default=Decimal("0.25"), ge=Decimal("0.25"), le=1)
    incapacidades: tuple[IncapacidadSchema, ...] = ()
    faltas_adicionales: int = Field(default=0, ge=0)
    percepciones: tuple[PercepcionCapturadaSchema, ...] = ()
    infonavit: InfonavitSchema | None = None
    fonacot: Decimal = Field(default=CERO, ge=0)
    prestamo: Decimal = Field(default=CERO, ge=0)
    pension: PensionSchema | None = None
    viaticos_comprobados: Decimal = Field(default=CERO, ge=0)
    prima_vacacional_exenta_previa: Decimal = Field(
        default=CERO,
        ge=0,
        description="Prima vacacional ya exenta en el año fuera del historial (15 UMA anuales).",
    )


class ResumenPeriodoSchema(BaseModel):
    id: int
    tipo: str
    periodicidad: str
    inicio: date
    fin: date
    fecha_pago: date
    estado: str
    empleados: int
    total_percepciones: Decimal
    total_deducciones: Decimal
    total_isr: Decimal
    total_neto: Decimal


class HistorialResponse(BaseModel):
    exito: bool = True
    cliente: str
    periodos: tuple[ResumenPeriodoSchema, ...]


class PeriodoGuardadoResponse(BaseModel):
    exito: bool = True
    periodo: ResumenPeriodoSchema
    criterios: dict[str, Any]
    parametros: dict[str, Any]
    resultado: dict[str, Any] = Field(
        description="La respuesta del cálculo TAL COMO SALIÓ. No se recalcula al abrir."
    )


class DiferenciaEmpleado(BaseModel):
    empleado_no: str
    nombre: str
    neto_a: Decimal | None
    neto_b: Decimal | None
    diferencia: Decimal


class ComparacionResponse(BaseModel):
    exito: bool = True
    a: ResumenPeriodoSchema
    b: ResumenPeriodoSchema
    diferencia_neto: Decimal
    diferencia_isr: Decimal
    diferencia_percepciones: Decimal
    por_empleado: tuple[DiferenciaEmpleado, ...]


class CriteriosResponse(BaseModel):
    exito: bool = True
    defaults: dict[str, str]
    opciones: dict[str, dict[str, str]]


# ── Calculadoras (P4-06, P4-07, P4-08) ─────────────────────────────────────


class AguinaldoRequest(BaseModel):
    ejercicio: int = Field(ge=2025, le=2100)
    fecha_pago: date
    empleados: tuple[str, ...] = Field(
        default=(), description="Vacío = toda la plantilla de sueldos (régimen 02)."
    )
    exento_ya_aplicado: dict[str, Decimal] = Field(
        default_factory=dict, description="Exento de aguinaldo ya aplicado en el año (anticipos)."
    )
    guardar: bool = True


class PTUTrabajadorSchema(BaseModel):
    empleado_no: str
    dias_trabajados: int = Field(ge=0, le=366)
    salarios_devengados: Decimal = Field(ge=0)
    tipo: Literal["planta", "sindicalizado", "eventual", "confianza", "director"] = "planta"
    promedio_ptu_3_anios: Decimal = Field(default=CERO, ge=0)


class PTURequest(BaseModel):
    ejercicio: int = Field(ge=2020, le=2100, description="Ejercicio de la utilidad.")
    renta_gravable: Decimal = Field(ge=0, description="Dato capturado (Art. 120 LFT).")
    fecha_pago: date
    trabajadores: tuple[PTUTrabajadorSchema, ...] = Field(min_length=1)
    guardar: bool = True


class FiniquitoRequest(BaseModel):
    empleado_no: str
    fecha_baja: date
    causa: Literal[
        "renuncia", "despido_justificado", "despido_injustificado", "muerte", "termino_contrato"
    ]
    dias_salario_pendientes: int = Field(default=0, ge=0, le=31)
    dias_vacaciones_pendientes: Decimal = Field(default=CERO, ge=0)
    aguinaldo_ya_pagado: Decimal = Field(default=CERO, ge=0)
    incluir_20_dias: bool = Field(
        default=False,
        description="20 días por año (Art. 50 fr. II LFT): sólo si el patrón se niega a "
        "reinstalar (Art. 49) o el trabajador rescinde (Art. 52).",
    )
    guardar: bool = True


class AjusteAnualTrabajador(BaseModel):
    empleado_no: str
    ingresos_gravados: Decimal = Field(ge=0)
    ingresos_exentos: Decimal = Field(default=CERO, ge=0)
    isr_retenido: Decimal = Field(ge=0)
    subsidio_correspondido: Decimal = Field(default=CERO, ge=0)
    comunico_que_declara: bool = False
    impuesto_local_retenido: Decimal = Field(
        default=CERO,
        ge=0,
        description="Impuesto local a los ingresos por salarios retenido en el año: se resta "
        "de la base (Art. 97 LISR) si su tasa no excede del 5 %.",
    )
    tasa_impuesto_local: Decimal | None = Field(default=None, ge=0, le=1)


class AjusteAnualRequest(BaseModel):
    ejercicio: int = Field(ge=2026, le=2100)
    trabajadores: tuple[AjusteAnualTrabajador, ...] = Field(
        default=(),
        description="Acumulados capturados. Vacío = se suman del historial de nóminas "
        "ordinarias guardadas del ejercicio.",
    )


class CalculoResponse(BaseModel):
    """Respuesta genérica de las calculadoras: el resultado con su desglose."""

    exito: bool = True
    tipo: str
    periodo_id: int | None = None
    resultado: dict[str, Any]
    advertencias: tuple[str, ...] = ()
