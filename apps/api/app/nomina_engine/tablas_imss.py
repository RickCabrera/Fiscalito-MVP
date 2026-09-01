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
    se_reduce_por_ausentismo: bool = True
    """
    Si los dias de ausentismo e incapacidad reducen los dias cotizados de este
    ramo. Enfermedades y Maternidad NO se reduce (Art. 31 LSS, decision D3
    PROVISIONAL): un trabajador con 3 dias de ausencia cotiza 27 dias en los
    demas ramos y 30 en EyM. Un motor que use un solo contador de dias subcobra
    EyM en silencio, en el escenario mas comun que existe.
    """


# Ramos con tasa de ley escalar. RT y CEAV patronal NO estan aqui (ver el
# docstring del modulo). Fuente: LSS y Ley del Infonavit, articulos citados.
CUOTAS_RAMOS: dict[int, tuple[Ramo, ...]] = {
    2026: (
        Ramo(
            "eym_cuota_fija", "Enfermedades y Maternidad — cuota fija",
            Decimal("0.2040"), Decimal("0"), BaseCuota.UMA,
            PeriodicidadCuota.MENSUAL, "Art. 106 fr. I LSS",
            se_reduce_por_ausentismo=False,
        ),
        Ramo(
            "eym_excedente", "Enfermedades y Maternidad — excedente sobre 3 UMA",
            Decimal("0.0110"), Decimal("0.0040"), BaseCuota.EXCEDENTE_3_UMA,
            PeriodicidadCuota.MENSUAL, "Art. 106 fr. II LSS",
            se_reduce_por_ausentismo=False,
        ),
        Ramo(
            "eym_prestaciones_dinero", "Enfermedades y Maternidad — prestaciones en dinero",
            Decimal("0.0070"), Decimal("0.0025"), BaseCuota.SBC,
            PeriodicidadCuota.MENSUAL, "Art. 107 LSS",
            se_reduce_por_ausentismo=False,
        ),
        Ramo(
            "eym_gastos_medicos_pensionados",
            "Enfermedades y Maternidad — gastos médicos de pensionados",
            Decimal("0.0105"), Decimal("0.00375"), BaseCuota.SBC,
            PeriodicidadCuota.MENSUAL, "Art. 25 LSS",
            se_reduce_por_ausentismo=False,
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


def tabla_del_anio(tabla: dict, fecha: date, que: str):
    """
    Accesor por año con error explicito, compartido por el modulo de CEAV.

    Ningun diccionario versionado por año se indexa a pelo: un año sin fuente
    cargada tiene que decir que años hay y que se necesita para agregar uno.
    """
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
    return tabla_del_anio(CUOTAS_RAMOS, fecha, "tabla de ramos del IMSS")


def ramo_riesgos_trabajo(prima: Decimal, fecha: date) -> Ramo:
    """
    Construye el ramo de Riesgos de Trabajo con la prima de la empresa.

    La prima no es una tasa de ley: la empresa la autodetermina cada febrero
    con su siniestralidad (Art. 74 LSS) y para empresa nueva es la prima media
    de su clase (`PRIMA_MEDIA_CLASE`). Por eso se inyecta.

    La `fecha` no selecciona la prima —la trae el llamador— sino que valida
    que el año tenga tablas cargadas, para que construir un ramo de RT de un
    ejercicio sin fuente falle igual que pedir cualquier otro ramo.

    Raises:
        FiscalValidationError: si la prima cae fuera del rango del Art. 72 LSS
            (0.50000% a 15.00000%), o si el año no tiene tablas.
    """
    tabla_del_anio(CUOTAS_RAMOS, fecha, "tabla de ramos del IMSS")
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
    primas = tabla_del_anio(PRIMA_MEDIA_CLASE, fecha, "tabla de primas medias")
    prima = primas.get(clase)
    if prima is None:
        raise FiscalValidationError(
            f"Clase de riesgo inválida: {clase}. Válidas: 1 a 5 (Art. 73 LSS)."
        )
    return prima
