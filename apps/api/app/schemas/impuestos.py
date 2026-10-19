"""
Esquemas de impuestos del cliente y calculadoras (P3-02, P3-03, P3-07, P3-08).

Los importes viajan como texto o número y se leen como `Decimal` (Pydantic v2 acepta los dos);
las respuestas los devuelven como texto con dos decimales para no perder centavos en JSON.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator

ModoFactor = Literal["truncar", "redondear", "sin_redondeo"]
TipoRecargo = Literal[
    "mora", "prorroga", "parcialidades_12", "parcialidades_24", "parcialidades_mas_24"
]


class ConfigImpuestosSchema(BaseModel):
    """
    Criterio del despacho por cliente (DP-3). Cada default está documentado.

    - `modo_factor` (default `truncar`): cómo se corta al diezmilésimo el factor de
      actualización y la proporción de IVA (Art. 17-A CFF último párrafo). FUENTE POR CONFIRMAR.
    - `tipo_recargo` (default `mora`): tasa de recargos del resumen (Art. 21 CFF + LIF).
    - `tope_meses_recargos` (default 60 = cinco años, Art. 21 CFF; 120 en los supuestos del
      Art. 67).
    - `region_fronteriza` (default no): el cliente aplica el estímulo de IVA al 8 %.
    - `proporcion_iva_modo` (default `calculada` mes a mes, Art. 5o. fr. V c) LIVA) o `fija`
      con `proporcion_iva_fija` (Art. 5o.-C, proporción del ejercicio anterior).
    - `asignacion_iva`: UUID → gravado | exento | indistinto (default indistinto).
    - `isn_aplicar_adicional` (default sí): adicional estatal sobre el ISN (Veracruz 15 %).
    - `isn_claves_excluidas` / `isn_claves_incluidas`: ajustes a la base del ISN.
    - `saldo_favor_iva_inicial`: saldo a favor de IVA anterior al primer mes en la bóveda.
    """

    modo_factor: ModoFactor = "truncar"
    tipo_recargo: TipoRecargo = "mora"
    tope_meses_recargos: int = Field(default=60, ge=1, le=120)
    region_fronteriza: bool = False
    proporcion_iva_modo: Literal["calculada", "fija"] = "calculada"
    proporcion_iva_fija: Decimal | None = Field(default=None, ge=0, le=1)
    asignacion_iva: dict[str, Literal["gravado", "exento", "indistinto"]] = Field(
        default_factory=dict
    )
    isn_aplicar_adicional: bool = True
    isn_claves_excluidas: list[str] = Field(default_factory=list)
    isn_claves_incluidas: list[str] = Field(default_factory=list)
    saldo_favor_iva_inicial: Decimal = Field(default=Decimal("0"), ge=0)

    @field_validator("asignacion_iva")
    @classmethod
    def _uuid_mayusculas(cls, v: dict[str, str]) -> dict[str, str]:
        return {k.strip().upper(): val for k, val in v.items()}


class CapturaRenglon(BaseModel):
    """Captura del contador en un renglón del resumen."""

    importe_a_pagar: Decimal | None = Field(default=None, ge=0)
    subsidio: Decimal = Field(default=Decimal("0"), ge=0)
    compensaciones: Decimal = Field(default=Decimal("0"), ge=0)


class ResumenRequest(BaseModel):
    """`POST /impuestos/clientes/{clave}/resumen`."""

    anio: int = Field(ge=2020, le=2100)
    mes: int = Field(ge=1, le=12)
    fecha_pago: date
    fecha_limite: date | None = Field(
        default=None, description="Si se omite: día 17 del mes siguiente, corrido a hábil."
    )
    capturas: dict[str, CapturaRenglon] = Field(default_factory=dict)
    formato: Literal["json", "xlsx", "csv"] = "json"


class IvaPeriodoRequest(BaseModel):
    """`POST /impuestos/clientes/{clave}/iva`."""

    anio: int = Field(ge=2020, le=2100)
    meses: list[int] = Field(min_length=1, max_length=12)
    saldo_favor_inicial: Decimal | None = Field(default=None, ge=0)
    opciones_saldo: dict[int, Literal["acreditar", "devolucion", "compensacion"]] = Field(
        default_factory=dict
    )


class ActualizacionRequest(BaseModel):
    """`POST /calculadoras/actualizacion-recargos`."""

    monto: Decimal = Field(ge=0)
    fecha_limite: date
    fecha_pago: date
    tipo_recargo: TipoRecargo = "mora"
    modo_factor: ModoFactor = "truncar"
    tope_meses: int = Field(default=60, ge=1, le=120)


class PercepcionEntrada(BaseModel):
    """Una percepción (clave c_TipoPercepcion) para el ISN."""

    clave: str = Field(pattern=r"^\d{3}$")
    importe: Decimal = Field(ge=0)
    descripcion: str = ""


class IsnRequest(BaseModel):
    """
    `POST /calculadoras/isn`.

    Con `cliente` + `anio`/`mes`: usa la entidad del cliente y los CFDI de nómina de la bóveda.
    Sin cliente: `entidad` y `percepciones` (o `total_erogaciones` como una sola percepción).
    """

    cliente: str | None = None
    anio: int | None = Field(default=None, ge=2020, le=2100)
    mes: int | None = Field(default=None, ge=1, le=12)
    entidad: str | None = None
    fecha: date | None = None
    percepciones: list[PercepcionEntrada] = Field(default_factory=list)
    total_erogaciones: Decimal | None = Field(default=None, ge=0)
    aplicar_adicional: bool = True
    claves_excluidas: list[str] = Field(default_factory=list)


class IsrSueldosRequest(BaseModel):
    """`POST /calculadoras/isr-sueldos`."""

    base_gravable: Decimal = Field(ge=0)
    clave_periodicidad: str = Field(default="05", pattern=r"^\d{2}$")
    fecha_pago: date
    ingreso_gravado_mensual: Decimal | None = Field(default=None, ge=0)
    dias_periodo: int = Field(default=30, ge=1, le=31)
    es_trabajador_de_salario_minimo: bool = False


class IsrResicoRequest(BaseModel):
    """`POST /calculadoras/isr-resico`."""

    ingresos_cobrados: Decimal = Field(ge=0)
    isr_retenido: Decimal = Field(default=Decimal("0"), ge=0)


class AguinaldoRequest(BaseModel):
    """`POST /calculadoras/aguinaldo`."""

    salario_diario: Decimal = Field(gt=0)
    dias_aguinaldo: int = Field(default=15, ge=15)
    dias_trabajados_en_el_anio: int = Field(default=365, ge=0, le=366)
    fecha_pago: date
    zona: Literal["general", "zlfn"] = "general"


class PtuRequest(BaseModel):
    """`POST /calculadoras/ptu`."""

    utilidad_repartible: Decimal = Field(ge=0)
    dias_trabajador: int = Field(ge=0, le=366)
    salario_trabajador: Decimal = Field(ge=0)
    total_dias_todos: int = Field(gt=0)
    total_salarios_todos: Decimal = Field(gt=0)
    salario_diario: Decimal = Field(gt=0)
    promedio_ptu_3_anios: Decimal = Field(default=Decimal("0"), ge=0)
    fecha_pago: date


class FiniquitoRequest(BaseModel):
    """`POST /calculadoras/finiquito`."""

    salario_diario: Decimal = Field(gt=0)
    fecha_ingreso: date
    fecha_baja: date
    dias_aguinaldo: int = Field(default=15, ge=15)
    prima_vacacional: Decimal = Field(default=Decimal("0.25"), ge=Decimal("0.25"), le=1)
    dias_vacaciones_pendientes: Decimal = Field(default=Decimal("0"), ge=0)
    dias_pendientes_de_pago: Decimal = Field(default=Decimal("0"), ge=0)
    tipo: Literal[
        "renuncia", "despido_justificado", "despido_injustificado", "muerte", "termino_contrato"
    ] = "renuncia"
    zona: Literal["general", "zlfn"] = "general"
    salario_diario_integrado: Decimal | None = Field(
        default=None,
        gt=0,
        description="SDI para las indemnizaciones (Art. 84 LFT). Sin él, se integra con el "
        "factor de prestaciones mínimas de ley a la antigüedad cumplida.",
    )
    incluir_20_dias: bool = Field(
        default=False,
        description="20 días por año (Art. 50 fr. II): sólo si el patrón se niega a reinstalar "
        "(Art. 49) o el trabajador rescinde (Art. 52).",
    )
