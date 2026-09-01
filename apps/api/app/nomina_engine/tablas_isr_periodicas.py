"""
Tarifas del ISR por periodicidad de pago (Anexo 8 RMF).

Fuente: Anexo 8 de la RMF 2026, publicado en el DOF el 28-12-2025.
Rubro A "Tarifas para el calculo del impuesto correspondiente a los ejercicios
2025 y 2026" y rubro B "Tarifas aplicables a retenciones", que incluye las
tarifas diaria, semanal, decenal, quincenal y mensual.
PDF oficial:
https://www.sat.gob.mx/minisitio/NormatividadRMFyRGCE/documentos2026/rmf/anexos/Anexo-8-RMF-2026_DOF-28122025.pdf

COMO SE CONSTRUYEN LAS TARIFAS PERIODICAS
-----------------------------------------
Las tarifas de periodos menores al mes no son transcripciones independientes:
el Anexo 8 las obtiene de la mensual con una regla exacta.

    diaria    = mensual / 30.4          -> ROUND_HALF_UP a 2 decimales
    periodica = diaria x dias_del_periodo
    limite_inferior[n] = limite_superior[n-1] + 0.01

El redondeo a la diaria ocurre ANTES de multiplicar por los dias. El camino
`mensual x dias / 30.4` da otro numero: para el segundo renglon quincenal
produce $3,537.09 cuando lo publicado es $3,537.15. Es el mismo problema de
orden de redondeo que `app.constants.uma_mensual_vigente` resolvio para la UMA.

El limite inferior TAMPOCO se deriva del limite inferior mensual: sale del
limite superior del renglon anterior mas un centavo. Derivarlo da $416.70 para
el segundo renglon quincenal, cuando lo publicado es $416.71.

AUTORIDAD
---------
La autoridad son los valores PUBLICADOS, que estan transcritos como literales
en `tests/nomina/test_tablas_isr_periodicas.py`. La generacion de este modulo
es una reproduccion validada contra ellos, no una fuente. Si en un ejercicio
futuro la tarifa publicada dejara de coincidir con la regla, ganan los
literales: se sustituye la generacion por transcripcion.

VIGENCIA
--------
Las tarifas del Anexo 8 rigen por **ejercicio calendario** (1-ene a 31-dic).
Es una vigencia distinta de la de la UMA, que corre del 1-feb al 31-ene. En
enero conviven las dos: tarifa del ejercicio nuevo y UMA del ejercicio
anterior.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.exceptions import FiscalValidationError
from app.redondeo import DOS_DECIMALES as _DOS_DECIMALES
from app.redondeo import redondear as _redondear

_DIAS_MES_FISCAL = Decimal("30.4")
INFINITO = Decimal("Infinity")


@dataclass(frozen=True)
class RenglonTarifa:
    """Un renglon de tarifa del Art. 96 LISR."""

    limite_inferior: Decimal
    limite_superior: Decimal
    cuota_fija: Decimal
    tasa_excedente: Decimal


# Tarifa mensual del Art. 96 LISR, ejercicio 2026.
# Transcrita del Anexo 8 (DOF 28-12-2025). Es la misma tabla que
# `fiscal_engine.tablas_isr.TABLA_ISR_MENSUAL`, aqui en Decimal porque
# nomina_engine no trabaja en float. `test_tablas_isr_periodicas.py` compara
# las dos renglon por renglon: si divergen, falla.
TARIFA_MENSUAL_2026: tuple[RenglonTarifa, ...] = (
    RenglonTarifa(Decimal("0.01"), Decimal("844.59"), Decimal("0.00"), Decimal("0.0192")),
    RenglonTarifa(Decimal("844.60"), Decimal("7168.51"), Decimal("16.22"), Decimal("0.0640")),
    RenglonTarifa(Decimal("7168.52"), Decimal("12598.02"), Decimal("420.95"), Decimal("0.1088")),
    RenglonTarifa(Decimal("12598.03"), Decimal("14644.64"), Decimal("1011.68"), Decimal("0.16")),
    RenglonTarifa(Decimal("14644.65"), Decimal("17533.64"), Decimal("1339.14"), Decimal("0.1792")),
    RenglonTarifa(Decimal("17533.65"), Decimal("35362.83"), Decimal("1856.84"), Decimal("0.2136")),
    RenglonTarifa(Decimal("35362.84"), Decimal("55736.68"), Decimal("5665.16"), Decimal("0.2352")),
    RenglonTarifa(Decimal("55736.69"), Decimal("106410.50"), Decimal("10457.09"), Decimal("0.30")),
    RenglonTarifa(
        Decimal("106410.51"), Decimal("141880.66"), Decimal("25659.23"), Decimal("0.32")
    ),
    RenglonTarifa(
        Decimal("141880.67"), Decimal("425641.99"), Decimal("37009.69"), Decimal("0.34")
    ),
    RenglonTarifa(Decimal("425642.00"), INFINITO, Decimal("133488.54"), Decimal("0.35")),
)


def _derivar_tarifa(
    mensual: tuple[RenglonTarifa, ...], dias: int
) -> tuple[RenglonTarifa, ...]:
    """
    Construye la tarifa de `dias` dias a partir de la mensual.

    Ver el docstring del modulo: se redondea la diaria y despues se multiplica
    por los dias; el limite inferior sale del superior anterior mas $0.01.
    """
    renglones: list[RenglonTarifa] = []
    limite_inferior = _DOS_DECIMALES
    for renglon in mensual:
        cuota = _redondear(renglon.cuota_fija / _DIAS_MES_FISCAL) * dias
        if renglon.limite_superior.is_infinite():
            limite_superior = INFINITO
        else:
            limite_superior = _redondear(renglon.limite_superior / _DIAS_MES_FISCAL) * dias
        renglones.append(
            RenglonTarifa(limite_inferior, limite_superior, cuota, renglon.tasa_excedente)
        )
        limite_inferior = limite_superior + _DOS_DECIMALES
    return tuple(renglones)


TARIFA_DIARIA_2026 = _derivar_tarifa(TARIFA_MENSUAL_2026, 1)
TARIFA_SEMANAL_2026 = _derivar_tarifa(TARIFA_MENSUAL_2026, 7)
TARIFA_QUINCENAL_2026 = _derivar_tarifa(TARIFA_MENSUAL_2026, 15)

# Tarifas por ejercicio y por clave de c_PeriodicidadPago (catalogo del SAT).
# 01 diaria, 02 semanal, 04 quincenal, 05 mensual.
TARIFAS_POR_EJERCICIO: dict[int, dict[str, tuple[RenglonTarifa, ...]]] = {
    2026: {
        "01": TARIFA_DIARIA_2026,
        "02": TARIFA_SEMANAL_2026,
        "04": TARIFA_QUINCENAL_2026,
        "05": TARIFA_MENSUAL_2026,
    },
}

# Claves de c_PeriodicidadPago que existen en el catalogo pero para las que
# este modulo NO entrega tarifa, con la razon. Se responde con un error
# explicito: publicar una tarifa que ninguna autoridad publico seria peor que
# fallar. Ver docs/decisiones-nomina.md D10.
PERIODICIDADES_SIN_TARIFA: dict[str, str] = {
    "03": (
        "catorcenal: el Anexo 8 no publica tarifa de 14 dias. La via (semanal x 2, "
        "diaria x 14, o el procedimiento del RLISR) esta pendiente de definir con la "
        "contadora; ver docs/decisiones-nomina.md D10"
    ),
    "10": (
        "decenal: el Anexo 8 si la publica, pero sus valores no se pudieron verificar "
        "contra una fuente publicada al construir este modulo. Agregarla es una linea "
        "en cuanto se transcriban sus 11 renglones con su cita; ver D10"
    ),
    "06": "bimestral: no es una periodicidad de pago de nomina con tarifa de retencion",
    "07": "unidad de obra: no es un periodo, no tiene tarifa",
    "08": "comision: no es un periodo, no tiene tarifa",
    "09": "precio alzado: no es un periodo, no tiene tarifa",
    "99": "otra periodicidad: sin tarifa determinable",
}


def tarifa_por_periodicidad(
    clave: str, fecha: date
) -> tuple[RenglonTarifa, ...]:
    """
    Tarifa del Anexo 8 para una clave de `c_PeriodicidadPago` en una fecha.

    La vigencia es por ejercicio calendario, no por la regla de febrero de la
    UMA. Decision D1 de docs/decisiones-nomina.md: se usan las tarifas
    publicadas por periodicidad, no el prorrateo de la mensual.

    Raises:
        FiscalValidationError: si el ejercicio no tiene tarifas cargadas, o si
            la clave no tiene tarifa publicada (catorcenal, decenal, y las
            claves que no son periodos).
    """
    del_ejercicio = TARIFAS_POR_EJERCICIO.get(fecha.year)
    if del_ejercicio is None:
        disponibles = ", ".join(str(a) for a in sorted(TARIFAS_POR_EJERCICIO))
        raise FiscalValidationError(
            f"No hay tarifas del Anexo 8 cargadas para el ejercicio {fecha.year}. "
            f"Ejercicios disponibles: {disponibles}. Para agregar uno hay que citar el "
            f"Anexo 8 de la RMF de ese año y su publicación en el DOF."
        )
    tarifa = del_ejercicio.get(clave)
    if tarifa is None:
        motivo = PERIODICIDADES_SIN_TARIFA.get(clave)
        if motivo is None:
            validas = ", ".join(sorted(del_ejercicio))
            raise FiscalValidationError(
                f"Clave de periodicidad desconocida: {clave!r}. Con tarifa: {validas}."
            )
        raise FiscalValidationError(
            f"No hay tarifa de ISR para la periodicidad {clave!r} — {motivo}."
        )
    return tarifa


def isr_periodo(base_gravable: Decimal, clave_periodicidad: str, fecha: date) -> Decimal:
    """
    ISR causado del periodo, por la tarifa del Art. 96 LISR que corresponda.

    ISR = cuota fija + (base - limite inferior) x tasa sobre excedente.
    NO aplica el subsidio para el empleo: eso lo hace `subsidio.py` y lo
    combina F1-04. Devuelve Decimal redondeado a 2 decimales.

    Raises:
        FiscalValidationError: si la base es negativa o la periodicidad no
            tiene tarifa.
    """
    if base_gravable < 0:
        raise FiscalValidationError(
            f"La base gravable no puede ser negativa: {base_gravable}."
        )
    tarifa = tarifa_por_periodicidad(clave_periodicidad, fecha)
    for renglon in tarifa:
        if base_gravable <= renglon.limite_superior:
            excedente = base_gravable - renglon.limite_inferior
            if excedente < 0:  # base por debajo del primer limite inferior ($0.00)
                excedente = Decimal("0")
            return _redondear(renglon.cuota_fija + excedente * renglon.tasa_excedente)
    # Inalcanzable: el ultimo renglon tiene limite superior infinito.
    raise FiscalValidationError(
        f"No se encontró renglón de tarifa para la base {base_gravable}."
    )
