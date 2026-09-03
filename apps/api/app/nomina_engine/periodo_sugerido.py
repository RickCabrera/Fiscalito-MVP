"""
Que periodo proponer, segun la periodicidad de pago del patron. (O-03)

POR QUE ESTO TIENE QUE EXISTIR, Y POR QUE EN EL BACKEND
-------------------------------------------------------
Hasta O-03 la app proponia **siempre una quincena**: `conPeriodoAlDia`
(`apps/store/src/services/carteraFirestore.ts`) copiaba el `periodo_sugerido`
del cliente `demo` a *todos*, sin mirar su `clave_periodicidad`. Su propio
docstring lo advertia: *"el dia que se abran las otras claves esta es la puerta
que queda abierta"*.

O-03 abre exactamente esas claves. Sin esto, elegir **Mensual** dejaba a la
empresa con una quincena propuesta y —con la guarda nueva de
`duracion_periodo`— el motor rechazando el calculo: **un selector que rompe la
app en dos de sus tres opciones**, con la culpa aparentando ser del motor.

Vive en Python y no en TypeScript por la misma razon que `CarteraContext` ya
declara para no replicar `quincena(hoy)`: de la `fecha_pago` que sale de aqui
dependen la UMA, el salario minimo, la tarifa del Anexo 8 y el transitorio de
enero del subsidio (§D18). Dos implementaciones de esa regla son dos verdades
sobre con que valores se calcula la nomina.

SIEMPRE EL ULTIMO PERIODO **TERMINADO**
---------------------------------------
Y no el que esta en curso, por la razon que `demo_nomina.quincena` ya dejo
escrita: `cerrar_periodo()` marca falta **todo dia laborable sin checada**,
incluidos los que todavia no llegan. Cerrar el periodo en curso el dia 2 daria
faltas por los dias que faltan del mes.

LO QUE PRODUCE SIEMPRE CASA CON `duracion_periodo`
--------------------------------------------------
Y hay un test que lo recorre dia por dia durante un año para cada clave. Si no
casara, la app propondria un periodo que su propio motor rechaza — que es
justo el callejon que esto viene a evitar.
"""

from __future__ import annotations

from datetime import date, timedelta

from app.exceptions import FiscalValidationError
from app.schemas.asistencia import Periodo

# Las cuatro claves de `c_PeriodicidadPago` con tarifa publicada. Las demas las
# rechaza `tarifa_por_periodicidad` con su propio motivo (§D10), y proponerles
# un periodo seria ofrecer un calculo que despues no se puede hacer.
CLAVES_CON_PERIODO = ("01", "02", "04", "05")


def _quincena(hoy: date) -> Periodo:
    """
    La ultima quincena **ya terminada**.

    Es la implementacion que vivia en `demo_nomina.quincena`, movida aqui: ese
    modulo esta marcado "se borra en F2" y esta regla es de produccion. Aquel
    delega en esta para que siga habiendo una sola.

    OJO CON EL BORDE: sembrar el dia 15 y demostrar el 16 da **dos quincenas
    distintas**, y el panel sale vacio. Sembrar y demostrar el mismo dia.

    Los dias del periodo salen de las fechas, nunca de una constante: del 16 al
    31 son **16 dias, no 15**.
    """
    if hoy.day > 15:
        return Periodo(inicio=hoy.replace(day=1), fin=hoy.replace(day=15))
    fin = hoy.replace(day=1) - timedelta(days=1)
    return Periodo(inicio=fin.replace(day=16), fin=fin)


def _semana(hoy: date) -> Periodo:
    """
    La ultima semana **lunes a domingo** ya terminada.

    Lunes a domingo y no "los ultimos siete dias": una semana de nomina es un
    periodo de calendario, y `cerrar_periodo` cuenta dias laborables con
    `weekday()`. Un periodo movil daria una cantidad distinta de fines de
    semana segun el dia en que se corriera.
    """
    domingo = hoy - timedelta(days=hoy.weekday() + 1)
    return Periodo(inicio=domingo - timedelta(days=6), fin=domingo)


def _mes(hoy: date) -> Periodo:
    """El ultimo mes natural completo."""
    ultimo = hoy.replace(day=1) - timedelta(days=1)
    return Periodo(inicio=ultimo.replace(day=1), fin=ultimo)


def _dia(hoy: date) -> Periodo:
    """Ayer. Hoy todavia no termina."""
    ayer = hoy - timedelta(days=1)
    return Periodo(inicio=ayer, fin=ayer)


_POR_CLAVE = {"01": _dia, "02": _semana, "04": _quincena, "05": _mes}


def periodo_sugerido(clave_periodicidad: str, hoy: date) -> Periodo:
    """
    El ultimo periodo terminado para esa periodicidad.

    Args:
        clave_periodicidad: clave de `c_PeriodicidadPago`.
        hoy: la fecha desde la que se mira. Explicita y sin default: un
            `date.today()` implicito haria que el mismo cálculo diera
            resultados distintos segun cuando se corriera, y es exactamente el
            tipo de cosa que hace irreproducible una nomina.

    Raises:
        FiscalValidationError: si la clave no tiene periodo que proponer. Se
            lista el motivo de la clave concreta en `tarifa_por_periodicidad`;
            aqui se dice lo que le importa a quien pregunta.
    """
    calcular = _POR_CLAVE.get(clave_periodicidad)
    if calcular is None:
        raise FiscalValidationError(
            f"No hay periodo que proponer para la periodicidad {clave_periodicidad!r}. "
            f"Las que se pueden calcular son: {', '.join(CLAVES_CON_PERIODO)} "
            f"(diaria, semanal, quincenal y mensual). Las demás no tienen tarifa de "
            f"ISR publicada o no son periodos — ver docs/decisiones-nomina.md §D10."
        )
    return calcular(hoy)
