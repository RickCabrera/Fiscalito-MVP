"""
Dias habiles para plazos laborales.

Contiene UNICAMENTE los dias de descanso obligatorio del **Art. 74 LFT** y el
conteo de dias habiles. No conoce obligaciones, ni el dia 17, ni ninguna fecha
fiscal: `calendario_laboral.py` (F1-06) consume este modulo, no lo reimplementa.

NO ES EL CALENDARIO DEL SAT
---------------------------
`fiscal_engine/calendario.py` tiene su propia nocion de dia habil para el dia
17 y el sexto digito del RFC. Son dos calendarios distintos que se ven iguales
y NO deben fusionarse: el del SAT corre el vencimiento por el sexto digito, y
el del IMSS lo corre por viernes o dia inhabil salvo para los avisos
afiliatorios (RACERF Art. 3).

ADVERTENCIA SOBRE "DIA HABIL"
-----------------------------
Este modulo usa los descansos obligatorios del **Art. 74 LFT**. El IMSS publica
ademas su propio acuerdo anual de dias inhabiles, que incluye sus periodos
vacacionales y **no coincide** con el Art. 74. Mientras ese acuerdo no este en
el repo con su fuente, toda fecha limite calculada aqui es una **estimacion
conservadora**, no una fecha legal cierta. Ver `docs/nocturno-log.md`.

QUE QUEDA FUERA, A PROPOSITO
-----------------------------
- **Art. 74 fr. IX — jornada electoral.** Depende del calendario del INE. Se
  omite porque el error tiene direccion: marcar de mas un dia como inhabil
  CORRE el vencimiento hacia adelante, y presentar tarde un aviso afiliatorio
  cuesta de 20 a 350 UMA (Art. 304-B LSS). Contar de menos es lo conservador.
- **Art. 74 fr. VII — transmision del Poder Ejecutivo cada seis años.** La
  fraccion existe, pero no se incluye sin poder citar el DOF del texto vigente
  (la transmision se movio de diciembre a octubre y la publicacion no esta
  verificada en el repo). No afecta ningun calculo de 2026; la proxima
  ocurrencia es 2030.
"""

from __future__ import annotations

from datetime import date, timedelta

_LUNES = 0


def _n_esimo_lunes(anio: int, mes: int, n: int) -> date:
    """N-esimo lunes de un mes (n=1 es el primero)."""
    primero = date(anio, mes, 1)
    dias_al_lunes = (_LUNES - primero.weekday()) % 7
    return primero + timedelta(days=dias_al_lunes + 7 * (n - 1))


def descansos_obligatorios(anio: int) -> frozenset[date]:
    """
    Dias de descanso obligatorio del Art. 74 LFT para un año.

    Fracciones incluidas: I (1 de enero), II (primer lunes de febrero,
    conmemoracion del 5 de febrero), III (tercer lunes de marzo, conmemoracion
    del 21 de marzo), IV (1 de mayo), V (16 de septiembre), VI (tercer lunes de
    noviembre, conmemoracion del 20 de noviembre) y VIII (25 de diciembre).

    Las fracciones VII y IX quedan fuera; ver el docstring del modulo.
    """
    return frozenset(
        {
            date(anio, 1, 1),
            _n_esimo_lunes(anio, 2, 1),
            _n_esimo_lunes(anio, 3, 3),
            date(anio, 5, 1),
            date(anio, 9, 16),
            _n_esimo_lunes(anio, 11, 3),
            date(anio, 12, 25),
        }
    )


def es_habil(dia: date) -> bool:
    """Un dia es habil si no es sabado, domingo ni descanso obligatorio."""
    return dia.weekday() < 5 and dia not in descansos_obligatorios(dia.year)


def sumar_dias_habiles(inicio: date, dias: int) -> date:
    """
    Fecha que resulta de contar `dias` dias habiles DESPUES de `inicio`.

    El dia de partida no cuenta: `sumar_dias_habiles(lunes, 1)` es el martes
    siguiente (si es habil). Es la forma en que la LSS expresa los plazos de
    los avisos: "dentro de los cinco dias habiles siguientes".
    """
    if dias < 0:
        raise ValueError("Los días hábiles a sumar no pueden ser negativos")
    actual = inicio
    contados = 0
    while contados < dias:
        actual += timedelta(days=1)
        if es_habil(actual):
            contados += 1
    return actual


def n_esimo_dia_habil_del_mes(anio: int, mes: int, n: int) -> date:
    """
    N-esimo dia habil de un mes (n=1 es el primero).

    Lo usan los plazos que corren "dentro de los primeros cinco dias habiles"
    de un mes, como el aviso bimestral de trabajadores de salario variable
    (Art. 34 fr. II LSS).
    """
    if n < 1:
        raise ValueError("El día hábil pedido debe ser 1 o mayor")
    actual = date(anio, mes, 1)
    contados = 1 if es_habil(actual) else 0
    while contados < n:
        actual += timedelta(days=1)
        if es_habil(actual):
            contados += 1
    return actual
