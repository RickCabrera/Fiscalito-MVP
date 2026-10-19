"""
Finiquito y liquidación. (P4-06) — funciones puras.

FINIQUITO = lo que se le debe a cualquiera que se va: salarios devengados,
aguinaldo, vacaciones y prima vacacional proporcionales (y prima de antigüedad
si procede). LIQUIDACIÓN = finiquito + indemnizaciones cuando la separación es
imputable al patrón.

FUENTES
-------
- **LFT Art. 87**: aguinaldo proporcional al tiempo trabajado en el año.
- **LFT Arts. 76 y 79**: vacaciones; al terminar antes del año, remuneración
  proporcional al tiempo de servicios. **Art. 80**: prima vacacional ≥ 25 %.
- **LFT Art. 162**: prima de antigüedad de **12 días por año** de servicios, con el
  salario topado por los **Arts. 485 y 486** (no más del doble del salario mínimo
  del área). Se paga a quien se separa voluntariamente con **15 años** o más, a
  quien se separa por causa justificada y a quien es separado —justificada o
  injustificadamente—, y en caso de muerte cualquiera que sea la antigüedad.
- **LFT Arts. 48, 49 y 50**: despido injustificado: **3 meses** de salario
  (Art. 48 / Art. 50 fr. III) y, cuando el patrón se niega a reinstalar (Art. 49)
  o en relación por tiempo indeterminado, **20 días por año** (Art. 50 fr. II).
- **LISR Art. 93 fr. XIII**: prima de antigüedad, retiro e indemnizaciones exentos
  hasta **90 UMA por año de servicio**; fracción de más de seis meses = año
  completo. **Art. 93 fr. XIV**: aguinaldo (30 UMA) y prima vacacional (15 UMA).
- ISR de la parte gravada de separación: **Arts. 95 y 96** (`isr_separacion`).
  Lo ordinario (aguinaldo, vacaciones, prima, salarios) con el Art. 96.

# FUENTE POR CONFIRMAR: "3 meses" = 90 días de salario diario (práctica de las
# Juntas/Tribunales). Algunos usan 3 × 30.4. Configurable vía `DIAS_TRES_MESES`.
# DECISIÓN PROVISIONAL (nocturno): las indemnizaciones se calculan con el salario
# diario integrado capturado (salario + prestaciones, Art. 84 LFT); la prima de
# antigüedad con el salario diario topado a 2 SM (Art. 486).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from app.constants import ZonaSalarioMinimo, salario_minimo_vigente, uma_vigente
from app.exceptions import FiscalValidationError
from app.nomina_engine.aguinaldo import aguinaldo_proporcional, dias_trabajados_en_el_anio
from app.nomina_engine.isr_extraordinario import isr_art_96, isr_separacion
from app.redondeo import redondear

CERO = Decimal("0.00")
DIAS_ANIO = Decimal("365")
DIAS_PRIMA_ANTIGUEDAD = 12  # Art. 162 fr. I LFT
ANIOS_PRIMA_VOLUNTARIA = 15  # Art. 162 fr. III LFT
DIAS_TRES_MESES = Decimal("90")  # Arts. 48 y 50 fr. III LFT — FUENTE POR CONFIRMAR
DIAS_POR_ANIO_INDEMNIZACION = 20  # Art. 50 fr. II LFT
UMAS_EXENCION_SEPARACION = 90  # Art. 93 fr. XIII LISR
UMAS_PRIMA_VACACIONAL = 15
UMAS_AGUINALDO = 30

CAUSAS = {
    "renuncia": "Separación voluntaria",
    "despido_justificado": "Despido justificado (Art. 47 LFT)",
    "despido_injustificado": "Despido injustificado (Arts. 48-50 LFT)",
    "muerte": "Muerte del trabajador",
    "termino_contrato": "Terminación de la relación (Art. 53 LFT)",
}


@dataclass(frozen=True)
class DatosSeparacion:
    """Lo que el cálculo necesita del trabajador y de la separación."""

    fecha_alta: date
    fecha_baja: date
    salario_diario: Decimal
    salario_diario_integrado: Decimal
    causa: str
    zona: ZonaSalarioMinimo = ZonaSalarioMinimo.GENERAL
    dias_aguinaldo: int = 15
    dias_vacaciones_anio: int = 12
    prima_vacacional: Decimal = Decimal("0.25")
    dias_vacaciones_pendientes: Decimal = CERO  # de años anteriores, no disfrutadas
    dias_salario_pendientes: int = 0
    aguinaldo_ya_pagado: Decimal = CERO
    # O4: False por default. Los 20 días por año (Art. 50 fr. II) proceden cuando el patrón
    # se niega a reinstalar (Art. 49) o el trabajador rescinde por causa imputable al
    # patrón (Art. 52); en un despido injustificado con reinstalación ofrecida no.
    incluir_20_dias: bool = False

    def __post_init__(self) -> None:
        if self.causa not in CAUSAS:
            raise FiscalValidationError(f"Causa inválida {self.causa!r}: {', '.join(CAUSAS)}.")
        if self.fecha_baja < self.fecha_alta:
            raise FiscalValidationError("La baja no puede ser anterior al alta.")
        if self.salario_diario <= 0 or self.salario_diario_integrado < self.salario_diario:
            raise FiscalValidationError("Salario diario positivo y SDI ≥ salario diario.")


@dataclass(frozen=True)
class Concepto:
    """Una línea del finiquito, con gravado/exento y fundamento."""

    clave: str
    concepto: str
    importe: Decimal
    exento: Decimal
    gravado: Decimal
    fundamento: str
    separacion: bool = False


@dataclass(frozen=True)
class ResultadoFiniquito:
    """Desglose completo con el ISR."""

    anios_servicio: Decimal
    anios_para_exencion: int
    conceptos: tuple[Concepto, ...]
    total: Decimal
    isr_ordinario: Decimal
    isr_separacion: Decimal
    neto: Decimal
    ultimo_sueldo_mensual: Decimal
    notas: tuple[str, ...] = field(default_factory=tuple)


def anios_de_servicio(alta: date, baja: date) -> Decimal:
    """Años de servicio con fracción (días ÷ 365)."""
    return Decimal((baja - alta).days + 1) / DIAS_ANIO


def anios_para_exencion(alta: date, baja: date) -> int:
    """Años completos; una fracción de más de seis meses cuenta como año (Art. 93 fr. XIII)."""
    anios = anios_de_servicio(alta, baja)
    enteros = int(anios)
    return enteros + (1 if anios - enteros > Decimal("0.5") else 0)


def procede_prima_antiguedad(causa: str, anios: Decimal) -> bool:
    """Art. 162 fr. III y V LFT."""
    if causa == "renuncia":
        return anios >= ANIOS_PRIMA_VOLUNTARIA
    return causa in ("despido_justificado", "despido_injustificado", "muerte")


def prima_antiguedad(d: DatosSeparacion) -> Decimal:
    """12 días por año, salario topado al doble del mínimo (Arts. 162, 485 y 486 LFT)."""
    tope = salario_minimo_vigente(d.fecha_baja, d.zona) * 2
    salario = min(d.salario_diario, tope)
    return redondear(
        salario * DIAS_PRIMA_ANTIGUEDAD * anios_de_servicio(d.fecha_alta, d.fecha_baja)
    )


def _proporcional_vacaciones(d: DatosSeparacion) -> Decimal:
    """Días de vacaciones devengados desde el último aniversario (Art. 79 LFT)."""
    try:
        aniversario = d.fecha_alta.replace(year=d.fecha_baja.year)
    except ValueError:  # 29 de febrero
        aniversario = date(d.fecha_baja.year, 3, 1)
    if aniversario > d.fecha_baja:
        try:
            aniversario = aniversario.replace(year=d.fecha_baja.year - 1)
        except ValueError:
            aniversario = date(d.fecha_baja.year - 1, 3, 1)
    aniversario = max(aniversario, d.fecha_alta)
    dias = Decimal((d.fecha_baja - aniversario).days + 1)
    return Decimal(d.dias_vacaciones_anio) * dias / DIAS_ANIO + d.dias_vacaciones_pendientes


def calcular_finiquito(
    d: DatosSeparacion, ingreso_ordinario_mensual: Decimal = CERO
) -> ResultadoFiniquito:
    """Finiquito (y liquidación si la causa la genera), con exenciones e ISR."""
    fecha, uma = d.fecha_baja, uma_vigente(d.fecha_baja)
    anios = anios_de_servicio(d.fecha_alta, d.fecha_baja)
    anios_ex = anios_para_exencion(d.fecha_alta, d.fecha_baja)
    c: list[Concepto] = []

    if d.dias_salario_pendientes:
        s = redondear(d.salario_diario * d.dias_salario_pendientes)
        c.append(Concepto("001", "SALARIOS DEVENGADOS", s, CERO, s, "Art. 84 LFT"))
    dias_anio = dias_trabajados_en_el_anio(d.fecha_alta, fecha.year, fecha)
    agui = max(
        aguinaldo_proporcional(d.salario_diario, d.dias_aguinaldo, dias_anio)
        - d.aguinaldo_ya_pagado,
        CERO,
    )
    if agui:
        ex = min(agui, redondear(uma * UMAS_AGUINALDO))
        c.append(
            Concepto(
                "002",
                "AGUINALDO PROPORCIONAL",
                agui,
                ex,
                agui - ex,
                "Art. 87 LFT; Art. 93 fr. XIV LISR (30 UMA)",
            )
        )
    dias_vac = _proporcional_vacaciones(d)
    vac = redondear(d.salario_diario * dias_vac)
    if vac:
        c.append(
            Concepto(
                "001",
                "VACACIONES PROPORCIONALES",
                vac,
                CERO,
                vac,
                "Arts. 76 y 79 LFT; gravadas (sin exención en el Art. 93)",
            )
        )
        prima = redondear(vac * d.prima_vacacional)
        ex = min(prima, redondear(uma * UMAS_PRIMA_VACACIONAL))
        c.append(
            Concepto(
                "021",
                "PRIMA VACACIONAL PROPORCIONAL",
                prima,
                ex,
                prima - ex,
                "Art. 80 LFT; Art. 93 fr. XIV LISR (15 UMA)",
            )
        )

    separacion: list[tuple[str, str, Decimal, str]] = []
    if procede_prima_antiguedad(d.causa, anios):
        separacion.append(
            ("022", "PRIMA DE ANTIGÜEDAD", prima_antiguedad(d), "Arts. 162, 485 y 486 LFT")
        )
    if d.causa == "despido_injustificado":
        separacion.append(
            (
                "025",
                "INDEMNIZACIÓN 3 MESES",
                redondear(d.salario_diario_integrado * DIAS_TRES_MESES),
                "Arts. 48 y 50 fr. III LFT",
            )
        )
        if d.incluir_20_dias:
            separacion.append(
                (
                    "025",
                    "INDEMNIZACIÓN 20 DÍAS POR AÑO",
                    redondear(d.salario_diario_integrado * DIAS_POR_ANIO_INDEMNIZACION * anios),
                    "Arts. 49 y 50 fr. II LFT",
                )
            )
    exento_disponible = redondear(uma * UMAS_EXENCION_SEPARACION * anios_ex)
    for clave, nombre, importe, fund in separacion:
        ex = min(importe, exento_disponible)
        exento_disponible -= ex
        c.append(
            Concepto(
                clave,
                nombre,
                importe,
                ex,
                importe - ex,
                f"{fund}; Art. 93 fr. XIII LISR (90 UMA × {anios_ex} años)",
                True,
            )
        )

    usmo = redondear(d.salario_diario * Decimal("30"))
    # DECISIÓN PROVISIONAL (nocturno): último sueldo mensual ordinario = salario
    # diario × 30. La ley no fija el divisor; el SAT acepta 30 o 30.4 en la práctica.
    gravado_ord = sum((x.gravado for x in c if not x.separacion), start=CERO)
    gravado_sep = sum((x.gravado for x in c if x.separacion), start=CERO)
    isr_ord = isr_art_96(gravado_ord, ingreso_ordinario_mensual, fecha).isr
    isr_sep = isr_separacion(gravado_sep, usmo, fecha, ingreso_ordinario_mensual + gravado_ord).isr
    total = sum((x.importe for x in c), start=CERO)
    notas = [f"Causa: {CAUSAS[d.causa]}."]
    if d.causa == "despido_injustificado" and not d.incluir_20_dias:
        notas.append(
            "No incluye los 20 días por año (Art. 50 fr. II LFT): proceden cuando el patrón se "
            "niega a reinstalar (Art. 49) o el trabajador rescinde (Art. 52). Actívalos si aplica."
        )
    if not procede_prima_antiguedad(d.causa, anios):
        notas.append(
            "No procede prima de antigüedad: renuncia con menos de 15 años (Art. 162 fr. III)."
        )
    return ResultadoFiniquito(
        anios_servicio=anios.quantize(Decimal("0.0001")),
        anios_para_exencion=anios_ex,
        conceptos=tuple(c),
        total=total,
        isr_ordinario=isr_ord,
        isr_separacion=isr_sep,
        neto=total - isr_ord - isr_sep,
        ultimo_sueldo_mensual=usmo,
        notas=tuple(notas),
    )
