"""
Personas morales: ajuste anual por inflación (Arts. 44-46 LISR), anual (Art. 9 / Art. 212) y
PTU a repartir. Parte de `personas_morales.py` (O11); fuentes y decisiones en su docstring.

RENTA GRAVABLE PARA LA PTU (Art. 9 LISR, cuarto párrafo — corrección B3 del revisor de motor)
--------------------------------------------------------------------------------------------
Se parte de ingresos acumulables − deducciones autorizadas del ejercicio, sin disminuir la PTU
pagada ni las pérdidas pendientes, y además "se deberán disminuir de los ingresos acumulables
las cantidades no deducibles en términos de la fracción XXX del artículo 28" (la parte no
deducible de los pagos que a la vez son ingresos exentos para el trabajador: 53 % o 47 %).
Ese importe (`no_deducibles_art28_xxx`) SÓLO disminuye la renta gravable de PTU; no toca la
utilidad fiscal ni el resultado fiscal.

PORCENTAJE DE PTU (O6)
----------------------
10 % de la renta gravable: Resolución del H. Consejo de Representantes de la Sexta Comisión
Nacional para la Participación de los Trabajadores en las Utilidades de las Empresas
(9-sep-2020, publicada en el DOF el 18-sep-2020), resolutivo primero: el porcentaje "deberá
mantenerse en el 10% aplicable sobre la renta gravable". Ratifica el de la Quinta Comisión
(DOF 3-feb-2009). Ver `knowledge_base/16_personas_morales.md`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from app.exceptions import FiscalValidationError
from app.fiscal_engine.actualizacion import MODO_FACTOR_DEFAULT, ModoFactor
from app.fiscal_engine.pm_perdidas import (
    CERO,
    UNO,
    FactorINPC,
    PerdidaAplicada,
    PerdidaPendiente,
    aplicar_perdidas,
    ceros,
    coeficiente_utilidad,
    factor_inpc,
    mes_txt,
    unicas,
)
from app.fiscal_engine.pm_provisionales import TASA_ISR_PM, Estimulo

# Una sola fuente del 10 %: el motor de nómina (P4, O6 del revisor de motor).
from app.nomina_engine.ptu import PORCENTAJE_PTU  # noqa: E402
from app.redondeo import redondear

FUNDAMENTO_PTU = (
    "Resolución de la Sexta Comisión Nacional para la PTU (DOF 18-sep-2020), resolutivo "
    "primero: 10 % sobre la renta gravable; Art. 9 LISR cuarto párrafo"
)


# ── ajuste anual por inflación (Arts. 44-46) ──


@dataclass
class ResultadoAAI:
    saldos_creditos: list[Decimal]
    saldos_deudas: list[Decimal]
    promedio_creditos: Decimal
    promedio_deudas: Decimal
    factor: FactorINPC | None
    factor_ajuste: Decimal
    acumulable: Decimal
    deducible: Decimal
    notas: list[str] = field(default_factory=list)

    @property
    def fuentes_por_confirmar(self) -> tuple[str, ...]:
        return self.factor.fuentes_por_confirmar if self.factor else ()


def ajuste_por_promedios(
    promedio_creditos: Decimal, promedio_deudas: Decimal, factor_ajuste: Decimal
) -> tuple[Decimal, Decimal]:
    """Art. 44: (acumulable, deducible) con los saldos promedio y el factor ya calculados."""
    dif = promedio_deudas - promedio_creditos
    if dif > 0:
        return redondear(dif * factor_ajuste), CERO
    return CERO, redondear(-dif * factor_ajuste)


def ajuste_anual_inflacion(
    anio: int, creditos: list[Decimal], deudas: list[Decimal],
    modo: ModoFactor = MODO_FACTOR_DEFAULT, primer_mes: int = 1,
) -> ResultadoAAI:
    """Art. 44 LISR con los saldos al último día de cada mes del ejercicio."""
    meses = len(creditos)
    if meses == 0 or len(deudas) != meses:
        return ResultadoAAI([], [], CERO, CERO, None, CERO, CERO, CERO,
                            ["Sin saldos mensuales de créditos y deudas: no se calcula el "
                             "ajuste anual por inflación."])
    pc = redondear(sum(creditos, CERO) / meses)
    pd = redondear(sum(deudas, CERO) / meses)
    antiguo = (anio - 1, 12) if primer_mes == 1 else (anio, primer_mes - 1)
    ultimo = (anio, primer_mes + meses - 1)
    f = factor_inpc(ultimo, antiguo, modo)
    factor = f.factor - UNO
    acumulable, deducible = ajuste_por_promedios(pc, pd, factor)
    notas = []
    if f.uso_ultimo_publicado:
        notas.append(f"El INPC de {mes_txt(ultimo)} aún no se publica: el factor usa el último "
                     f"publicado ({f.mes_reciente}) y el ajuste es una estimación (Art. 17-A CFF).")
    return ResultadoAAI(creditos, deudas, pc, pd, f, factor, acumulable, deducible, notas)


# ── anual (Art. 9 / Art. 212) ──


@dataclass
class EntradaAnual:
    anio: int
    ingresos_acumulables: Decimal  # sin el ajuste anual por inflación
    deducciones_autorizadas: Decimal  # sin el ajuste anual por inflación
    aai: ResultadoAAI | None = None
    ptu_pagada: Decimal = CERO
    perdidas: list[PerdidaPendiente] = field(default_factory=list)
    estimulos: list[Estimulo] = field(default_factory=list)
    pagos_provisionales: Decimal = CERO
    retenciones: Decimal = CERO
    anticipos_miembros: Decimal = CERO
    modo: ModoFactor = MODO_FACTOR_DEFAULT
    # Art. 9 cuarto párrafo: no deducibles por el Art. 28 fr. XXX; sólo restan en la renta
    # gravable de PTU (B3).
    no_deducibles_art28_xxx: Decimal = CERO


@dataclass
class Renglon:
    clave: str
    concepto: str
    importe: Decimal
    fundamento: str = ""


@dataclass
class ResultadoAnualPM:
    anio: int
    renglones: list[Renglon]
    utilidad_fiscal: Decimal
    perdida_fiscal: Decimal
    resultado_fiscal: Decimal
    isr_ejercicio: Decimal
    a_cargo: Decimal
    a_favor: Decimal
    coeficiente_siguiente: Decimal
    ingresos_nominales: Decimal
    renta_gravable_ptu: Decimal
    ptu_a_repartir: Decimal
    perdidas: list[PerdidaAplicada]
    notas: list[str] = field(default_factory=list)
    no_deducibles_art28_xxx: Decimal = CERO
    fuentes_por_confirmar: tuple[str, ...] = ()

    def importe(self, clave: str) -> Decimal:
        return next(r.importe for r in self.renglones if r.clave == clave)


def _renglones(e: EntradaAnual, resico: bool, aai_acum: Decimal, aai_ded: Decimal,
               valores: dict[str, Decimal]) -> list[Renglon]:
    art = "Art. 212" if resico else "Art. 9"
    ingreso_txt = ("Ingresos efectivamente percibidos (Art. 207)" if resico
                   else "Ingresos acumulables (sin ajuste por inflación)")
    deduccion_txt = ("Deducciones autorizadas efectivamente erogadas (Arts. 208-210)" if resico
                     else "Deducciones autorizadas")
    v = valores
    return [
        Renglon("ingresos", ingreso_txt, redondear(e.ingresos_acumulables),
                "Art. 207 LISR" if resico else "Arts. 16, 17 y 18 LISR"),
        Renglon("aai_acumulable", "Ajuste anual por inflación acumulable", aai_acum, "Art. 44"),
        Renglon("ingresos_totales", "Total de ingresos acumulables", v["ingresos"], art),
        Renglon("deducciones", deduccion_txt, redondear(e.deducciones_autorizadas),
                "Arts. 208-210 LISR" if resico else "Arts. 25, 27 y 28 LISR"),
        Renglon("aai_deducible", "Ajuste anual por inflación deducible", aai_ded, "Art. 44"),
        Renglon("deducciones_totales", "Total de deducciones autorizadas", v["deducciones"], art),
        Renglon("utilidad_antes_ptu", "Utilidad (pérdida) antes de PTU", v["antes_ptu"], art),
        Renglon("ptu_pagada", "PTU pagada en el ejercicio", e.ptu_pagada, "Art. 9 fr. I"),
        Renglon("utilidad_fiscal", "Utilidad fiscal", v["utilidad"], "Art. 9 fr. I"),
        Renglon("perdida_fiscal", "Pérdida fiscal del ejercicio", v["perdida"], "Art. 57"),
        Renglon("estimulos", "Estímulos que disminuyen la utilidad", v["est"], "Configurado"),
        Renglon("perdidas_aplicadas", "Pérdidas de ejercicios anteriores aplicadas", v["perd"],
                "Arts. 9 fr. II y 57"),
        Renglon("resultado_fiscal", "Resultado fiscal", v["resultado"], "Art. 9 fr. II"),
        Renglon("isr_ejercicio", "ISR del ejercicio (30 %)", v["isr"], "Art. 9"),
        Renglon("pagos_provisionales", "Pagos provisionales efectuados", e.pagos_provisionales,
                "Art. 211" if resico else "Art. 14"),
        Renglon("retenciones", "ISR retenido por el sistema financiero", e.retenciones,
                "Art. 54"),
        Renglon("a_cargo", "ISR a cargo", ceros(v["neto"]), "Art. 76 fr. V"),
        Renglon("a_favor", "ISR a favor", ceros(-v["neto"]), "Art. 22 CFF"),
    ]


def anual_pm(e: EntradaAnual, *, resico: bool = False) -> ResultadoAnualPM:
    """Impuesto del ejercicio de una persona moral (Art. 9; RESICO PM: Art. 212)."""
    if e.no_deducibles_art28_xxx < 0:
        raise FiscalValidationError("Los no deducibles del Art. 28 fr. XXX no pueden ser "
                                    "negativos.")
    aai_acum = e.aai.acumulable if e.aai else CERO
    aai_ded = e.aai.deducible if e.aai else CERO
    ingresos = redondear(e.ingresos_acumulables + aai_acum)
    deducciones = redondear(e.deducciones_autorizadas + aai_ded)
    antes_ptu = ingresos - deducciones
    utilidad_neta = antes_ptu - e.ptu_pagada
    utilidad = ceros(utilidad_neta)
    perdida = ceros(-utilidad_neta)  # Art. 57: la pérdida se aumenta con la PTU pagada.
    est = min(sum((x.importe for x in e.estimulos), CERO), utilidad)
    perd, detalle = aplicar_perdidas(e.perdidas, e.anio, (e.anio, 6), utilidad - est, e.modo)
    resultado = ceros(utilidad - est - perd)
    isr = redondear(resultado * TASA_ISR_PM)
    neto = isr - e.pagos_provisionales - e.retenciones
    r = _renglones(e, resico, aai_acum, aai_ded, {
        "ingresos": ingresos, "deducciones": deducciones, "antes_ptu": antes_ptu,
        "utilidad": utilidad, "perdida": perdida, "est": est, "perd": perd,
        "resultado": resultado, "isr": isr, "neto": neto})
    # Art. 9 cuarto párrafo: sin PTU pagada ni pérdidas, menos los no deducibles del 28-XXX.
    xxx = redondear(e.no_deducibles_art28_xxx)
    renta_ptu = ceros(antes_ptu - xxx)
    ptu = redondear(renta_ptu * PORCENTAJE_PTU)
    coef = CERO if resico else coeficiente_utilidad(
        utilidad, e.ingresos_acumulables, e.anticipos_miembros, e.modo)
    notas = list(e.aai.notas if e.aai else [])
    notas += [p.nota for p in detalle if p.nota]
    if est and est < sum((x.importe for x in e.estimulos), CERO):
        notas.append("Los estímulos se limitaron a la utilidad fiscal del ejercicio.")
    fuentes = unicas(list(e.aai.fuentes_por_confirmar if e.aai else ())
                     + [x for p in detalle for x in p.fuentes_por_confirmar])
    return ResultadoAnualPM(e.anio, r, utilidad, perdida, resultado, isr, ceros(neto),
                            ceros(-neto), coef, redondear(e.ingresos_acumulables), renta_ptu,
                            ptu, detalle, notas, xxx, fuentes)
