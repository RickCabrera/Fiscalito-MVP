"""
Criterios de nómina del despacho, configurables por cliente. (P4, DP-3)

Las preguntas §D26, §D27 y §D28 de `docs/decisiones-nomina.md` no tienen una
respuesta legal única: dependen del criterio de la contadora. Aquí dejan de ser
bloqueos o constantes escondidas y pasan a ser **opciones por cliente con un
default documentado**. Cada opción lleva su explicación, que la ficha del
cliente pinta en el bloque "Criterios de nómina".

EL MOTOR NO ELIGE EN SILENCIO
-----------------------------
El resultado de cada cálculo guarda los criterios con los que se hizo
(`NominaPeriodo.criterios`), así que una nómina vieja se puede explicar aunque
el cliente haya cambiado sus criterios después.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from typing import Any

from app.exceptions import FiscalValidationError

# ── Opciones con su explicación ─────────────────────────────────────────────

OPCIONES: dict[str, dict[str, str]] = {
    # §D26 — periodo PARCIAL de un alta o una baja a mitad de periodo.
    "parcial": {
        "tarifa_proporcional": (
            "Tarifa proporcional a los días (DEFAULT). Se aplica la tarifa del Art. 96 "
            "derivada a los días que el trabajador estuvo en el periodo (diaria del "
            "Anexo 8 x días). Es la opción conservadora: con 8 días de sueldo contra la "
            "tarifa quincenal completa el ingreso cae en renglones más bajos y el ISR "
            "sale subestimado —el error que la guarda de duración vino a cerrar—, y el "
            "patrón responde solidariamente por lo no retenido (Art. 26 fr. I CFF). "
            "Retener de más se corrige en el ajuste anual (Art. 97 LISR)."
        ),
        "tarifa_periodo": (
            "Tarifa del periodo sobre lo devengado. Se aplica la tarifa completa de la "
            "periodicidad (p. ej. quincenal) a lo que se pagó en los días parciales. Es "
            "lo que hacía la app antes de O-03; retiene menos."
        ),
    },
    # §D27 — la quincena de 13, 14 o 16 días.
    "febrero": {
        "quince_siempre": (
            "Pagar 15 días por quincena siempre (DEFAULT). Es la práctica mexicana "
            "habitual: la quincena vale 15 días de salario aunque el periodo natural "
            "tenga 13, 14 o 16. Las cuotas del IMSS y el subsidio siguen contando los "
            "días naturales (Art. 31 LSS)."
        ),
        "dias_calendario": (
            "Días calendario. Se pagan los días naturales del periodo: 13 en la segunda "
            "quincena de febrero, 16 en la de un mes de 31."
        ),
    },
    # §D28 — piso de prestaciones del patrón contra la ficha del empleado.
    "prestaciones": {
        "mayor": (
            "El mayor de los dos (DEFAULT). La política del patrón es un piso: si la "
            "ficha del empleado tiene más días negociados, se respetan; si tiene menos, "
            "manda el patrón (Arts. 33 y 56 LFT)."
        ),
        "ficha": (
            "Manda la ficha del empleado. Cambiar las prestaciones del patrón no "
            "propaga a los empleados ya dados de alta."
        ),
    },
    # Art. 174 RLISR — opción del retenedor para aguinaldo, PTU, primas.
    "isr_extraordinario": {
        "art_96": (
            "Art. 96 LISR (DEFAULT). La parte gravada se suma al ingreso del mes y se "
            "retiene la diferencia de la tarifa mensual. Es el procedimiento de la ley."
        ),
        "art_174": (
            "Art. 174 RLISR. Procedimiento opcional del Reglamento: la remuneración se "
            "anualiza (÷365 x 30.4), se calcula una tasa efectiva y se aplica a la "
            "parte gravada. Suele retener menos."
        ),
    },
    # Lo que se hace con el excedente del tope de PTU (Art. 127 LFT, reforma 2021).
    "ptu_remanente": {
        "no_se_reparte": (
            "No se reparte (DEFAULT). Lo que excede el tope de cada trabajador no se le "
            "entrega y se reporta como remanente. La LFT no ordena redistribuirlo. "
            "FUENTE POR CONFIRMAR con la contadora."
        ),
        "sumar_siguiente_ejercicio": (
            "Sumar al ejercicio siguiente. Lo que excede los topes se reporta para sumarlo a "
            "la utilidad repartible del año siguiente (criterio IDC, por analogía con el "
            "Art. 122 LFT). FUENTE POR CONFIRMAR."
        ),
        "redistribuir": (
            "Redistribuir entre quienes no llegaron a su tope, en proporción a lo que "
            "les tocó, hasta agotar el remanente o los topes."
        ),
    },
}


@dataclass(frozen=True)
class CriteriosNomina:
    """Los criterios de un cliente. Los defaults son los documentados arriba."""

    parcial: str = "tarifa_proporcional"
    febrero: str = "quince_siempre"
    prestaciones: str = "mayor"
    isr_extraordinario: str = "art_96"
    ptu_remanente: str = "no_se_reparte"

    def __post_init__(self) -> None:
        for campo in fields(self):
            valor = getattr(self, campo.name)
            validas = OPCIONES[campo.name]
            if valor not in validas:
                raise FiscalValidationError(
                    f"Criterio {campo.name}={valor!r} inválido. Opciones: {', '.join(validas)}."
                )

    def como_dict(self) -> dict[str, str]:
        return asdict(self)


def criterios_de(datos: dict[str, Any] | None) -> CriteriosNomina:
    """Los criterios guardados en la ficha; lo que falte toma su default."""
    if not datos:
        return CriteriosNomina()
    conocidos = {f.name for f in fields(CriteriosNomina)}
    return CriteriosNomina(**{k: v for k, v in datos.items() if k in conocidos})


# Lo que el criterio "mayor" vs "ficha" resuelve (§D28).
def prestacion_efectiva(patron: Any, ficha: Any, criterio: str) -> Any:
    """`max(patrón, ficha)` con "mayor"; la ficha con "ficha"."""
    if criterio == "ficha":
        return ficha
    return max(patron, ficha)
