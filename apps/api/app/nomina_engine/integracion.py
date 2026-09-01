"""
Salario Base de Cotizacion (SBC) y factor de integracion.

El SBC —tambien llamado Salario Diario Integrado (SDI)— es la base de casi
todas las cuotas de `tablas_imss.py`. Referencia documental con fuentes:
`knowledge_base/nomina/21_sbc_integracion.md`.

    SBC = salario_diario x factor + conceptos integrables + promedio variable
    SBC = clamp(SBC, 1 SM del area, 25 UMA)          (Art. 28 LSS)

EL FACTOR SE CALCULA, NO SE BUSCA EN UNA TABLA
----------------------------------------------
La tabla de factores minimos de ley (1.0493 para el primer año, etc.) es
material de TEST, no de produccion: muchas empresas otorgan prestaciones
superiores a la ley (30 dias de aguinaldo, prima del 50%, vales), y §D5 fija el
minimo de ley solo como default. El motor calcula desde
`(dias_aguinaldo, dias_vacaciones, prima_vacacional)`.

EL DIVISOR ES 365, SIEMPRE
--------------------------
No son "los dias del año": es 365 constante por convencion del IMSS/SUA,
tambien en años bisiestos. 2028 no cambia el factor.

EL CASO REAL NO ES MINIMO DE LEY
--------------------------------
Por §D9, cuando el SDI viene de un CFDI se toma como DATO DE ENTRADA y no se
recomputa: los factores implicitos del caso real de S-04 son superiores a los
de ley y no derivables de la antiguedad. Por eso la decision D12 sobre los
decimales del factor NO afecta el cuadre de S-04.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.constants import ZonaSalarioMinimo, salario_minimo_vigente, uma_vigente
from app.exceptions import FiscalValidationError
from app.redondeo import redondear, redondear_factor

DIAS_AGUINALDO_DE_LEY = 15
PRIMA_VACACIONAL_DE_LEY = Decimal("0.25")
DIAS_DEL_ANIO_PARA_INTEGRAR = Decimal("365")
UMAS_TOPE_SBC = 25


def dias_vacaciones_de_ley(anios_servicio_cumplidos: int) -> int:
    """
    Dias de vacaciones que marca el Art. 76 LFT segun la antiguedad.

    `anios_servicio_cumplidos` son años CUMPLIDOS: **0 es el alta nueva**, que
    para integrar el SBC usa los 12 dias que va a devengar en su primer año.
    Rechazar el 0 haria imposible calcular el SBC de un alta — que es
    justamente el caso con 5 dias habiles para presentar el aviso.

    Escala vigente desde el 1-ene-2023 (reforma DOF 27-12-2022): 12 dias el
    primer año, mas 2 por cada año subsecuente hasta llegar a 20, y a partir
    del sexto año 2 dias mas por cada 5 de servicios.

    La regla NO es una tabla cerrada: 36-40 años dan 34 dias, y asi
    sucesivamente. Un trabajador de 37 años de antiguedad existe.
    """
    if anios_servicio_cumplidos < 0:
        raise FiscalValidationError(
            f"Los años de servicio no pueden ser negativos: {anios_servicio_cumplidos}."
        )
    if anios_servicio_cumplidos <= 1:
        return 12
    if anios_servicio_cumplidos <= 5:
        return 12 + 2 * (anios_servicio_cumplidos - 1)
    quinquenios = -(-(anios_servicio_cumplidos - 5) // 5)  # techo de la division
    return 20 + 2 * quinquenios


def factor_integracion(
    dias_aguinaldo: int, dias_vacaciones: int, prima_vacacional: Decimal
) -> Decimal:
    """
    Factor de integracion del SBC (Art. 27 LSS).

        factor = 1 + dias_aguinaldo/365 + dias_vacaciones x prima/365

    Devuelve el factor **redondeado a 4 decimales** (D12), que es la precision
    con la que se declara y con la que estan expresadas las tablas de
    prestaciones minimas.

    Raises:
        FiscalValidationError: si el aguinaldo es menor a los 15 dias del
            Art. 87 LFT, si los dias de vacaciones son negativos, o si la prima
            vacacional cae fuera de [0.25, 1]. La validacion de la prima no es
            paranoia: pasar `25` en vez de `0.25` produce un factor de 1.86 y
            un SBC inflado 77% que ninguna tabla de referencia detecta.
    """
    if dias_aguinaldo < DIAS_AGUINALDO_DE_LEY:
        raise FiscalValidationError(
            f"El aguinaldo de {dias_aguinaldo} días es menor al mínimo de ley "
            f"({DIAS_AGUINALDO_DE_LEY} días, Art. 87 LFT). Un aguinaldo menor "
            f"subintegraría el SBC y las cuotas."
        )
    if dias_vacaciones < 0:
        raise FiscalValidationError(
            f"Los días de vacaciones no pueden ser negativos: {dias_vacaciones}."
        )
    if not PRIMA_VACACIONAL_DE_LEY <= prima_vacacional <= Decimal("1"):
        raise FiscalValidationError(
            f"La prima vacacional {prima_vacacional} está fuera de [0.25, 1]. El "
            f"mínimo de ley es 25% (Art. 80 LFT) y se expresa como proporción "
            f"(0.25), no como porcentaje (25)."
        )
    proporcion_aguinaldo = Decimal(dias_aguinaldo) / DIAS_DEL_ANIO_PARA_INTEGRAR
    proporcion_prima = (
        Decimal(dias_vacaciones) * prima_vacacional / DIAS_DEL_ANIO_PARA_INTEGRAR
    )
    return redondear_factor(Decimal(1) + proporcion_aguinaldo + proporcion_prima)


def factor_integracion_de_ley(anios_servicio_cumplidos: int) -> Decimal:
    """Factor con prestaciones minimas de ley para una antiguedad dada."""
    return factor_integracion(
        DIAS_AGUINALDO_DE_LEY,
        dias_vacaciones_de_ley(anios_servicio_cumplidos),
        PRIMA_VACACIONAL_DE_LEY,
    )


@dataclass(frozen=True)
class ConceptoIntegrable:
    """
    Una percepcion adicional que puede integrar al SBC (Art. 27 LSS).

    `monto_diario` es la **porcion que integra**, ya calculada por el llamador,
    no la percepcion completa. Varias exclusiones del Art. 27 tienen tope y
    solo integra el EXCEDENTE: despensa por encima del 40% de la UMA, premios
    de asistencia y de puntualidad por encima del 10% del SBC cada uno. Pasar
    la despensa completa con `integra=True` sobreintegra el SBC.

    El motor no decide que integra: el catalogo es dato, no `if`s (§D5).
    """

    descripcion: str
    monto_diario: Decimal
    integra: bool
    fundamento: str = "Art. 27 LSS"


@dataclass(frozen=True)
class SBCAcotado:
    """SBC despues del clamp del Art. 28 LSS, con el rastro de que se aplico."""

    valor: Decimal
    piso_aplicado: bool
    tope_aplicado: bool
    piso: Decimal
    tope: Decimal


def _suma_integrable(conceptos: tuple[ConceptoIntegrable, ...]) -> Decimal:
    return sum(
        (c.monto_diario for c in conceptos if c.integra), start=Decimal("0")
    )


def sbc_fijo(
    salario_diario: Decimal,
    factor: Decimal,
    conceptos: tuple[ConceptoIntegrable, ...] = (),
) -> Decimal:
    """
    SBC de salario fijo (Art. 30 fr. I LSS): salario x factor + integrables.

    **El valor NO esta acotado.** Pasalo por `clamp_sbc()` antes de calcular
    cuotas: `tablas_imss.ceav_patronal()` levanta si recibe un SBC por debajo
    del piso, a proposito, para que nadie lo corrija en silencio.
    """
    if salario_diario < 0:
        raise FiscalValidationError(
            f"El salario diario no puede ser negativo: {salario_diario}."
        )
    return redondear(salario_diario * factor + _suma_integrable(conceptos))


def sbc_variable(percepciones_variables: Decimal, dias_devengados: int) -> Decimal:
    """
    Parte variable del SBC (Art. 30 fr. II LSS).

    Promedio diario de las percepciones variables del bimestre anterior:
    `total / dias de salario devengado en ese bimestre`. En un alta nueva no
    hay bimestre anterior y el patron estima.

    **El valor NO esta acotado** — ver `sbc_fijo`.
    """
    if percepciones_variables < 0:
        raise FiscalValidationError(
            f"Las percepciones variables no pueden ser negativas: {percepciones_variables}."
        )
    if dias_devengados <= 0:
        raise FiscalValidationError(
            f"Los días de salario devengado deben ser positivos: {dias_devengados}. "
            f"En un alta nueva no hay bimestre anterior: el SBC variable se estima."
        )
    return redondear(percepciones_variables / Decimal(dias_devengados))


def sbc_mixto(
    salario_diario: Decimal,
    factor: Decimal,
    percepciones_variables: Decimal,
    dias_devengados: int,
    conceptos: tuple[ConceptoIntegrable, ...] = (),
) -> Decimal:
    """
    SBC mixto (Art. 30 fr. III LSS): parte fija integrada + promedio variable.

    El clamp se aplica UNA vez al total, no a cada componente. **El valor NO
    esta acotado** — ver `sbc_fijo`.
    """
    fija = sbc_fijo(salario_diario, factor, conceptos)
    variable = sbc_variable(percepciones_variables, dias_devengados)
    return redondear(fija + variable)


def clamp_sbc(sbc: Decimal, fecha: date, zona: ZonaSalarioMinimo) -> SBCAcotado:
    """
    Acota el SBC entre 1 salario minimo del area y 25 UMA (Art. 28 LSS).

    Piso y tope se mueven en fechas distintas: el piso sigue al salario minimo
    (1 de enero) y el tope a la UMA (1 de febrero). En enero conviven el
    salario minimo del año en curso y la UMA del anterior.

    Devuelve `SBCAcotado` y no un `Decimal` a secas porque saber que se aplico
    el piso importa aguas abajo: es el unico camino por el que un SBC llega a
    ser exactamente 1 salario minimo, que es el supuesto del Art. 36 LSS (el
    patron absorbe la cuota obrera) y el renglon de 3.150% de la tabla de CEAV.
    """
    if sbc < 0:
        raise FiscalValidationError(f"El SBC no puede ser negativo: {sbc}.")
    piso = salario_minimo_vigente(fecha, zona)
    tope = redondear(uma_vigente(fecha) * UMAS_TOPE_SBC)
    if sbc < piso:
        return SBCAcotado(piso, True, False, piso, tope)
    if sbc > tope:
        return SBCAcotado(tope, False, True, piso, tope)
    return SBCAcotado(sbc, False, False, piso, tope)
