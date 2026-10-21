"""
Reglas del recibo del periodo que salieron de `periodo_completo.py` por el tope de 300
líneas. (P6-07)

FUENTES
-------
- **LISR Art. 96, quinto párrafo:** "Tratándose de honorarios a miembros de consejos
  directivos, de vigilancia, consultivos o de cualquier otra índole, así como de los
  honorarios a administradores, comisarios y gerentes generales, la retención y entero ...
  no podrá ser inferior la cantidad que resulte de aplicar la tasa máxima para aplicarse
  sobre el excedente del límite inferior que establece la tarifa contenida en el artículo
  152 de esta Ley, sobre su monto, salvo que exista, además, relación de trabajo con el
  retenedor, en cuyo caso, se procederá en los términos del párrafo segundo de este
  artículo." Por eso la retención mínima depende de dos marcas de la ficha
  (`es_consejero`, `consejero_es_trabajador`) y no del c_TipoRegimen: el 07 ("miembros de
  consejos") no cubre a administradores ni gerentes, y no dice si además hay relación de
  trabajo.
- **LFT Arts. 66 y 68 segundo párrafo:** tope diario y semanal del tiempo extra; ver
  `jornada.py`.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date

from app.exceptions import FiscalValidationError
from app.nomina_engine.jornada import (
    clasificar_horas_por_dia,
    tope_horas_extra_periodo,
    tope_horas_extra_semanal,
)
from app.nomina_engine.periodo_completo_tipos import EmpleadoNomina
from app.nomina_engine.variables_tipos import VariablesEmpleado
from app.redondeo import redondear


def avisos_consejero(e: EmpleadoNomina) -> list[str]:
    """Art. 96 quinto párrafo: la retención mínima depende de la ficha, no del régimen."""
    if e.es_consejero and e.consejero_es_trabajador:
        return [
            f"{e.empleado_no}: consejero que además es trabajador del retenedor: se retiene con "
            "la tarifa (Art. 96 LISR, quinto párrafo, remite al segundo), sin la tasa mínima."
        ]
    if e.tipo_regimen == "07" and not e.es_consejero and e.consejero_es_trabajador:
        return [
            f"{e.empleado_no}: régimen 07 marcado con relación de trabajo con el retenedor: se "
            "retiene con la tarifa (Art. 96 LISR, quinto párrafo, remite al segundo)."
        ]
    if e.tipo_regimen == "07" and not e.es_consejero:
        return [
            f"{e.empleado_no}: régimen 07 sin marcar en la ficha: se aplica la retención mínima "
            "del Art. 96 LISR, quinto párrafo (lectura conservadora). Si además tiene relación "
            "de trabajo con el retenedor, márcalo y se usará la tarifa."
        ]
    return []


def aplicar_tope_diario(
    v: VariablesEmpleado, dias_periodo: int, fin: date, no: str
) -> tuple[VariablesEmpleado, list[str]]:
    """Tope diario del Art. 66 LFT con las horas por día; sin ellas, sólo se avisa."""
    if not v.horas_extra_por_dia:
        if v.horas_dobles:
            return v, [
                f"{no}: horas dobles capturadas sin desglose diario: no se verificó el tope de "
                "3 horas diarias del Art. 66 LFT (sólo el semanal)."
            ]
        return v, []
    if len(v.horas_extra_por_dia) > dias_periodo:
        raise FiscalValidationError(
            f"{no}: {len(v.horas_extra_por_dia)} días de horas extra en un periodo de "
            f"{dias_periodo} días."
        )
    c = clasificar_horas_por_dia(v.horas_extra_por_dia, fin)
    v = replace(
        v, horas_dobles=c.dobles, horas_triples=v.horas_triples + c.triples, horas_extra_por_dia=()
    )
    return v, c.avisos(no)


def clasificar_horas_extra(
    v: VariablesEmpleado, dias_periodo: int, fin: date, no: str
) -> tuple[VariablesEmpleado, list[str]]:
    """
    Dobles y triples del periodo: tope diario (con desglose por día) y luego el tope semanal
    proporcional del Art. 66 LFT y Transitorio Cuarto (DOF 01-05-2026); lo que excede se paga
    triple (Art. 68 LFT, segundo párrafo) y va 100 % gravado.

    Es la ÚNICA clasificación: la usan el cálculo del recibo y el armado del CFDI de nómina,
    para que las horas por tipo cuadren siempre con el importe (revisor P6-07, B1).
    """
    v, avisos = aplicar_tope_diario(v, dias_periodo, fin, no)
    tope_dobles = redondear(tope_horas_extra_periodo(fin, dias_periodo))
    if v.horas_dobles > tope_dobles:
        exceso = v.horas_dobles - tope_dobles
        avisos.append(
            f"{no}: {v.horas_dobles} horas dobles exceden el tope de {tope_dobles} "
            f"del periodo ({tope_horas_extra_semanal(fin)} por semana, Art. 66 LFT); las "
            f"{exceso} de más se pagan triples (Art. 68) y van 100 % gravadas."
        )
        v = replace(v, horas_dobles=tope_dobles, horas_triples=v.horas_triples + exceso)
    return v, avisos
