"""
ISR de sueldos y salarios: exenciones, base gravable y retencion.

    base_gravable = percepciones - exenciones del Art. 93 LISR
    isr_causado   = tarifa del Art. 96 segun la periodicidad (tablas_isr_periodicas)
    isr_retenido  = max(isr_causado - subsidio, 0)

Fuentes: LISR Art. 93 **fr. I y fr. XIV** (las unicas exenciones que este
modulo implementa) y Art. 96; Decreto de desindexacion del salario minimo
(DOF 27-01-2016) y Art. 26 apartado B constitucional, que es el eslabon por el
que los topes que la ley expresa en
"veces el salario minimo" se leen en UMA. Sin ese eslabon el aguinaldo exento
seria $9,451.20 en vez de $3,519.30: un factor de 2.69.

Referencia documental (que se declara a si misma no fuente de calculo):
`knowledge_base/nomina/23_isr_nomina_subsidio.md`.

TRES NORMAS DISTINTAS PARA EL TRABAJADOR DE SALARIO MINIMO
-----------------------------------------------------------
Coinciden en la misma persona y **se aplican por separado**:

1. Tiempo extra 100 % exento, dentro de los limites de la LFT (Art. 93 fr. I).
2. **No se le efectua retencion de ISR** (Art. 96, ultimo parrafo).
3. El patron absorbe su cuota obrera del IMSS (Art. 36 LSS) — eso es `cuotas.py`.

El predicado NO se define aqui: se recibe ya resuelto, y quien lo resuelve es
`ceav.es_trabajador_de_salario_minimo()`, que es el unico del motor a
proposito (§D4). **Salvedad abierta:** ese predicado compara el **SBC** contra
el salario minimo, y los Arts. 93 y 96 hablan del **salario**, no del SBC. Es
la misma ambiguedad de §D4 y esta anotada ahi; no se bifurca en silencio.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.constants import uma_vigente
from app.exceptions import FiscalValidationError
from app.nomina_engine.subsidio import subsidio_empleo
from app.nomina_engine.tablas_isr_periodicas import isr_periodo
from app.redondeo import redondear

# Topes de exencion en veces la UMA diaria vigente a la fecha de pago.
# Clave = c_TipoPercepcion del complemento de nomina.
TOPES_EN_UMA: dict[str, tuple[int, str]] = {
    "002": (30, "Art. 93 fr. XIV LISR — gratificación anual (aguinaldo)"),
    "003": (15, "Art. 93 fr. XIV LISR — PTU"),
    "021": (15, "Art. 93 fr. XIV LISR — prima vacacional"),
}

# Percepciones que NO tienen exencion en el Art. 93 y por tanto van 100 %
# gravadas. Es una LISTA BLANCA a proposito: cualquier clave que no este aqui
# ni tenga exencion implementada levanta error.
#
# El default invertido es la unica forma de cerrar el hueco. El Art. 93 tiene
# fracciones enteras —prevision social (fr. VIII y IX, con tope CONJUNTO de
# 7 UMA), pagos por separacion (fr. XIII), subsidios por incapacidad (fr. III),
# jubilaciones (fr. IV y V), reembolso de gastos medicos (fr. VI)— cuyas claves
# son muchas y cuyo calculo este modulo no implementa. Enumerarlas una por una
# dejaria fuera las que se olviden, y esas se gravarian al 100 % en silencio.
#
# Y aqui el silencio es el error peligroso: gravar de mas es conservador **para
# el fisco**, no para el trabajador, que es a quien se le retiene de mas.
GRAVADAS_AL_100: dict[str, str] = {
    "001": "Sueldos, salarios, rayas y jornales",
    "010": "Premios por puntualidad",
    "038": "Otros ingresos por salarios",
    "049": "Premios por asistencia",
}


@dataclass(frozen=True)
class Percepcion:
    """Una partida del recibo, antes de separar gravado y exento."""

    clave: str
    descripcion: str
    importe: Decimal


@dataclass(frozen=True)
class PercepcionGravada:
    """La misma partida ya partida, con el fundamento de su exencion."""

    clave: str
    descripcion: str
    importe: Decimal
    gravado: Decimal
    exento: Decimal
    fundamento: str


@dataclass(frozen=True)
class ContextoExencion:
    """
    Datos que las exenciones necesitan y que no vienen en la percepcion.

    `domingos_trabajados` no esta en el CFDI: la prima dominical se exenta
    hasta 1 UMA **por domingo trabajado** (Art. 93 fr. XIV), asi que el
    llamador tiene que decirlo. Default 1, que es lo que corresponde a un
    recibo semanal con prima dominical.
    """

    fecha: date
    domingos_trabajados: int = 1
    es_trabajador_de_salario_minimo: bool = False
    semanas_del_periodo: Decimal = Decimal("1")


def _exenta_todo(p: Percepcion, fundamento: str) -> PercepcionGravada:
    return PercepcionGravada(
        p.clave, p.descripcion, p.importe, Decimal("0.00"), p.importe, fundamento
    )


def _grava_todo(p: Percepcion, fundamento: str) -> PercepcionGravada:
    return PercepcionGravada(
        p.clave, p.descripcion, p.importe, p.importe, Decimal("0.00"), fundamento
    )


def _con_tope(p: Percepcion, tope: Decimal, fundamento: str) -> PercepcionGravada:
    exento = min(p.importe, tope)
    return PercepcionGravada(
        p.clave, p.descripcion, p.importe, p.importe - exento, exento, fundamento
    )


def _horas_extra(p: Percepcion, ctx: ContextoExencion) -> PercepcionGravada:
    """
    Art. 93 fr. I: el tiempo extra tiene dos ramas segun el trabajador.

    Al de salario minimo se le exenta el 100 % dentro de los limites de la LFT;
    a los demas, el 50 % sin exceder **5 UMA por semana** de servicios.

    LIMITE CONOCIDO, no implementado: el Art. 66 LFT acota el tiempo extra a
    3 horas diarias y 3 veces por semana, y lo que excede se paga al triple y
    es 100 % gravado. Este modulo no recibe las horas, asi que no lo verifica.
    Ojo con la direccion del error: aqui va **a favor del trabajador y en
    contra del fisco**, la contraria a la que el resto del modulo cuida. Por
    eso el fundamento devuelto no afirma que el limite se haya cumplido.
    """
    if ctx.es_trabajador_de_salario_minimo:
        return _exenta_todo(
            p,
            "Art. 93 fr. I LISR — trabajador de salario mínimo (los límites de tiempo "
            "extra del Art. 66 LFT no se verifican aquí)",
        )
    tope = redondear(uma_vigente(ctx.fecha) * 5 * ctx.semanas_del_periodo)
    exento = min(redondear(p.importe / 2), tope)
    return PercepcionGravada(
        p.clave,
        p.descripcion,
        p.importe,
        p.importe - exento,
        exento,
        "Art. 93 fr. I LISR — 50 % exento, tope de 5 UMA por semana",
    )


def exentar(percepcion: Percepcion, contexto: ContextoExencion) -> PercepcionGravada:
    """
    Separa una percepcion en gravado y exento (Art. 93 LISR).

    Los topes se expresan en UMA vigente **a la fecha de pago**: en enero rige
    la UMA del año anterior, asi que la misma percepcion exenta distinto.

    Raises:
        FiscalValidationError: si el importe es negativo, o si la clave no
            esta clasificada — ver el comentario de `GRAVADAS_AL_100`.
    """
    if percepcion.importe < 0:
        raise FiscalValidationError(
            f"El importe de {percepcion.clave} no puede ser negativo: {percepcion.importe}."
        )
    if percepcion.clave == "019":
        return _horas_extra(percepcion, contexto)
    if percepcion.clave == "020":
        tope = redondear(uma_vigente(contexto.fecha) * contexto.domingos_trabajados)
        return _con_tope(
            percepcion, tope, "Art. 93 fr. XIV LISR — 1 UMA por domingo trabajado"
        )
    en_uma = TOPES_EN_UMA.get(percepcion.clave)
    if en_uma is not None:
        veces, fundamento = en_uma
        return _con_tope(
            percepcion, redondear(uma_vigente(contexto.fecha) * veces), fundamento
        )
    if percepcion.clave in GRAVADAS_AL_100:
        return _grava_todo(percepcion, "Sin exención en el Art. 93 LISR")
    raise FiscalValidationError(
        f"La percepción {percepcion.clave} no está clasificada. Este módulo implementa "
        f"las exenciones del Art. 93 fr. I y fr. XIV, y grava al 100 % solo las claves "
        f"que sabe que no tienen exención ({', '.join(sorted(GRAVADAS_AL_100))}). Las "
        f"demás fracciones —previsión social con tope conjunto de 7 UMA (fr. VIII y IX), "
        f"pagos por separación (fr. XIII), subsidios por incapacidad (fr. III), "
        f"jubilaciones (fr. IV y V), reembolso de gastos médicos (fr. VI)— no están "
        f"implementadas. Gravarla al 100 % en silencio le retendría de más al trabajador."
    )


def base_gravable(
    percepciones: tuple[Percepcion, ...], contexto: ContextoExencion
) -> tuple[tuple[PercepcionGravada, ...], Decimal]:
    """
    Desglose gravado/exento de cada percepcion, y la base gravable del periodo.

    La suma NO se re-redondea: los importes del CFDI ya vienen a 2 decimales y
    §D2 redondea por concepto, no al agregar. Si el llamador arma percepciones
    con mas decimales, redondearlas es su responsabilidad.
    """
    desglose = tuple(exentar(p, contexto) for p in percepciones)
    return desglose, sum((d.gravado for d in desglose), start=Decimal("0"))


@dataclass(frozen=True)
class ResultadoISR:
    """ISR del periodo, con el subsidio ya acreditado."""

    causado: Decimal
    subsidio: Decimal
    acreditado: Decimal
    retenido: Decimal
    subsidio_no_entregado: Decimal
    sin_retencion_por_salario_minimo: bool

    @property
    def invariante(self) -> bool:
        """
        Las dos reglas que el resultado siempre cumple.

        1. **El subsidio no se pierde**: `subsidio == acreditado +
           no_entregado`, en cualquier rama.
        2. **El retenido**: normalmente `causado - acreditado`; cero cuando el
           Art. 96 ultimo parrafo lo suprime.

        La segunda regla NO es la misma en las dos ramas a proposito: la no
        retencion del Art. 96 **no es un acreditamiento**. El ISR se causa
        igual, simplemente no se retiene, y el subsidio queda integro sin
        entregar porque no hubo ISR contra el cual aplicarlo.
        """
        subsidio_completo = self.subsidio == self.acreditado + self.subsidio_no_entregado
        if self.sin_retencion_por_salario_minimo:
            return subsidio_completo and self.retenido == Decimal("0.00")
        return subsidio_completo and self.retenido == self.causado - self.acreditado


def isr_retenido(
    base: Decimal,
    clave_periodicidad: str,
    fecha: date,
    ingreso_gravado_mensual: Decimal,
    dias_periodo: int,
    es_trabajador_de_salario_minimo: bool = False,
) -> ResultadoISR:
    """
    ISR a retener del periodo.

    Args:
        ingreso_gravado_mensual: base MENSUAL contra la que se compara el tope
            del subsidio. Este modulo no la deriva: la decision de como se
            obtiene en una nomina semanal es §D11 y sigue abierta. El caso real
            de S-04 aporta evidencia — ver §D11.
        es_trabajador_de_salario_minimo: resuelto por
            `ceav.es_trabajador_de_salario_minimo()`. Activa el ultimo parrafo
            del Art. 96: no se le efectua retencion.

    El subsidio **solo reduce el ISR hasta cero**. Desde 2024 el remanente no se
    entrega en efectivo, y se reporta en `subsidio_no_entregado` porque el CFDI
    lo declara aparte (`SubsidioCausado`) del importe entregado.
    """
    causado = isr_periodo(base, clave_periodicidad, fecha)
    subsidio = subsidio_empleo(fecha, ingreso_gravado_mensual, dias_periodo)
    # Sin retencion no hay ISR contra el cual acreditar, asi que el subsidio
    # queda integro sin entregar. Devolver `acreditado` explicito es lo que
    # permite a F1-05 emitir SubsidioCausado y el importe entregado sin tener
    # que reconstruirlos, y lo que mantiene el invariante en las dos ramas.
    acreditado = (
        Decimal("0.00") if es_trabajador_de_salario_minimo else min(subsidio, causado)
    )
    return ResultadoISR(
        causado=causado,
        subsidio=subsidio,
        acreditado=acreditado,
        retenido=Decimal("0.00")
        if es_trabajador_de_salario_minimo
        else causado - acreditado,
        subsidio_no_entregado=subsidio - acreditado,
        sin_retencion_por_salario_minimo=es_trabajador_de_salario_minimo,
    )
