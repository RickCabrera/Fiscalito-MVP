"""
Percepciones y deducciones variables del periodo. (P4-05)

Convierte lo que el operador captura por empleado —horas extra, domingos,
vacaciones, incapacidades, créditos, pensión— en partidas del recibo, cada una
con su fundamento. **No calcula ISR**: las exenciones las aplica
`isr_nomina.exentar` (Art. 93 LISR) y el armado vive en `recibo_completo.py`.

FUENTES
-------
- Horas extra: LFT Art. 66 (se pagan con 100 % más = dobles; el tope semanal sube de
  9 a 12 horas entre 2026 y 2030 por el Transitorio Cuarto del Decreto DOF 01-05-2026,
  ver `jornada.py`) y Art. 68 (lo que excede se paga con 200 % más
  = triples). Exención: LISR Art. 93 fr. I (50 % sin exceder 5 UMA por semana,
  **sólo dentro del límite de la LFT**: las triples no tienen exención).
- Prima dominical: LFT Art. 71 (25 % por lo menos del salario ordinario).
  Exención: LISR Art. 93 fr. XIV (1 UMA por domingo).
- Prima vacacional: LFT Art. 80 (25 % mínimo). Exención: 15 UMA al año
  (Art. 93 fr. XIV), acumulando lo exento en el año calendario.
- Incapacidades: los días de incapacidad los paga el IMSS como subsidio
  (LSS Arts. 58, 96 y 101), no el patrón; reducen días pagados y, en los ramos que
  §D3 manda, los días cotizados.
- Descuentos: LFT Art. 110 fr. I (préstamos del patrón: hasta 30 % del excedente
  del salario mínimo), fr. III (Infonavit), fr. V (pensión alimenticia ordenada por
  autoridad) y fr. VII (Fonacot: hasta 20 % del salario).
- Claves de catálogo (`c_TipoPercepcion`, `c_TipoDeduccion`, `c_TipoOtroPago`) del
  complemento de nómina 1.2, versionadas en `tests/xsd/catNomina.xsd`.
- SBC: LSS Art. 27 (qué integra y qué no) y Art. 30 fr. II (lo variable integra el
  bimestre SIGUIENTE, con el promedio del anterior).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from app.constants import DIAS_MES_FISCAL
from app.nomina_engine.isr_nomina import PercepcionGravada
from app.nomina_engine.recibo import PartidaDeduccion
from app.nomina_engine.variables_tipos import (  # noqa: F401 — re-exportados
    PERCEPCIONES_CAPTURABLES,
    TIPOS_INCAPACIDAD,
    CreditoInfonavit,
    Incapacidad,
    PensionAlimenticia,
    PercepcionCapturada,
    VariablesEmpleado,
)
from app.redondeo import redondear

CERO = Decimal("0.00")

# LFT Art. 71: "por lo menos" 25 %. Es el mínimo; un patrón puede dar más.
PRIMA_DOMINICAL_DE_LEY = Decimal("0.25")
# LFT Arts. 66 y 68.
FACTOR_HORA_DOBLE = Decimal("2")
FACTOR_HORA_TRIPLE = Decimal("3")
# LFT Art. 61: jornada diurna máxima de 8 horas. Se usa para el salario por hora.
HORAS_JORNADA_DE_LEY = Decimal("8")
# LSS Art. 27 fr. VII: premios de asistencia y puntualidad no integran mientras
# cada uno no rebase el 10 % del SBC.
TOPE_PREMIOS_SBC = Decimal("0.10")
# LFT Art. 110 fr. VII y fr. I.
TOPE_FONACOT = Decimal("0.20")
TOPE_PRESTAMO_PATRON = Decimal("0.30")


@dataclass(frozen=True)
class ConceptoVariable:
    """Una percepción variable ya valuada, con su efecto en el SBC."""

    clave: str
    clave_interna: str
    concepto: str
    importe: Decimal
    integra_sbc: Decimal
    fundamento: str
    sin_exencion: bool = False  # True = 100 % gravada aunque su clave tenga exención


@dataclass(frozen=True)
class EfectoSBC:
    """Lo que el periodo aporta al SBC variable del bimestre siguiente (Art. 30 fr. II LSS)."""

    integrable: Decimal
    detalle: tuple[tuple[str, Decimal, str], ...] = field(default_factory=tuple)


def percepciones_variables(
    v: VariablesEmpleado, salario_diario: Decimal, sbc: Decimal, dias_pagados: int
) -> tuple[tuple[ConceptoVariable, ...], EfectoSBC]:
    """Valúa las percepciones variables y su efecto en el SBC variable."""
    salario_hora = salario_diario / v.horas_jornada
    conceptos: list[ConceptoVariable] = []
    if v.horas_dobles:
        conceptos.append(
            ConceptoVariable(
                "019",
                "P019D",
                "HORAS EXTRA DOBLES",
                redondear(salario_hora * FACTOR_HORA_DOBLE * v.horas_dobles),
                CERO,
                "Art. 66 LFT (100 % más); no integra: Art. 27 fr. IX LSS",
            )
        )
    if v.horas_triples:
        triples = redondear(salario_hora * FACTOR_HORA_TRIPLE * v.horas_triples)
        conceptos.append(
            ConceptoVariable(
                "019",
                "P019T",
                "HORAS EXTRA TRIPLES",
                triples,
                triples,
                "Art. 68 LFT (200 % más). Exceden el límite de la LFT: 100 % gravadas "
                "(Art. 93 fr. I LISR) e integran al SBC (Art. 27 fr. IX LSS)",
                sin_exencion=True,
            )
        )
    if v.domingos_trabajados:
        prima = redondear(salario_diario * v.prima_dominical * v.domingos_trabajados)
        conceptos.append(
            ConceptoVariable(
                "020",
                "P020",
                "PRIMA DOMINICAL",
                prima,
                prima,
                "Art. 71 LFT; integra al SBC (no está en las exclusiones del Art. 27 LSS)",
            )
        )
    if v.dias_vacaciones:
        prima_vac = redondear(salario_diario * v.dias_vacaciones * v.prima_vacacional)
        conceptos.append(
            ConceptoVariable(
                "021",
                "P021",
                "PRIMA VACACIONAL",
                prima_vac,
                CERO,
                "Art. 80 LFT; ya integrada en el factor (Art. 27 LSS)",
            )
        )
    tope_premio = redondear(sbc * TOPE_PREMIOS_SBC * dias_pagados)
    for p in v.percepciones:
        descripcion, regla = PERCEPCIONES_CAPTURABLES[p.clave]
        if regla == "premio":
            integra = max(p.importe - tope_premio, CERO)
            fund = "Art. 27 fr. VII LSS: integra lo que excede el 10 % del SBC"
        elif regla == "integra":
            integra, fund = p.importe, "Art. 27 LSS: integra"
        else:
            integra, fund = CERO, "Ya integrada en el factor (Art. 27 LSS)"
        conceptos.append(
            ConceptoVariable(
                p.clave,
                f"P{p.clave}",
                p.concepto or descripcion,
                redondear(p.importe),
                redondear(integra),
                fund,
            )
        )
    detalle = tuple((c.concepto, c.integra_sbc, c.fundamento) for c in conceptos if c.integra_sbc)
    return tuple(conceptos), EfectoSBC(sum((c.integra_sbc for c in conceptos), start=CERO), detalle)


def con_exencion_anual(
    g: PercepcionGravada, ya_exento: Decimal, tope_anual: Decimal
) -> PercepcionGravada:
    """
    Limita el exento de una percepción al tope ANUAL menos lo ya exentado en el año.

    O3: la prima vacacional (Art. 93 fr. XIV LISR) está exenta hasta 15 UMA **por año
    calendario**, no por pago. Sin esto, dos pagos en el año exentarían 30 UMA.
    """
    disponible = max(tope_anual - ya_exento, CERO)
    exento = min(g.exento, disponible)
    return PercepcionGravada(
        g.clave,
        g.descripcion,
        g.importe,
        g.importe - exento,
        exento,
        f"{g.fundamento}; tope anual, ya exento en el año {ya_exento}",
    )


def descuento_infonavit(
    credito: CreditoInfonavit, sbc: Decimal, dias_cotizados: int, dias_naturales: int
) -> Decimal:
    """
    Amortización del periodo.

    # DECISIÓN PROVISIONAL (nocturno): el porcentaje se aplica sobre los días
    # cotizados (sin ausentismo ni incapacidad), y la cuota fija y el factor
    # mensuales se prorratean / 30.4 x días naturales. Hay despachos que dividen
    # la cuota bimestral entre los periodos del bimestre.
    """
    if credito.tipo == "porcentaje":
        return redondear(sbc * credito.valor * dias_cotizados)
    if credito.tipo == "cuota_fija":
        return redondear(credito.valor / DIAS_MES_FISCAL * dias_naturales)
    mensual = credito.valor * (credito.valor_unidad_diario or CERO) * DIAS_MES_FISCAL
    return redondear(mensual / DIAS_MES_FISCAL * dias_naturales)


def pension_alimenticia(p: PensionAlimenticia, bruto: Decimal, neto: Decimal) -> Decimal:
    """
    Importe de la pensión. `neto` = percepciones − ISR − cuota obrera.

    # DECISIÓN PROVISIONAL (nocturno): "neto" descuenta sólo las deducciones de
    # ley (ISR e IMSS). La orden judicial manda; si define otra base, se captura
    # como monto.
    """
    if p.tipo == "monto":
        return redondear(p.valor)
    return redondear((bruto if p.base == "bruto" else neto) * p.valor)


def descuentos_capturados(
    v: VariablesEmpleado,
    sueldo: Decimal,
    bruto: Decimal,
    neto_de_ley: Decimal,
    sbc: Decimal,
    dias_cotizados: int | None,
    dias_naturales: int,
) -> tuple[list[PartidaDeduccion], list[str]]:
    """
    Infonavit, Fonacot, préstamo y pensión del periodo, con sus topes (LFT Art. 110).

    `dias_cotizados` es `None` para asimilados: sin IMSS no hay crédito Infonavit que
    descontar por nómina.
    """
    ded: list[PartidaDeduccion] = []
    avisos: list[str] = []
    if v.infonavit and dias_cotizados is not None:
        imp = descuento_infonavit(v.infonavit, sbc, dias_cotizados, dias_naturales)
        if imp:
            ded.append(PartidaDeduccion("010", "D010", "CRÉDITO INFONAVIT", imp))
    if v.fonacot:
        tope = redondear(sueldo * TOPE_FONACOT)
        if v.fonacot > tope:
            avisos.append(
                f"{v.empleado_no}: Fonacot topado a 20 % del salario (Art. 110 fr. VII LFT)."
            )
        ded.append(PartidaDeduccion("011", "D011", "FONACOT", min(v.fonacot, tope)))
    if v.prestamo:
        ded.append(PartidaDeduccion("012", "D012", "PRÉSTAMO / ANTICIPO", v.prestamo))
        avisos.append(
            f"{v.empleado_no}: verifica el tope del Art. 110 fr. I LFT (30 % del excedente "
            "del salario mínimo) contra el saldo total del préstamo."
        )
    if v.pension:
        ded.append(
            PartidaDeduccion(
                "007",
                "D007",
                "PENSIÓN ALIMENTICIA",
                pension_alimenticia(v.pension, bruto, neto_de_ley),
            )
        )
    return ded, avisos
