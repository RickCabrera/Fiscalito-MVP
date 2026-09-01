"""
Avisos de modificacion de salario ante el IMSS (Art. 34 LSS).

Un cambio de SBC hay que avisarlo, y el plazo depende del tipo de salario:

| Tipo    | Plazo                                                      | Fundamento    |
|---------|------------------------------------------------------------|---------------|
| Fijo    | 5 dias habiles siguientes al cambio                         | Art. 34 fr. I |
| Variable| primeros 5 dias habiles de ene, mar, may, jul, sep y nov    | Art. 34 fr. II|
| Mixto   | la parte fija al cambiar; la variable, bimestral            | Art. 34 fr. III|

EL MIXTO GENERA DOS AVISOS
--------------------------
Con dos vencimientos distintos, por eso `avisos_requeridos()` devuelve una
tupla y no un solo resultado.

EL PLAZO DEL AVISO NO SE CORRE POR CAER EN VIERNES
--------------------------------------------------
El Art. 3 del RACERF prorroga al siguiente dia habil los plazos que vencen en
dia inhabil **o viernes**, pero excluye expresamente la presentacion de avisos
afiliatorios. O sea: aqui se CUENTAN solo dias habiles, y el vencimiento se
queda donde cae aunque sea viernes. La regla contraria —la del viernes— aplica
al pago de cuotas del dia 17, que es F1-06. Son dos reglas opuestas que van a
convivir en el mismo repo.

Las fechas que calcula este modulo son **estimaciones conservadoras**: ver la
advertencia sobre la definicion de "dia habil" en `dias_habiles.py`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum

from app.exceptions import FiscalValidationError
from app.nomina_engine.dias_habiles import n_esimo_dia_habil_del_mes, sumar_dias_habiles
from app.redondeo import redondear

DIAS_HABILES_AVISO = 5


class TipoSalario(str, Enum):
    """Art. 30 LSS."""

    FIJO = "fijo"
    VARIABLE = "variable"
    MIXTO = "mixto"


class TipoAviso(str, Enum):
    MODIFICACION_FIJA = "modificacion_fija"
    BIMESTRAL_VARIABLE = "bimestral_variable"


@dataclass(frozen=True)
class ResultadoAviso:
    """Un aviso a presentar, con su vencimiento y su fundamento."""

    requiere: bool
    tipo: TipoAviso
    fecha_limite: date | None
    fundamento: str


def cambio_de_sbc(sbc_anterior: Decimal, sbc_nuevo: Decimal) -> bool:
    """
    Si el SBC cambio, comparando a 2 decimales.

    El redondeo previo no es cosmetico: sin el, una diferencia de sub-centavo
    arrastrada por el promedio de variables dispara un aviso fantasma.
    """
    return redondear(sbc_anterior) != redondear(sbc_nuevo)


def fecha_limite_aviso_fijo(fecha_cambio: date) -> date:
    """
    Vencimiento del aviso por modificacion de salario fijo (Art. 34 fr. I LSS).

    Cinco dias habiles SIGUIENTES al cambio: el dia del cambio no cuenta. No se
    prorroga por caer en viernes (RACERF Art. 3).
    """
    return sumar_dias_habiles(fecha_cambio, DIAS_HABILES_AVISO)


def fecha_limite_aviso_variable(bimestre_reportado: int, anio: int) -> date:
    """
    Vencimiento del aviso bimestral de variables (Art. 34 fr. II LSS).

    Quinto dia habil del mes impar siguiente al bimestre que se reporta: el
    bimestre 1 (ene-feb) se avisa en marzo, el 2 (mar-abr) en mayo, y el 6
    (nov-dic) en enero del año siguiente.

    Args:
        bimestre_reportado: 1 a 6.
        anio: año del bimestre reportado, no el del aviso.
    """
    if not 1 <= bimestre_reportado <= 6:
        raise FiscalValidationError(
            f"Bimestre inválido: {bimestre_reportado}. Debe estar entre 1 y 6."
        )
    mes = 2 * bimestre_reportado + 1
    if mes > 12:  # el bimestre 6 se avisa en enero del año siguiente
        mes, anio = 1, anio + 1
    return n_esimo_dia_habil_del_mes(anio, mes, DIAS_HABILES_AVISO)


def _exigir(valor, nombre: str, motivo: str):
    if valor is None:
        raise FiscalValidationError(f"Falta `{nombre}`: {motivo}")
    return valor


def _aviso_parte_fija(
    sbc_fijo_anterior: Decimal, sbc_fijo_nuevo: Decimal, fecha_cambio: date, fundamento: str
) -> ResultadoAviso:
    hubo_cambio = cambio_de_sbc(sbc_fijo_anterior, sbc_fijo_nuevo)
    return ResultadoAviso(
        requiere=hubo_cambio,
        tipo=TipoAviso.MODIFICACION_FIJA,
        fecha_limite=fecha_limite_aviso_fijo(fecha_cambio) if hubo_cambio else None,
        fundamento=fundamento,
    )


def avisos_requeridos(
    tipo_salario: TipoSalario,
    *,
    sbc_fijo_anterior: Decimal | None = None,
    sbc_fijo_nuevo: Decimal | None = None,
    fecha_cambio: date | None = None,
    bimestre_reportado: int | None = None,
    anio_bimestre: int | None = None,
) -> tuple[ResultadoAviso, ...]:
    """
    Avisos que hay que presentar, con su vencimiento.

    Los argumentos son SOLO POR NOMBRE y no tienen defaults derivados de otro
    argumento, a proposito: cada tipo de salario necesita datos distintos y un
    default silencioso aqui produce una fecha limite legal equivocada sin que
    nada falle.

    Args:
        sbc_fijo_anterior / sbc_fijo_nuevo: la parte FIJA del SBC, no el total.
            Para el mixto la distincion es la que decide si hay aviso: el
            Art. 34 fr. III obliga a avisar la parte fija solo cuando la parte
            fija cambia. Comparar totales declararia un aviso que no existe
            cada vez que se moviera nada mas el promedio variable.
        fecha_cambio: fecha del cambio de la parte fija. Obligatoria para fijo
            y mixto; sin sentido para variable puro, que no tiene "fecha de
            cambio" sino un bimestre.
        bimestre_reportado: 1 a 6, el bimestre cuyo promedio se determina.
        anio_bimestre: año DEL BIMESTRE reportado, no el del aviso. Es
            obligatorio y explicito: el bimestre 6 se avisa en enero del año
            siguiente, asi que derivarlo de una fecha de captura de enero
            devolveria el vencimiento del año equivocado.

    Diferencia de fondo entre los tipos: en el fijo el aviso existe solo si el
    SBC cambio; en variable y mixto la obligacion bimestral existe **aunque el
    promedio haya dado igual**, porque lo que se presenta es la determinacion
    del bimestre.

    Returns:
        Una tupla. El mixto devuelve DOS avisos con vencimientos distintos.
    """
    motivo_sbc = "el aviso compara el SBC de la parte fija antes y despues del cambio"
    motivo_fecha = "el plazo de 5 dias habiles del Art. 34 corre desde el cambio"

    if tipo_salario is TipoSalario.FIJO:
        return (
            _aviso_parte_fija(
                _exigir(sbc_fijo_anterior, "sbc_fijo_anterior", motivo_sbc),
                _exigir(sbc_fijo_nuevo, "sbc_fijo_nuevo", motivo_sbc),
                _exigir(fecha_cambio, "fecha_cambio", motivo_fecha),
                "Art. 34 fr. I LSS",
            ),
        )

    motivo_bimestre = (
        f"el aviso de {tipo_salario.value} es bimestral (Art. 34 fr. II LSS) y no "
        f"depende de una fecha de cambio"
    )
    aviso_variable = ResultadoAviso(
        requiere=True,  # la obligacion bimestral no depende de que el SBC cambie
        tipo=TipoAviso.BIMESTRAL_VARIABLE,
        fecha_limite=fecha_limite_aviso_variable(
            _exigir(bimestre_reportado, "bimestre_reportado", motivo_bimestre),
            _exigir(
                anio_bimestre,
                "anio_bimestre",
                "el bimestre 6 se avisa en enero del año siguiente, asi que el año del "
                "bimestre no se puede inferir de la fecha en que se calcula",
            ),
        ),
        fundamento="Art. 34 fr. II LSS",
    )
    if tipo_salario is TipoSalario.VARIABLE:
        return (aviso_variable,)

    return (
        _aviso_parte_fija(
            _exigir(sbc_fijo_anterior, "sbc_fijo_anterior", motivo_sbc),
            _exigir(sbc_fijo_nuevo, "sbc_fijo_nuevo", motivo_sbc),
            _exigir(fecha_cambio, "fecha_cambio", motivo_fecha),
            "Art. 34 fr. III LSS (parte fija)",
        ),
        aviso_variable,
    )
