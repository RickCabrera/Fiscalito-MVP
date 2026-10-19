"""
Motor de personas morales: régimen general (601) y RESICO de personas morales (P3-01). Puro.

No lee la base: recibe importes ya sumados (los arma `app/impuestos/personas_morales.py` desde
la bóveda, la contabilidad P2 y los datos capturados) y devuelve cada paso del cálculo para
que el contador lo pueda rehacer a mano y los papeles de trabajo (P3-06) lo copien tal cual.

FUENTES (LISR vigente, texto de la Cámara de Diputados; ver `knowledge_base/16_personas_morales.md`)
---------------------------------------------------------------------------------------------
- **Art. 9** — tasa del 30 % sobre el resultado fiscal. Fr. I: utilidad fiscal = ingresos
  acumulables − deducciones autorizadas − PTU pagada en el ejercicio. Fr. II: a la utilidad
  fiscal se le restan las pérdidas pendientes de ejercicios anteriores. Penúltimo párrafo: la
  renta gravable para la PTU no disminuye la PTU pagada ni las pérdidas pendientes. Último
  párrafo: la anual se presenta dentro de los tres meses siguientes al cierre (marzo).
- **Art. 14** — pagos provisionales mensuales (día 17 del mes siguiente):
  - fr. I: coeficiente de utilidad = utilidad fiscal del último ejercicio de doce meses (más los
    anticipos y rendimientos del Art. 94 fr. II, cooperativas) entre sus ingresos nominales. Si
    ese ejercicio no dio coeficiente (pérdida), se usa el del último que lo tenga, sin que sea
    anterior en más de cinco años. El artículo NO actualiza el coeficiente.
  - fr. II: utilidad estimada = coeficiente × ingresos nominales del inicio del ejercicio al
    último día del mes; se disminuye la PTU pagada en el ejercicio **en partes iguales en los
    pagos de mayo a diciembre** (acumulativa, sin exceder la utilidad) y las pérdidas
    pendientes. Ingresos nominales = ingresos acumulables sin el ajuste anual por inflación
    acumulable.
  - fr. III: tasa del Art. 9 y se acreditan los pagos provisionales anteriores del ejercicio y
    las retenciones del Art. 54 (intereses pagados por el sistema financiero).
- **Arts. 44-46** — ajuste anual por inflación: saldo promedio anual de créditos y de deudas
  (suma de saldos al último día de cada mes ÷ meses del ejercicio); si deudas > créditos el
  ajuste es acumulable y si créditos > deudas es deducible; factor de ajuste anual = INPC del
  último mes del ejercicio ÷ INPC del último mes del ejercicio anterior − 1.
- **Art. 57** — pérdidas: se disminuyen en los diez ejercicios siguientes; primera
  actualización de julio a diciembre del ejercicio en que ocurrió; las siguientes desde el
  mes de la última actualización hasta el último mes de la primera mitad (junio) del ejercicio
  en que se aplican. Pérdida = deducciones − ingresos, aumentada con la PTU pagada.
- **Arts. 206-215 (Título VII, Cap. XII, RESICO PM)** — 207 ingresos efectivamente
  percibidos; 208 deducciones; 209 inversiones; 210 requisitos (efectivamente erogadas);
  **211 pagos provisionales**: ingresos percibidos − deducciones erogadas − PTU pagada en el
  ejercicio − pérdidas, por la tasa del Art. 9, menos pagos anteriores y retenciones del 54;
  **212 anual** conforme al Art. 9 con esos mismos flujos.
- **Art. 17-A CFF último párrafo** — factores y proporciones "hasta el diezmilésimo": se usa
  para el coeficiente de utilidad, los factores de actualización y el factor de ajuste anual,
  con el criterio de corte del cliente (`ModoFactor`, DP-3; default truncar, FUENTE POR
  CONFIRMAR, ver `actualizacion.py`).

CRITERIOS QUE NO DICE LA LEY (DECISIONES, todas señaladas en `notas`)
---------------------------------------------------------------------
- Pérdidas en pagos provisionales: en enero-junio se aplican con su última actualización y
  desde julio actualizadas a junio (el INPC de junio aún no existe en la primera mitad).
  DECISIÓN PROVISIONAL (la más conservadora: no se adelanta una actualización).
  FUENTE POR CONFIRMAR.
- PTU pagada después de mayo: la fracción acumulada de mayo a diciembre se empieza a disminuir
  en el pago del mes en que se pagó (no antes de pagarla). DECISIÓN PROVISIONAL.
- RESICO PM: los Arts. 206-215 no remiten al Art. 44; no se calcula ajuste anual por inflación
  salvo que el despacho lo pida (`aai_en_resico`). FUENTE POR CONFIRMAR.
- PTU a repartir: 10 % de la renta gravable (Resolución de la Comisión Nacional para la PTU,
  DOF 03/02/2009 — FUENTE POR CONFIRMAR contra la resolución vigente). La renta gravable sale
  del Art. 9 sin disminuir PTU pagada ni pérdidas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from app.fiscal_engine.actualizacion import (
    MODO_FACTOR_DEFAULT,
    ModoFactor,
    ajustar_a_pesos,
    cortar_diezmilesimo,
)
from app.fiscal_engine.inpc import inpc_para_actualizar
from app.redondeo import redondear

CERO = Decimal("0.00")
UNO = Decimal("1")
TASA_ISR_PM = Decimal("0.30")  # Art. 9 LISR, primer párrafo.
# FUENTE POR CONFIRMAR: Resolución de la Quinta Comisión Nacional para la PTU (DOF 03/02/2009).
PORCENTAJE_PTU = Decimal("0.10")
MESES_PTU = 8  # Art. 14 fr. II: partes iguales de mayo a diciembre.
PRIMER_MES_PTU = 5
ANIOS_PERDIDA = 10  # Art. 57 LISR.
ANIOS_COEFICIENTE = 5  # Art. 14 fr. I.

Mes = tuple[int, int]


def _mes_txt(m: Mes) -> str:
    return f"{m[0]}-{m[1]:02d}"


def _ceros(v: Decimal) -> Decimal:
    return v if v > 0 else CERO


# ── factores ──


@dataclass(frozen=True)
class FactorINPC:
    """Un factor INPC reciente ÷ antiguo, con sus índices para rehacerlo a mano."""

    factor: Decimal
    inpc_reciente: Decimal
    mes_reciente: str
    inpc_antiguo: Decimal
    mes_antiguo: str
    uso_ultimo_publicado: bool


def factor_inpc(reciente: Mes, antiguo: Mes, modo: ModoFactor = MODO_FACTOR_DEFAULT) -> FactorINPC:
    """INPC del mes más reciente ÷ INPC del más antiguo del periodo; nunca menor que 1."""
    r, ur = inpc_para_actualizar(*reciente)
    a, ua = inpc_para_actualizar(*antiguo)
    f = cortar_diezmilesimo(r.valor / a.valor, modo)
    return FactorINPC(max(f, UNO), r.valor, _mes_txt((r.anio, r.mes)), a.valor,
                      _mes_txt((a.anio, a.mes)), ur or ua)


def coeficiente_utilidad(
    utilidad_fiscal: Decimal, ingresos_nominales: Decimal, anticipos: Decimal = CERO,
    modo: ModoFactor = MODO_FACTOR_DEFAULT,
) -> Decimal:
    """Art. 14 fr. I: (utilidad fiscal + anticipos Art. 94 fr. II) ÷ ingresos nominales."""
    numerador = utilidad_fiscal + anticipos
    if ingresos_nominales <= 0 or numerador <= 0:
        return Decimal("0.0000")
    return cortar_diezmilesimo(numerador / ingresos_nominales, modo)


# ── pérdidas (Art. 57) ──


@dataclass(frozen=True)
class PerdidaPendiente:
    """Pérdida por amortizar. `actualizada_a` None = monto histórico, nunca actualizado."""

    ejercicio: int
    remanente: Decimal
    actualizada_a: Mes | None = None


@dataclass
class PerdidaAplicada:
    ejercicio: int
    remanente_inicial: Decimal
    factores: list[FactorINPC]
    actualizada: Decimal
    actualizada_a: str
    aplicada: Decimal = CERO
    remanente_final: Decimal = CERO
    vigente: bool = True
    nota: str = ""


def actualizar_perdida(
    p: PerdidaPendiente, anio: int, hasta: Mes | None, modo: ModoFactor
) -> PerdidaAplicada:
    """Actualiza la pérdida (Art. 57) hasta `hasta`; None = sólo la primera actualización."""
    if anio - p.ejercicio > ANIOS_PERDIDA or p.ejercicio >= anio:
        motivo = ("más de diez ejercicios: ya no se puede disminuir (Art. 57)"
                  if p.ejercicio < anio else "no es de un ejercicio anterior")
        return PerdidaAplicada(p.ejercicio, p.remanente, [], CERO, "", vigente=False,
                               nota=f"Pérdida de {p.ejercicio}: {motivo}.")
    monto, factores = p.remanente, []
    ultimo = p.actualizada_a
    if ultimo is None:
        f = factor_inpc((p.ejercicio, 12), (p.ejercicio, 7), modo)
        factores.append(f)
        monto, ultimo = redondear(monto * f.factor), (p.ejercicio, 12)
    if hasta is not None and hasta > ultimo:
        f = factor_inpc(hasta, ultimo, modo)
        factores.append(f)
        monto, ultimo = redondear(monto * f.factor), hasta
    return PerdidaAplicada(p.ejercicio, p.remanente, factores, monto, _mes_txt(ultimo))


def aplicar_perdidas(
    perdidas: list[PerdidaPendiente], anio: int, hasta: Mes | None, base: Decimal,
    modo: ModoFactor,
) -> tuple[Decimal, list[PerdidaAplicada]]:
    """Actualiza y disminuye las pérdidas de la más antigua a la más reciente, hasta la base."""
    disponible, total, detalle = _ceros(base), CERO, []
    for p in sorted(perdidas, key=lambda x: x.ejercicio):
        a = actualizar_perdida(p, anio, hasta, modo)
        if a.vigente:
            a.aplicada = min(a.actualizada, disponible)
            a.remanente_final = a.actualizada - a.aplicada
            disponible -= a.aplicada
            total += a.aplicada
        detalle.append(a)
    return total, detalle


# ── PTU ──


def ptu_disminuible_provisional(
    ptu_pagada: Decimal, mes: int, mes_pago: int = PRIMER_MES_PTU
) -> Decimal:
    """Art. 14 fr. II: octavos acumulados de mayo a diciembre (desde que se pagó)."""
    if ptu_pagada <= 0 or mes < PRIMER_MES_PTU or mes < mes_pago:
        return CERO
    return redondear(ptu_pagada * (mes - PRIMER_MES_PTU + 1) / MESES_PTU)


@dataclass(frozen=True)
class Estimulo:
    """Disminución de la utilidad (estímulo configurado por el despacho, con su fundamento)."""

    concepto: str
    importe: Decimal
    fundamento: str = ""
    desde_mes: int = 1
    en_provisionales: bool = True


# ── pagos provisionales del régimen general (Art. 14) ──


@dataclass
class PagoProvisionalPM:
    mes: int
    ingresos_mes: Decimal
    ingresos_acumulados: Decimal
    coeficiente: Decimal
    utilidad_estimada: Decimal
    ptu_disminuida: Decimal
    estimulos: Decimal
    perdidas: Decimal
    base: Decimal
    isr_causado: Decimal
    pagos_anteriores: Decimal
    retenciones: Decimal
    pago_determinado: Decimal
    pago_efectuado: Decimal
    pago_capturado: bool
    a_pagar_pesos: Decimal
    # RESICO PM: deducciones pagadas acumuladas (en el régimen general queda en cero).
    deducciones_acumuladas: Decimal = CERO


@dataclass
class EntradaProvisionales:
    anio: int
    hasta_mes: int
    ingresos_mes: dict[int, Decimal]
    coeficiente: Decimal = CERO
    ptu_pagada: Decimal = CERO
    mes_pago_ptu: int = PRIMER_MES_PTU
    perdidas: list[PerdidaPendiente] = field(default_factory=list)
    retenciones_mes: dict[int, Decimal] = field(default_factory=dict)
    pagos_efectuados: dict[int, Decimal] = field(default_factory=dict)
    estimulos: list[Estimulo] = field(default_factory=list)
    deducciones_mes: dict[int, Decimal] = field(default_factory=dict)  # sólo RESICO PM
    modo: ModoFactor = MODO_FACTOR_DEFAULT


def _estimulos_mes(estimulos: list[Estimulo], mes: int) -> Decimal:
    return sum((e.importe for e in estimulos if e.en_provisionales and mes >= e.desde_mes), CERO)


def _cerrar_pago(e: EntradaProvisionales, mes: int, base: Decimal,
                 pagos_ant: Decimal, ret: Decimal) -> tuple[Decimal, Decimal, Decimal, bool]:
    isr = redondear(base * TASA_ISR_PM)
    determinado = _ceros(isr - pagos_ant - ret)
    capturado = mes in e.pagos_efectuados
    efectuado = redondear(e.pagos_efectuados[mes]) if capturado else determinado
    return isr, determinado, efectuado, capturado


def pagos_provisionales_pm(e: EntradaProvisionales) -> list[PagoProvisionalPM]:
    """Pagos provisionales de enero a `hasta_mes` (Art. 14 LISR)."""
    salida: list[PagoProvisionalPM] = []
    ing_acum = ret_acum = pagos_ant = CERO
    for mes in range(1, e.hasta_mes + 1):
        ing_mes = redondear(e.ingresos_mes.get(mes, CERO))
        ing_acum += ing_mes
        ret_acum += redondear(e.retenciones_mes.get(mes, CERO))
        utilidad = redondear(ing_acum * e.coeficiente)
        ptu = min(ptu_disminuible_provisional(e.ptu_pagada, mes, e.mes_pago_ptu), utilidad)
        est = min(_estimulos_mes(e.estimulos, mes), utilidad - ptu)
        hasta = (e.anio, 6) if mes >= 7 else None
        perd, _ = aplicar_perdidas(e.perdidas, e.anio, hasta, utilidad - ptu - est, e.modo)
        base = _ceros(utilidad - ptu - est - perd)
        isr, det, efe, cap = _cerrar_pago(e, mes, base, pagos_ant, ret_acum)
        salida.append(PagoProvisionalPM(
            mes, ing_mes, ing_acum, e.coeficiente, utilidad, ptu, est, perd, base, isr,
            pagos_ant, ret_acum, det, efe, cap, ajustar_a_pesos(efe)))
        pagos_ant += efe
    return salida


def pagos_provisionales_resico_pm(e: EntradaProvisionales) -> list[PagoProvisionalPM]:
    """Art. 211 LISR: flujo acumulado (cobrado − pagado − PTU pagada − pérdidas) × 30 %."""
    salida: list[PagoProvisionalPM] = []
    ing_acum = ded_acum = ret_acum = pagos_ant = CERO
    for mes in range(1, e.hasta_mes + 1):
        ing_mes = redondear(e.ingresos_mes.get(mes, CERO))
        ing_acum += ing_mes
        ded_acum += redondear(e.deducciones_mes.get(mes, CERO))
        ret_acum += redondear(e.retenciones_mes.get(mes, CERO))
        utilidad = _ceros(ing_acum - ded_acum)
        # Art. 211: "la PTU pagada en el ejercicio" — completa desde el mes en que se paga.
        ptu = min(e.ptu_pagada if mes >= e.mes_pago_ptu else CERO, utilidad)
        est = min(_estimulos_mes(e.estimulos, mes), utilidad - ptu)
        hasta = (e.anio, 6) if mes >= 7 else None
        perd, _ = aplicar_perdidas(e.perdidas, e.anio, hasta, utilidad - ptu - est, e.modo)
        base = _ceros(utilidad - ptu - est - perd)
        isr, det, efe, cap = _cerrar_pago(e, mes, base, pagos_ant, ret_acum)
        salida.append(PagoProvisionalPM(
            mes, ing_mes, ing_acum, CERO, utilidad, ptu, est, perd, base, isr, pagos_ant,
            ret_acum, det, efe, cap, ajustar_a_pesos(efe), deducciones_acumuladas=ded_acum))
        pagos_ant += efe
    return salida


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
        notas.append(f"El INPC de {_mes_txt(ultimo)} aún no se publica: el factor usa el último "
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

    def importe(self, clave: str) -> Decimal:
        return next(r.importe for r in self.renglones if r.clave == clave)


def anual_pm(e: EntradaAnual, *, resico: bool = False) -> ResultadoAnualPM:
    """Impuesto del ejercicio de una persona moral (Art. 9; RESICO PM: Art. 212)."""
    aai_acum = e.aai.acumulable if e.aai else CERO
    aai_ded = e.aai.deducible if e.aai else CERO
    ingresos = redondear(e.ingresos_acumulables + aai_acum)
    deducciones = redondear(e.deducciones_autorizadas + aai_ded)
    antes_ptu = ingresos - deducciones
    utilidad_neta = antes_ptu - e.ptu_pagada
    utilidad = _ceros(utilidad_neta)
    perdida = _ceros(-utilidad_neta)  # Art. 57: la pérdida se aumenta con la PTU pagada.
    est = min(sum((x.importe for x in e.estimulos), CERO), utilidad)
    perd, detalle = aplicar_perdidas(e.perdidas, e.anio, (e.anio, 6), utilidad - est, e.modo)
    resultado = _ceros(utilidad - est - perd)
    isr = redondear(resultado * TASA_ISR_PM)
    neto = isr - e.pagos_provisionales - e.retenciones
    art = "Art. 212" if resico else "Art. 9"
    ingreso_txt = ("Ingresos efectivamente percibidos (Art. 207)" if resico
                   else "Ingresos acumulables (sin ajuste por inflación)")
    deduccion_txt = ("Deducciones autorizadas efectivamente erogadas (Arts. 208-210)" if resico
                     else "Deducciones autorizadas")
    r = [
        Renglon("ingresos", ingreso_txt, redondear(e.ingresos_acumulables),
                "Art. 207 LISR" if resico else "Arts. 16, 17 y 18 LISR"),
        Renglon("aai_acumulable", "Ajuste anual por inflación acumulable", aai_acum, "Art. 44"),
        Renglon("ingresos_totales", "Total de ingresos acumulables", ingresos, art),
        Renglon("deducciones", deduccion_txt, redondear(e.deducciones_autorizadas),
                "Arts. 208-210 LISR" if resico else "Arts. 25, 27 y 28 LISR"),
        Renglon("aai_deducible", "Ajuste anual por inflación deducible", aai_ded, "Art. 44"),
        Renglon("deducciones_totales", "Total de deducciones autorizadas", deducciones, art),
        Renglon("utilidad_antes_ptu", "Utilidad (pérdida) antes de PTU", antes_ptu, art),
        Renglon("ptu_pagada", "PTU pagada en el ejercicio", e.ptu_pagada, "Art. 9 fr. I"),
        Renglon("utilidad_fiscal", "Utilidad fiscal", utilidad, "Art. 9 fr. I"),
        Renglon("perdida_fiscal", "Pérdida fiscal del ejercicio", perdida, "Art. 57"),
        Renglon("estimulos", "Estímulos que disminuyen la utilidad", est, "Configurado"),
        Renglon("perdidas_aplicadas", "Pérdidas de ejercicios anteriores aplicadas", perd,
                "Arts. 9 fr. II y 57"),
        Renglon("resultado_fiscal", "Resultado fiscal", resultado, "Art. 9 fr. II"),
        Renglon("isr_ejercicio", "ISR del ejercicio (30 %)", isr, "Art. 9"),
        Renglon("pagos_provisionales", "Pagos provisionales efectuados", e.pagos_provisionales,
                "Art. 211" if resico else "Art. 14"),
        Renglon("retenciones", "ISR retenido por el sistema financiero", e.retenciones,
                "Art. 54"),
        Renglon("a_cargo", "ISR a cargo", _ceros(neto), "Art. 76 fr. V"),
        Renglon("a_favor", "ISR a favor", _ceros(-neto), "Art. 22 CFF"),
    ]
    renta_ptu = _ceros(antes_ptu)
    ptu = redondear(renta_ptu * PORCENTAJE_PTU)
    coef = CERO if resico else coeficiente_utilidad(
        utilidad, e.ingresos_acumulables, e.anticipos_miembros, e.modo)
    notas = list(e.aai.notas if e.aai else [])
    notas += [p.nota for p in detalle if p.nota]
    if est and est < sum((x.importe for x in e.estimulos), CERO):
        notas.append("Los estímulos se limitaron a la utilidad fiscal del ejercicio.")
    return ResultadoAnualPM(e.anio, r, utilidad, perdida, resultado, isr, _ceros(neto),
                            _ceros(-neto), coef, redondear(e.ingresos_acumulables), renta_ptu,
                            ptu, detalle, notas)


# ── serialización ──


def _t(v: Decimal) -> str:
    return f"{v:.2f}"


def factor_dict(f: FactorINPC) -> dict[str, object]:
    return {"factor": f"{f.factor:.4f}", "inpc_reciente": str(f.inpc_reciente),
            "mes_reciente": f.mes_reciente, "inpc_antiguo": str(f.inpc_antiguo),
            "mes_antiguo": f.mes_antiguo, "uso_ultimo_publicado": f.uso_ultimo_publicado}


def pago_dict(p: PagoProvisionalPM) -> dict[str, object]:
    return {
        "mes": p.mes, "ingresos_mes": _t(p.ingresos_mes),
        "ingresos_acumulados": _t(p.ingresos_acumulados),
        "deducciones_acumuladas": _t(p.deducciones_acumuladas),
        "coeficiente": f"{p.coeficiente:.4f}", "utilidad_estimada": _t(p.utilidad_estimada),
        "ptu_disminuida": _t(p.ptu_disminuida), "estimulos": _t(p.estimulos),
        "perdidas": _t(p.perdidas), "base": _t(p.base), "isr_causado": _t(p.isr_causado),
        "pagos_anteriores": _t(p.pagos_anteriores), "retenciones": _t(p.retenciones),
        "pago_determinado": _t(p.pago_determinado), "pago_efectuado": _t(p.pago_efectuado),
        "pago_capturado": p.pago_capturado, "a_pagar_pesos": _t(p.a_pagar_pesos),
    }


def perdida_dict(p: PerdidaAplicada) -> dict[str, object]:
    return {"ejercicio": p.ejercicio, "remanente_inicial": _t(p.remanente_inicial),
            "factores": [factor_dict(f) for f in p.factores], "actualizada": _t(p.actualizada),
            "actualizada_a": p.actualizada_a, "aplicada": _t(p.aplicada),
            "remanente_final": _t(p.remanente_final), "vigente": p.vigente, "nota": p.nota}


def aai_dict(a: ResultadoAAI) -> dict[str, object]:
    return {
        "saldos_creditos": [_t(x) for x in a.saldos_creditos],
        "saldos_deudas": [_t(x) for x in a.saldos_deudas],
        "promedio_creditos": _t(a.promedio_creditos), "promedio_deudas": _t(a.promedio_deudas),
        "factor": factor_dict(a.factor) if a.factor else None,
        "factor_ajuste": f"{a.factor_ajuste:.4f}", "acumulable": _t(a.acumulable),
        "deducible": _t(a.deducible), "notas": a.notas,
    }


def renglon_dict(r: Renglon) -> dict[str, str]:
    return {"clave": r.clave, "concepto": r.concepto, "importe": _t(r.importe),
            "fundamento": r.fundamento}
