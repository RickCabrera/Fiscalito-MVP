"""
Calculo de cuotas obrero-patronales IMSS e Infonavit.

Consume las tablas de `tablas_imss.py` y el SBC ya acotado de `integracion.py`.
Ningun porcentaje se teclea aqui: todos vienen de la tabla, con su fundamento.

TRES BASES DISTINTAS, NO UNA
----------------------------
Cada ramo declara su base (`BaseCuota`) y este modulo la respeta: el SBC para
casi todo, la **UMA** para la cuota fija de Enfermedades y Maternidad
(Art. 106 fr. I LSS) y el **excedente sobre 3 UMA** para la fraccion II, que
ademas solo existe si el SBC supera ese umbral.

LOS DIAS NO SON UN SOLO NUMERO
------------------------------
El ausentismo y la incapacidad **no reducen Enfermedades y Maternidad**
(Art. 31 LSS, decision D3): un trabajador con 3 dias de ausencia cotiza 27 dias
en los demas ramos y 30 en EyM. Por eso se recibe `DiasDelPeriodo` y no un
entero: un contador unico subcobraria EyM en silencio.

ART. 36 LSS — EL PATRON ABSORBE, NO SE EXENTA
---------------------------------------------
Cuando el trabajador es de salario minimo, la cuota obrera **se sigue
calculando y enterando**; solo cambia quien la paga. En el resultado eso se ve
asi: cada `CuotaRamo` conserva su `obrero` legal para el desglose —que es lo
que permite conciliar contra la EMA linea por linea— mientras `total_obrero`
queda en cero y `total_patron` la incluye. El invariante
`total == total_patron + total_obrero` se cumple en los dos casos.

QUE NO ES UNA CUOTA
-------------------
La **amortizacion de credito Infonavit** (`TipoDeduccion=010` del CFDI) aparece
en el caso real, pero no es un ramo ni una cuota: es un descuento al trabajador
que el patron retiene y entera. No entra en ningun total de este modulo. Su
lugar es el recibo, F1-05.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.constants import ZonaSalarioMinimo, salario_minimo_vigente, uma_vigente
from app.exceptions import FiscalValidationError
from app.nomina_engine.ceav import (
    es_trabajador_de_salario_minimo,
    ramo_ceav_patronal,
)
from app.nomina_engine.integracion import UMAS_TOPE_SBC, SBCAcotado
from app.nomina_engine.tablas_imss import (
    BaseCuota,
    PeriodicidadCuota,
    Ramo,
    cuotas_ramos_vigentes,
    ramo_riesgos_trabajo,
)
from app.redondeo import redondear

UMAS_UMBRAL_EXCEDENTE_EYM = 3


@dataclass(frozen=True)
class DiasDelPeriodo:
    """
    Dias del periodo, con sus ausencias (Art. 31 LSS, decision D3).

    `dias_periodo` son los dias naturales que cubre el entero. Ausentismos e
    incapacidades reducen los dias cotizados de los ramos generales pero **no**
    los de Enfermedades y Maternidad.
    """

    dias_periodo: int
    dias_ausentismo: int = 0
    dias_incapacidad: int = 0

    def __post_init__(self) -> None:
        if not 0 < self.dias_periodo <= 31:
            raise FiscalValidationError(
                f"Los días del periodo deben estar entre 1 y 31: {self.dias_periodo}."
            )
        if self.dias_ausentismo < 0 or self.dias_incapacidad < 0:
            raise FiscalValidationError(
                "Los días de ausentismo e incapacidad no pueden ser negativos."
            )
        if self.dias_ausentismo + self.dias_incapacidad > self.dias_periodo:
            raise FiscalValidationError(
                f"Las ausencias ({self.dias_ausentismo} + {self.dias_incapacidad}) no "
                f"pueden exceder los días del periodo ({self.dias_periodo})."
            )

    def dias_de(self, ramo: Ramo) -> int:
        """Dias cotizados de un ramo, segun si sus dias se reducen o no (D3)."""
        if not ramo.se_reduce_por_ausentismo:
            return self.dias_periodo
        return self.dias_periodo - self.dias_ausentismo - self.dias_incapacidad


@dataclass(frozen=True)
class CuotaRamo:
    """
    Una cuota calculada, con todo lo necesario para conciliarla contra la EMA.

    `base_diaria` y `tasa_*` se conservan porque un renglon de CEAV sin su tasa
    de tramo no es conciliable: la EMA trae importes y hay que poder explicar
    de donde salio cada uno.
    """

    clave: str
    nombre: str
    base_diaria: Decimal
    dias: int
    tasa_patron: Decimal
    tasa_obrero: Decimal
    patron: Decimal
    obrero: Decimal
    periodicidad: PeriodicidadCuota
    fundamento: str


@dataclass(frozen=True)
class CuotasEmpleado:
    """Cuotas de un empleado en un periodo, con su desglose por ramo."""

    ramos: tuple[CuotaRamo, ...]
    total_patron: Decimal
    total_obrero: Decimal
    total: Decimal
    sbc: SBCAcotado
    dias: DiasDelPeriodo
    absorbio_cuota_obrera: bool


def _verificar_coherencia(sbc: SBCAcotado, fecha: date, zona: ZonaSalarioMinimo) -> None:
    """
    El SBC tuvo que acotarse con la misma fecha y zona con las que se cotiza.

    Sin esta guarda, un `SBCAcotado` calculado con el piso de enero y la UMA de
    febrero pasaria sin ruido y produciria un numero plausible y equivocado.
    """
    piso = salario_minimo_vigente(fecha, zona)
    tope = redondear(uma_vigente(fecha) * UMAS_TOPE_SBC)
    if sbc.piso != piso or sbc.tope != tope:
        raise FiscalValidationError(
            f"El SBC se acotó con piso {sbc.piso} y tope {sbc.tope}, pero en "
            f"{fecha.isoformat()} para la zona {zona} corresponden {piso} y {tope}. "
            f"Vuelve a acotarlo con `clamp_sbc(sbc, fecha, zona)`."
        )


def _base_diaria(ramo: Ramo, sbc: Decimal, fecha: date) -> Decimal:
    """Base diaria de un ramo segun su `BaseCuota`."""
    if ramo.base is BaseCuota.SBC:
        return sbc
    if ramo.base is BaseCuota.UMA:
        return uma_vigente(fecha)
    umbral = uma_vigente(fecha) * UMAS_UMBRAL_EXCEDENTE_EYM
    return sbc - umbral if sbc > umbral else Decimal("0")


def cuotas_empleado(
    sbc: SBCAcotado,
    dias: DiasDelPeriodo,
    fecha: date,
    zona: ZonaSalarioMinimo,
    prima_riesgo: Decimal,
) -> CuotasEmpleado:
    """
    Cuotas de un empleado para el periodo.

    Args:
        sbc: SBC **ya acotado** por `integracion.clamp_sbc`. Se exige el tipo
            acotado y no un Decimal para que el clamp del Art. 28 no se pueda
            saltar, y porque el resultado del clamp es lo que dice si aplica el
            Art. 36.
        prima_riesgo: prima de Riesgos de Trabajo de la empresa. No es una tasa
            de ley: se autodetermina cada febrero (Art. 74 LSS).

    El redondeo es **por concepto y por empleado** (D2): cada ramo se redondea
    y despues se suman. Redondear la suma da un resultado distinto al centavo,
    y el caso real de S-04 muestra los dos ordenes conviviendo (ver D14).
    """
    _verificar_coherencia(sbc, fecha, zona)

    todos = (
        *cuotas_ramos_vigentes(fecha),
        ramo_riesgos_trabajo(prima_riesgo, fecha),
        ramo_ceav_patronal(sbc.valor, fecha, zona),
    )
    absorbe = es_trabajador_de_salario_minimo(sbc.valor, fecha, zona)

    calculadas: list[CuotaRamo] = []
    for ramo in todos:
        base = _base_diaria(ramo, sbc.valor, fecha)
        dias_ramo = dias.dias_de(ramo)
        calculadas.append(
            CuotaRamo(
                clave=ramo.clave,
                nombre=ramo.nombre,
                base_diaria=base,
                dias=dias_ramo,
                tasa_patron=ramo.patron,
                tasa_obrero=ramo.obrero,
                patron=redondear(base * ramo.patron * dias_ramo),
                obrero=redondear(base * ramo.obrero * dias_ramo),
                periodicidad=ramo.periodicidad,
                fundamento=ramo.fundamento,
            )
        )

    suma_patron = sum((c.patron for c in calculadas), start=Decimal("0"))
    suma_obrero = sum((c.obrero for c in calculadas), start=Decimal("0"))
    if absorbe:
        total_patron, total_obrero = suma_patron + suma_obrero, Decimal("0.00")
    else:
        total_patron, total_obrero = suma_patron, suma_obrero

    return CuotasEmpleado(
        ramos=tuple(calculadas),
        total_patron=total_patron,
        total_obrero=total_obrero,
        total=total_patron + total_obrero,
        sbc=sbc,
        dias=dias,
        absorbio_cuota_obrera=absorbe,
    )


@dataclass(frozen=True)
class Consolidado:
    """
    Consolidado de un periodo de entero, con desglose por ramo.

    El desglose no es adorno: es lo que permite conciliar contra la EMA y la
    EBA renglon por renglon (F3). Infonavit va aparte del RCV porque asi llega
    la emision del IMSS y asi se concilia.
    """

    periodicidad: PeriodicidadCuota
    por_ramo: dict[str, Decimal]
    total_patron: Decimal
    total_obrero: Decimal
    total: Decimal
    empleados: int


def _consolidar(
    cuotas: tuple[CuotasEmpleado, ...], periodicidad: PeriodicidadCuota
) -> Consolidado:
    """
    Suma las cuotas de la periodicidad pedida. NO re-redondea (D2).

    El redondeo ya ocurrio por concepto y por empleado; volver a redondear al
    consolidar cambiaria el total contra el que se paga.
    """
    por_ramo: dict[str, Decimal] = {}
    total_patron = Decimal("0")
    total_obrero = Decimal("0")
    for empleado in cuotas:
        for ramo in empleado.ramos:
            if ramo.periodicidad is not periodicidad:
                continue
            por_ramo[ramo.clave] = por_ramo.get(ramo.clave, Decimal("0")) + ramo.patron
            if empleado.absorbio_cuota_obrera:
                por_ramo[ramo.clave] += ramo.obrero
                total_patron += ramo.patron + ramo.obrero
            else:
                por_ramo[ramo.clave] += ramo.obrero
                total_patron += ramo.patron
                total_obrero += ramo.obrero
    return Consolidado(
        periodicidad=periodicidad,
        por_ramo=por_ramo,
        total_patron=total_patron,
        total_obrero=total_obrero,
        total=total_patron + total_obrero,
        empleados=len(cuotas),
    )


def consolidado_mensual(cuotas: tuple[CuotasEmpleado, ...]) -> Consolidado:
    """RT, EyM, IyV y Guarderias: se enteran mensualmente (Art. 39 LSS)."""
    return _consolidar(cuotas, PeriodicidadCuota.MENSUAL)


def consolidado_bimestral(cuotas: tuple[CuotasEmpleado, ...]) -> Consolidado:
    """
    Retiro, CEAV e Infonavit: se enteran bimestralmente (Art. 39 LSS).

    `por_ramo` deja Infonavit en su propia clave porque no es una cuota del
    IMSS sino una aportacion de la Ley del Infonavit, y la emision llega
    separada.
    """
    return _consolidar(cuotas, PeriodicidadCuota.BIMESTRAL)
