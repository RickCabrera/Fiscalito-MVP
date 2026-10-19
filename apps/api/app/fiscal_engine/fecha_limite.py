"""
Fecha límite del pago mensual y días inhábiles del CFF (P3-02). Separado de `actualizacion.py`
(O11), que lo reexporta.

FUENTES: Art. 12 CFF (días inhábiles y prórroga al siguiente día hábil); Arts. 96 y 106 LISR
y 5o.-D LIVA (día 17 del mes siguiente).
"""

from __future__ import annotations

from datetime import date, timedelta


def _n_esimo_lunes(anio: int, mes: int, n: int) -> date:
    primero = date(anio, mes, 1)
    return primero + timedelta(days=(-primero.weekday()) % 7 + 7 * (n - 1))


def dias_inhabiles_cff(anio: int) -> frozenset[date]:
    """
    Días inhábiles del Art. 12 CFF (primer párrafo), además de sábados y domingos.

    1o. de enero; primer lunes de febrero; tercer lunes de marzo; 1o. y 5 de mayo; 16 de
    septiembre; tercer lunes de noviembre; 25 de diciembre. El 1o. de diciembre "de cada 6
    años, cuando corresponda a la transmisión del Poder Ejecutivo" no se incluye: la próxima
    ocurrencia es 2030 y la fecha de transmisión cambió por reforma constitucional (FUENTE
    POR CONFIRMAR). Los periodos vacacionales que el SAT declara inhábiles por regla de la RMF
    tampoco se incluyen: dependen de cada año.
    """
    return frozenset({
        date(anio, 1, 1), _n_esimo_lunes(anio, 2, 1), _n_esimo_lunes(anio, 3, 3),
        date(anio, 5, 1), date(anio, 5, 5), date(anio, 9, 16), _n_esimo_lunes(anio, 11, 3),
        date(anio, 12, 25),
    })


def siguiente_dia_habil(dia: date) -> date:
    """El mismo día si es hábil; si no, el siguiente hábil (Art. 12 CFF, cuarto párrafo)."""
    while dia.weekday() >= 5 or dia in dias_inhabiles_cff(dia.year):
        dia += timedelta(days=1)
    return dia


def fecha_limite_mensual(anio: int, mes: int) -> date:
    """
    Día en que debió pagarse una contribución mensual del periodo (anio, mes).

    El día 17 del mes inmediato posterior (Arts. 96 y 106 LISR, 5-D LIVA), corrido al
    siguiente día hábil si es inhábil (Art. 12 CFF). La prórroga por el sexto dígito del RFC
    NO se aplica aquí: es un beneficio de decreto que P3-10 incorpora al calendario; hasta
    entonces la fecha límite se puede capturar a mano en el resumen.
    """
    siguiente = (anio + 1, 1) if mes == 12 else (anio, mes + 1)
    return siguiente_dia_habil(date(siguiente[0], siguiente[1], 17))
