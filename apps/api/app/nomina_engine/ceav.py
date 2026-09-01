"""
Cesantia en Edad Avanzada y Vejez: tabla patronal por tramo.

Vive aparte de `tablas_imss.py` porque su tasa patronal no es un escalar sino
una tabla por tramo de SBC, y porque el predicado del trabajador de salario
minimo que necesita lo comparte con el Art. 36 LSS.

Fuente: articulo transitorio del Decreto que reforma la LSS y la Ley del SAR,
DOF 16-12-2020, que contiene la tabla de la transicion 2023-2030.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.constants import ZonaSalarioMinimo, salario_minimo_vigente, uma_vigente
from app.exceptions import FiscalValidationError
from app.nomina_engine.tablas_imss import (
    BaseCuota,
    PeriodicidadCuota,
    Ramo,
    tabla_del_anio,
)

# Cuota OBRERA de CEAV: es un escalar, a diferencia de la patronal.
CEAV_OBRERO: dict[int, Decimal] = {2026: Decimal("0.01125")}


@dataclass(frozen=True)
class TramoCEAV:
    """
    Un tramo de la tabla de CEAV patronal.

    `limite_superior_uma` es el tope del tramo en multiplos de UMA. El primer
    tramo es la excepcion: aplica al SBC de exactamente 1 salario minimo, no a
    un rango de UMA (ver `ceav_patronal`).
    """

    limite_superior_uma: Decimal | None
    tasa: Decimal
    etiqueta: str


# Tabla de CEAV patronal por año. Es el cuarto escalon de la transicion
# 2023-2030 (llega a 11.875% en 2030).
# Fuente: articulo transitorio del Decreto que reforma la LSS y la Ley del SAR,
# DOF 16-12-2020. Consumidor documentado en knowledge_base/nomina/22.
# MANTENIMIENTO: cada enero se agrega el renglon del año nuevo citando el mismo
# transitorio. Los años viejos NO se borran: un recalculo de un ejercicio
# pasado tiene que seguir cuadrando.
CEAV_PATRONAL: dict[int, tuple[TramoCEAV, ...]] = {
    2026: (
        TramoCEAV(Decimal("1.50"), Decimal("0.03676"), "1.01 SM a 1.50 UMA"),
        TramoCEAV(Decimal("2.00"), Decimal("0.04851"), "1.51 a 2.00 UMA"),
        TramoCEAV(Decimal("2.50"), Decimal("0.05556"), "2.01 a 2.50 UMA"),
        TramoCEAV(Decimal("3.00"), Decimal("0.06026"), "2.51 a 3.00 UMA"),
        TramoCEAV(Decimal("3.50"), Decimal("0.06361"), "3.01 a 3.50 UMA"),
        TramoCEAV(Decimal("4.00"), Decimal("0.06613"), "3.51 a 4.00 UMA"),
        TramoCEAV(None, Decimal("0.07513"), "4.01 UMA en adelante"),
    ),
}

# Tasa del trabajador con SBC de exactamente 1 salario minimo.
CEAV_PATRONAL_SALARIO_MINIMO: dict[int, Decimal] = {2026: Decimal("0.03150")}


def es_trabajador_de_salario_minimo(
    sbc: Decimal, fecha: date, zona: ZonaSalarioMinimo
) -> bool:
    """
    Si el SBC corresponde a un trabajador de salario minimo.

    Predicado UNICO de todo el motor, a proposito: la misma pregunta legal
    gobierna el renglon de 3.150% de la tabla de CEAV y la absorcion de la
    cuota obrera por el patron (Art. 36 LSS). Si se contestara en dos archivos,
    la respuesta de la contadora se aplicaria en uno y no en el otro.

    DECISION PROVISIONAL (docs/decisiones-nomina.md D4): se lee "1.00 SM" como
    **SBC igual al salario minimo**. La otra lectura posible —trabajador que
    percibe el salario minimo, con SBC integrado por encima— cambia el
    resultado para todos los trabajadores de salario minimo del pais. Con la
    lectura literal, el supuesto solo se alcanza cuando el clamp del Art. 28
    subio el SBC al piso.
    """
    return sbc == salario_minimo_vigente(fecha, zona)


def ceav_patronal(sbc: Decimal, fecha: date, zona: ZonaSalarioMinimo) -> Decimal:
    """
    Tasa patronal de CEAV para un SBC, en una fecha y una zona.

    La `zona` es load-bearing, no cosmetica: el primer tramo de la tabla es el
    trabajador de 1 salario minimo, y el salario minimo depende del area
    geografica (Art. 28 LSS). En la ZLFN 1 SM son $440.87, que en 2026 son 3.76
    UMA — un tramo completamente distinto del que ocupa el minimo general.

    Los tramos se evaluan en multiplos de la UMA VIGENTE, asi que en enero se
    miden contra la UMA del año anterior: un mismo SBC puede cambiar de tramo
    el 1 de febrero sin que el salario haya cambiado.

    ORDEN DE BUSQUEDA: primero la igualdad exacta con 1 SM, despues los tramos
    en UMA. No es opcional — los limites no son monotonos. El salario minimo
    general de 2026 equivale a ~2.69 UMA, o sea que cae por encima de los
    tramos "1.01 SM a 1.50 UMA", "1.51 a 2.00 UMA" y "2.01 a 2.50 UMA". Una
    busqueda ingenua por limite superior devolveria el tramo equivocado.

    DECISION PROVISIONAL (docs/decisiones-nomina.md D4): se aplica la tabla
    literal. Los tramos que quedan por debajo del salario minimo son
    inalcanzables en zona general y se dejan sin logica especial, a la espera
    de confirmar contra la emision del IMSS.

    Raises:
        FiscalValidationError: si el SBC es menor al salario minimo de la zona
            (el clamp del Art. 28 LSS es responsabilidad de F1-02: aqui no se
            corrige en silencio) o si el año no tiene tabla cargada.
    """
    tramos = tabla_del_anio(CEAV_PATRONAL, fecha, "tabla de CEAV patronal")
    salario_minimo = salario_minimo_vigente(fecha, zona)

    if sbc < salario_minimo:
        raise FiscalValidationError(
            f"El SBC {sbc} es menor al salario mínimo de la zona {zona} en "
            f"{fecha.isoformat()} ({salario_minimo}). El SBC se acota al piso del "
            f"Art. 28 LSS antes de calcular cuotas."
        )
    if es_trabajador_de_salario_minimo(sbc, fecha, zona):
        return tabla_del_anio(
            CEAV_PATRONAL_SALARIO_MINIMO, fecha, "tasa de CEAV del salario mínimo"
        )

    veces_uma = sbc / uma_vigente(fecha)
    for tramo in tramos:
        if tramo.limite_superior_uma is None or veces_uma <= tramo.limite_superior_uma:
            return tramo.tasa
    raise FiscalValidationError(f"No se encontró tramo de CEAV para el SBC {sbc}.")


def ramo_ceav_patronal(sbc: Decimal, fecha: date, zona: ZonaSalarioMinimo) -> Ramo:
    """Construye el ramo de CEAV con la tasa patronal del tramo que le toca al SBC."""
    return Ramo(
        "ceav", "Cesantía en Edad Avanzada y Vejez",
        ceav_patronal(sbc, fecha, zona),
        tabla_del_anio(CEAV_OBRERO, fecha, "cuota obrera de CEAV"),
        BaseCuota.SBC, PeriodicidadCuota.BIMESTRAL,
        "Art. 168 fr. II LSS + transitorio del Decreto DOF 16-12-2020",
    )
