"""
Tablas de cuotas obrero-patronales IMSS e Infonavit, versionadas por año.

Este modulo NO calcula cuotas (eso es F1-03): entrega las tablas, el selector
del tramo de CEAV y los constructores de los dos ramos cuya tasa patronal no
es una tasa de ley fija.

Fuentes por estructura, con su articulo, en cada docstring. Referencia
documental: knowledge_base/nomina/22_cuotas_imss_infonavit_2026.md.

LA BASE IMPORTA TANTO COMO EL PORCENTAJE
----------------------------------------
Casi todo se calcula sobre el SBC, pero la cuota fija de Enfermedades y
Maternidad va sobre la **UMA** (Art. 106 fr. I LSS) y el excedente de EyM sobre
**SBC menos 3 UMA** (fr. II). Por eso cada ramo declara su base en un enum: un
motor que asuma SBC para todo da un numero plausible y equivocado.

DOS RAMOS NO CABEN EN UNA TASA ESCALAR
--------------------------------------
- **Riesgos de Trabajo**: la prima es de la empresa (0.50000%-15.00000%,
  Art. 72 LSS), se autodetermina cada febrero por siniestralidad. No es una
  tasa de ley: se inyecta con `ramo_riesgos_trabajo(prima)`.
- **CEAV patronal**: es una tabla por tramo de SBC en multiplos de UMA
  (transitorio de la reforma DOF 16-12-2020). Se resuelve con
  `ramo_ceav_patronal(sbc, fecha, zona)`.

Los dos quedan FUERA de `CUOTAS_RAMOS` a proposito. Si estuvieran dentro con
la tasa en `None`, un consumidor que itere la tabla multiplicando podria
saltarselos en silencio — y son las dos cuotas patronales mas caras del recibo.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum

from app.constants import ZonaSalarioMinimo, salario_minimo_vigente, uma_vigente
from app.exceptions import FiscalValidationError


class BaseCuota(str, Enum):
    """Sobre que se aplica el porcentaje de un ramo."""

    SBC = "sbc"
    UMA = "uma"
    EXCEDENTE_3_UMA = "excedente_3_uma"  # SBC - 3 UMA, solo si SBC > 3 UMA


class PeriodicidadCuota(str, Enum):
    """Cada cuando se entera el ramo (Art. 39 LSS)."""

    MENSUAL = "mensual"
    BIMESTRAL = "bimestral"


@dataclass(frozen=True)
class Ramo:
    """Un ramo de aseguramiento con sus dos cuotas, su base y su fundamento."""

    clave: str
    nombre: str
    patron: Decimal
    obrero: Decimal
    base: BaseCuota
    periodicidad: PeriodicidadCuota
    fundamento: str


# Ramos con tasa de ley escalar. RT y CEAV patronal NO estan aqui (ver el
# docstring del modulo). Fuente: LSS y Ley del Infonavit, articulos citados.
CUOTAS_RAMOS: dict[int, tuple[Ramo, ...]] = {
    2026: (
        Ramo(
            "eym_cuota_fija", "Enfermedades y Maternidad — cuota fija",
            Decimal("0.2040"), Decimal("0"), BaseCuota.UMA,
            PeriodicidadCuota.MENSUAL, "Art. 106 fr. I LSS",
        ),
        Ramo(
            "eym_excedente", "Enfermedades y Maternidad — excedente sobre 3 UMA",
            Decimal("0.0110"), Decimal("0.0040"), BaseCuota.EXCEDENTE_3_UMA,
            PeriodicidadCuota.MENSUAL, "Art. 106 fr. II LSS",
        ),
        Ramo(
            "eym_prestaciones_dinero", "Enfermedades y Maternidad — prestaciones en dinero",
            Decimal("0.0070"), Decimal("0.0025"), BaseCuota.SBC,
            PeriodicidadCuota.MENSUAL, "Art. 107 LSS",
        ),
        Ramo(
            "eym_gastos_medicos_pensionados",
            "Enfermedades y Maternidad — gastos médicos de pensionados",
            Decimal("0.0105"), Decimal("0.00375"), BaseCuota.SBC,
            PeriodicidadCuota.MENSUAL, "Art. 25 LSS",
        ),
        Ramo(
            "invalidez_vida", "Invalidez y Vida",
            Decimal("0.0175"), Decimal("0.00625"), BaseCuota.SBC,
            PeriodicidadCuota.MENSUAL, "Art. 147 LSS",
        ),
        Ramo(
            "guarderias", "Guarderías y Prestaciones Sociales",
            Decimal("0.0100"), Decimal("0"), BaseCuota.SBC,
            PeriodicidadCuota.MENSUAL, "Art. 211 LSS",
        ),
        Ramo(
            "retiro", "Retiro",
            Decimal("0.0200"), Decimal("0"), BaseCuota.SBC,
            PeriodicidadCuota.BIMESTRAL, "Art. 168 fr. I LSS",
        ),
        Ramo(
            "infonavit", "Infonavit — aportación patronal",
            Decimal("0.0500"), Decimal("0"), BaseCuota.SBC,
            PeriodicidadCuota.BIMESTRAL, "Art. 29 fr. II Ley del Infonavit",
        ),
    ),
}

# Cuota OBRERA de CEAV: es un escalar, a diferencia de la patronal.
CEAV_OBRERO: dict[int, Decimal] = {2026: Decimal("0.01125")}

# Prima media por clase de riesgo (Art. 73 LSS). Aplica a empresa nueva.
PRIMA_MEDIA_CLASE: dict[int, dict[int, Decimal]] = {
    2026: {
        1: Decimal("0.0054355"),
        2: Decimal("0.0113065"),
        3: Decimal("0.0259840"),
        4: Decimal("0.0465325"),
        5: Decimal("0.0758875"),
    },
}

# Rango legal de la prima de Riesgos de Trabajo (Art. 72 LSS).
PRIMA_RT_MINIMA = Decimal("0.005")
PRIMA_RT_MAXIMA = Decimal("0.15")


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


def _del_anio(tabla: dict, fecha: date, que: str):
    valor = tabla.get(fecha.year)
    if valor is None:
        disponibles = ", ".join(str(a) for a in sorted(tabla))
        raise FiscalValidationError(
            f"No hay {que} cargado para {fecha.year}. Años disponibles: {disponibles}. "
            f"Para agregar un año hay que citar la fuente oficial correspondiente."
        )
    return valor


def cuotas_ramos_vigentes(fecha: date) -> tuple[Ramo, ...]:
    """Ramos con tasa de ley vigentes en `fecha`. No incluye RT ni CEAV patronal."""
    return _del_anio(CUOTAS_RAMOS, fecha, "tabla de ramos del IMSS")


def ramo_riesgos_trabajo(prima: Decimal, fecha: date) -> Ramo:
    """
    Construye el ramo de Riesgos de Trabajo con la prima de la empresa.

    La prima no es una tasa de ley: la empresa la autodetermina cada febrero
    con su siniestralidad (Art. 74 LSS) y para empresa nueva es la prima media
    de su clase (`PRIMA_MEDIA_CLASE`). Por eso se inyecta.

    Raises:
        FiscalValidationError: si la prima cae fuera del rango del Art. 72 LSS
            (0.50000% a 15.00000%).
    """
    _del_anio(CUOTAS_RAMOS, fecha, "tabla de ramos del IMSS")
    if not PRIMA_RT_MINIMA <= prima <= PRIMA_RT_MAXIMA:
        raise FiscalValidationError(
            f"La prima de Riesgos de Trabajo {prima} está fuera del rango legal "
            f"{PRIMA_RT_MINIMA}–{PRIMA_RT_MAXIMA} (Art. 72 LSS)."
        )
    return Ramo(
        "riesgos_trabajo", "Riesgos de Trabajo", prima, Decimal("0"),
        BaseCuota.SBC, PeriodicidadCuota.MENSUAL, "Arts. 71-74 LSS",
    )


def prima_media_clase(clase: int, fecha: date) -> Decimal:
    """Prima media de la clase de riesgo (Art. 73 LSS). Clases I a V."""
    primas = _del_anio(PRIMA_MEDIA_CLASE, fecha, "tabla de primas medias")
    prima = primas.get(clase)
    if prima is None:
        raise FiscalValidationError(
            f"Clase de riesgo inválida: {clase}. Válidas: 1 a 5 (Art. 73 LSS)."
        )
    return prima


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
    tramos = _del_anio(CEAV_PATRONAL, fecha, "tabla de CEAV patronal")
    salario_minimo = salario_minimo_vigente(fecha, zona)

    if sbc < salario_minimo:
        raise FiscalValidationError(
            f"El SBC {sbc} es menor al salario mínimo de la zona {zona} en "
            f"{fecha.isoformat()} ({salario_minimo}). El SBC se acota al piso del "
            f"Art. 28 LSS antes de calcular cuotas."
        )
    if sbc == salario_minimo:
        return _del_anio(
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
        _del_anio(CEAV_OBRERO, fecha, "cuota obrera de CEAV"),
        BaseCuota.SBC, PeriodicidadCuota.BIMESTRAL,
        "Art. 168 fr. II LSS + transitorio del Decreto DOF 16-12-2020",
    )
