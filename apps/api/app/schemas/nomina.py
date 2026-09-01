"""
Schemas del cálculo de nómina de un periodo (D-06).

El endpoint es un **orquestador de demo**: un solo cálculo de punta a punta.
Los granulares (SBC, cuotas, recibo por separado) son F1-07.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from app.constants import ZonaSalarioMinimo
from app.nomina_engine.tablas_imss import PRIMA_RT_MAXIMA, PRIMA_RT_MINIMA


class PeriodoNomina(BaseModel):
    """
    Periodo de nómina, inclusivo en los dos extremos.

    `fecha_pago` está separada de `fin` a propósito, y no es un detalle: la
    vigencia de UMA, salario mínimo, tarifa del Anexo 8 y el transitorio de
    enero del subsidio se leen de **la fecha de pago**. Una quincena que cierra
    el 31-ene y se paga el 5-feb se calcula con los valores de febrero.
    """

    inicio: date
    fin: date
    fecha_pago: date | None = Field(
        default=None,
        description="Default: `fin`. DECISIÓN PROVISIONAL (nocturno): se asume "
        "que el patrón paga el último día del periodo. Decide los números de enero.",
    )

    @model_validator(mode="after")
    def _no_invertido(self) -> PeriodoNomina:
        """Un periodo al revés daría días negativos y cuotas sin sentido."""
        if self.fin < self.inicio:
            raise ValueError(
                f"El periodo termina antes de empezar: {self.inicio} a {self.fin}."
            )
        return self

    @property
    def pago(self) -> date:
        return self.fecha_pago or self.fin


class EmpleadoNominaSchema(BaseModel):
    """Un empleado de la plantilla. El SDI es dato de entrada (§D9)."""

    empleado_no: str
    nombre: str = ""
    salario_diario: Decimal = Field(gt=0)
    salario_diario_integrado: Decimal = Field(gt=0)
    zona: ZonaSalarioMinimo = ZonaSalarioMinimo.GENERAL


class IncidenciasEmpleadoSchema(BaseModel):
    """
    Incidencias de un empleado, tal como las devuelve `cerrar-periodo`.

    `dias_periodo` son **días naturales**, no laborables ni cotizados.
    `dias_ausentismo` alimenta `DiasDelPeriodo`; `faltas` descuenta días
    pagados. Hoy son el mismo número; en F1-09 divergen.
    """

    empleado_no: str
    dias_periodo: int = Field(gt=0, le=31)
    faltas: int = Field(ge=0)
    dias_ausentismo: int = Field(ge=0)
    dias_incapacidad: int = Field(default=0, ge=0)


class ParametrosPatron(BaseModel):
    """Parámetros de la empresa que el motor necesita y no puede adivinar."""

    prima_riesgo: Decimal = Field(
        ge=PRIMA_RT_MINIMA,
        le=PRIMA_RT_MAXIMA,
        description=f"Prima de RT autodeterminada (Art. 72 LSS): entre "
        f"{PRIMA_RT_MINIMA} y {PRIMA_RT_MAXIMA}. No es tasa de ley y no tiene default. "
        f"El motor también la valida; aquí se acota para responder 422 en la frontera "
        f"en vez de 500 desde el motor.",
    )
    clave_periodicidad: str = Field(
        default="04",
        description="Clave de c_PeriodicidadPago. 01 diaria, 02 semanal, 04 quincenal, "
        "05 mensual. Catorcenal (03) y decenal (10) responden 422: nadie publica su "
        "tarifa verificada (§D10).",
    )
    dias_pagados: int | None = Field(
        default=None,
        ge=0,
        description="Override de días pagados para todos. Sin él, "
        "`dias_periodo − faltas`.",
    )


class CalcularPeriodoRequest(BaseModel):
    cliente: str
    periodo: PeriodoNomina
    incidencias: tuple[IncidenciasEmpleadoSchema, ...]
    parametros: ParametrosPatron
    empleados: tuple[EmpleadoNominaSchema, ...] | None = Field(
        default=None,
        description="Omitirlo usa la plantilla de la demo, y SÓLO es válido para el "
        "cliente `demo`: calcularle a un cliente real la nómina de otras 9 personas "
        "sería peor que fallar.",
    )
    incluir_explicacion: bool = False

    @model_validator(mode="after")
    def _incidencias_no_vacias(self) -> CalcularPeriodoRequest:
        if not self.incidencias:
            raise ValueError(
                "Se requieren incidencias del periodo. Cierra el periodo en "
                "`/asistencia/cerrar-periodo` antes de calcular."
            )
        return self


class PartidaSchema(BaseModel):
    tipo: str
    clave: str
    concepto: str
    importe: Decimal
    gravado: Decimal | None = None
    exento: Decimal | None = None
    subsidio_causado: Decimal | None = None


class CuotaRamoSchema(BaseModel):
    """Un ramo calculado, con lo necesario para conciliarlo contra la EMA."""

    clave: str
    nombre: str
    base_diaria: Decimal
    dias: int
    patron: Decimal
    obrero: Decimal
    fundamento: str


class ReciboSchema(BaseModel):
    empleado_no: str
    nombre: str
    sbc: Decimal
    sbc_piso_aplicado: bool
    sbc_tope_aplicado: bool
    es_salario_minimo: bool
    dias_periodo: int
    dias_ausentismo: int
    dias_pagados: int
    percepciones: tuple[PartidaSchema, ...]
    deducciones: tuple[PartidaSchema, ...]
    otros_pagos: tuple[PartidaSchema, ...]
    total_percepciones: Decimal
    total_deducciones: Decimal
    neto: Decimal
    cuota_obrera: Decimal
    cuota_patronal: Decimal
    absorbio_cuota_obrera: bool
    ramos: tuple[CuotaRamoSchema, ...]


class PorcionConsolidada(BaseModel):
    """
    Lo devengado en ESTE periodo por los ramos de una periodicidad de entero.

    **No es el entero del Art. 39 LSS.** Una quincena trae media mensualidad de
    EyM/IyV y un doceavo de bimestre de Retiro/CEAV/Infonavit. Para enterar hay
    que sumar los periodos que caen en el mes o en el bimestre.
    """

    periodicidad: str
    por_ramo: dict[str, Decimal]
    total_patron: Decimal
    total_obrero: Decimal
    total: Decimal
    empleados: int


class CalcularPeriodoResponse(BaseModel):
    exito: bool = True
    cliente: str
    periodo: PeriodoNomina
    origen_plantilla: str = Field(
        description="`demo` si se usó la plantilla del servidor, `request` si vino en "
        "el cuerpo. El PDF no puede mentir sobre de quién es la nómina."
    )
    recibos: tuple[ReciboSchema, ...]
    porcion_mensual: PorcionConsolidada
    porcion_bimestral: PorcionConsolidada
    advertencias: tuple[str, ...] = ()
    explicacion: str | None = None
