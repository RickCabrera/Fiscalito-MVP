"""
Tipos de captura de las variables del periodo. (P4-05)

Separado de `variables.py` por el tope de 300 líneas; `variables.py` los re-exporta.
Fundamentos en el docstring de `variables.py`.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.exceptions import FiscalValidationError

CERO = Decimal("0.00")
PRIMA_DOMINICAL_DE_LEY = Decimal("0.25")  # LFT Art. 71
HORAS_JORNADA_DE_LEY = Decimal("8")  # LFT Art. 61

TIPOS_INCAPACIDAD = {"01": "Riesgo de trabajo", "02": "Enfermedad en general", "03": "Maternidad"}

# Percepciones adicionales que se aceptan capturadas, con si integran al SBC
# variable (Art. 27 LSS). Las que no están aquí se rechazan: el catálogo es
# lista blanca, igual que `isr_nomina.GRAVADAS_AL_100`.
PERCEPCIONES_CAPTURABLES: dict[str, tuple[str, str]] = {
    "010": ("PREMIO DE PUNTUALIDAD", "premio"),
    "049": ("PREMIO DE ASISTENCIA", "premio"),
    "038": ("OTROS INGRESOS POR SALARIOS", "integra"),
    "002": ("GRATIFICACIÓN ANUAL (AGUINALDO)", "no_integra"),
}


@dataclass(frozen=True)
class Incapacidad:
    """Días de incapacidad del periodo. `tipo` = c_TipoIncapacidad."""

    tipo: str
    dias: int

    def __post_init__(self) -> None:
        if self.tipo not in TIPOS_INCAPACIDAD:
            raise FiscalValidationError(
                f"Tipo de incapacidad {self.tipo!r} inválido: {', '.join(TIPOS_INCAPACIDAD)}."
            )
        if self.dias < 0:
            raise FiscalValidationError("Los días de incapacidad no pueden ser negativos.")


@dataclass(frozen=True)
class CreditoInfonavit:
    """
    Crédito Infonavit del trabajador. Tres formas de descuento.

    - `porcentaje`: fracción del SBC por día cotizado.
    - `cuota_fija`: monto MENSUAL; se prorratea por días naturales.
    - `factor`: veces el valor diario de la unidad (VSM o UMI) al mes.
      # FUENTE POR CONFIRMAR: el valor de la UMI/VSM lo publica el Infonavit cada
      # año y no está versionado en este repo; llega como `valor_unidad_diario`.
    """

    tipo: str
    valor: Decimal
    valor_unidad_diario: Decimal | None = None

    def __post_init__(self) -> None:
        if self.tipo not in ("porcentaje", "cuota_fija", "factor"):
            raise FiscalValidationError(f"Tipo de descuento Infonavit inválido: {self.tipo!r}.")
        if self.valor < 0:
            raise FiscalValidationError("El descuento Infonavit no puede ser negativo.")
        if self.tipo == "porcentaje" and self.valor > 1:
            raise FiscalValidationError(
                f"Infonavit en fracción: {self.valor} parece porcentaje (0.20, no 20)."
            )
        if self.tipo == "factor" and not self.valor_unidad_diario:
            raise FiscalValidationError(
                "El descuento por factor necesita el valor diario de la VSM/UMI vigente "
                "(lo publica el Infonavit; no está en el motor)."
            )


@dataclass(frozen=True)
class PensionAlimenticia:
    """Pensión ordenada por autoridad (LFT Art. 110 fr. V)."""

    tipo: str  # porcentaje | monto
    valor: Decimal
    base: str = "neto"  # neto | bruto

    def __post_init__(self) -> None:
        if self.tipo not in ("porcentaje", "monto") or self.base not in ("neto", "bruto"):
            raise FiscalValidationError(
                "Pensión alimenticia: tipo porcentaje|monto, base neto|bruto."
            )
        if self.valor < 0 or (self.tipo == "porcentaje" and self.valor > 1):
            raise FiscalValidationError(
                f"Pensión alimenticia inválida: {self.valor} (porcentaje en fracción, 0 a 1)."
            )


@dataclass(frozen=True)
class PercepcionCapturada:
    """Un bono o premio capturado a mano. `clave` = c_TipoPercepcion."""

    clave: str
    importe: Decimal
    concepto: str = ""


@dataclass(frozen=True)
class VariablesEmpleado:
    """Todo lo variable de un empleado en el periodo. Ceros = no aplica."""

    empleado_no: str
    horas_dobles: Decimal = CERO
    horas_triples: Decimal = CERO
    horas_jornada: Decimal = HORAS_JORNADA_DE_LEY
    domingos_trabajados: int = 0
    prima_dominical: Decimal = PRIMA_DOMINICAL_DE_LEY
    dias_vacaciones: int = 0
    prima_vacacional: Decimal = Decimal("0.25")
    incapacidades: tuple[Incapacidad, ...] = ()
    faltas_adicionales: int = 0
    percepciones: tuple[PercepcionCapturada, ...] = ()
    infonavit: CreditoInfonavit | None = None
    fonacot: Decimal = CERO
    prestamo: Decimal = CERO
    pension: PensionAlimenticia | None = None
    viaticos_comprobados: Decimal = CERO
    # O3: prima vacacional ya exenta en el año fuera de este sistema (Art. 93 fr. XIV:
    # 15 UMA por año calendario). Se suma a lo que ya consta en el historial.
    prima_vacacional_exenta_previa: Decimal = CERO

    def __post_init__(self) -> None:
        negativos = [
            n
            for n in (
                "horas_dobles",
                "horas_triples",
                "fonacot",
                "prestamo",
                "viaticos_comprobados",
            )
            if getattr(self, n) < 0
        ]
        if (
            negativos
            or self.domingos_trabajados < 0
            or self.dias_vacaciones < 0
            or self.faltas_adicionales < 0
        ):
            raise FiscalValidationError(f"{self.empleado_no}: hay variables negativas.")
        if self.horas_jornada <= 0:
            raise FiscalValidationError(f"{self.empleado_no}: la jornada debe ser positiva.")
        if self.prima_dominical < PRIMA_DOMINICAL_DE_LEY:
            raise FiscalValidationError(
                f"{self.empleado_no}: la prima dominical no puede ser menor al 25 % (Art. 71 LFT)."
            )
        for p in self.percepciones:
            if p.clave not in PERCEPCIONES_CAPTURABLES:
                raise FiscalValidationError(
                    f"{self.empleado_no}: la percepción {p.clave} no se puede capturar aquí. "
                    f"Admitidas: {', '.join(sorted(PERCEPCIONES_CAPTURABLES))}."
                )
            if p.importe < 0:
                raise FiscalValidationError(f"{self.empleado_no}: importe negativo en {p.clave}.")

    @property
    def dias_incapacidad(self) -> int:
        return sum(i.dias for i in self.incapacidades)
