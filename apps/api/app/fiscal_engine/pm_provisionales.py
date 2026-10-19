"""
Personas morales: pagos provisionales del régimen general (Art. 14 LISR) y de RESICO PM
(Art. 211). Parte de `personas_morales.py` (O11); fuentes y decisiones en su docstring.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from app.fiscal_engine.actualizacion import MODO_FACTOR_DEFAULT, ModoFactor, ajustar_a_pesos
from app.fiscal_engine.pm_perdidas import CERO, PerdidaPendiente, aplicar_perdidas, ceros, unicas
from app.redondeo import redondear

TASA_ISR_PM = Decimal("0.30")  # Art. 9 LISR, primer párrafo.
MESES_PTU = 8  # Art. 14 fr. II: partes iguales de mayo a diciembre.
PRIMER_MES_PTU = 5


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


# ── pagos provisionales ──


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
    # O12: INPC de fuente secundaria usados al actualizar las pérdidas de este pago.
    fuentes_por_confirmar: tuple[str, ...] = ()


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
    determinado = ceros(isr - pagos_ant - ret)
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
        perd, det = aplicar_perdidas(e.perdidas, e.anio, hasta, utilidad - ptu - est, e.modo)
        base = ceros(utilidad - ptu - est - perd)
        isr, deter, efe, cap = _cerrar_pago(e, mes, base, pagos_ant, ret_acum)
        salida.append(PagoProvisionalPM(
            mes, ing_mes, ing_acum, e.coeficiente, utilidad, ptu, est, perd, base, isr,
            pagos_ant, ret_acum, deter, efe, cap, ajustar_a_pesos(efe),
            fuentes_por_confirmar=unicas([x for p in det for x in p.fuentes_por_confirmar])))
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
        utilidad = ceros(ing_acum - ded_acum)
        # Art. 211: "la PTU pagada en el ejercicio" — completa desde el mes en que se paga.
        ptu = min(e.ptu_pagada if mes >= e.mes_pago_ptu else CERO, utilidad)
        est = min(_estimulos_mes(e.estimulos, mes), utilidad - ptu)
        hasta = (e.anio, 6) if mes >= 7 else None
        perd, det = aplicar_perdidas(e.perdidas, e.anio, hasta, utilidad - ptu - est, e.modo)
        base = ceros(utilidad - ptu - est - perd)
        isr, deter, efe, cap = _cerrar_pago(e, mes, base, pagos_ant, ret_acum)
        salida.append(PagoProvisionalPM(
            mes, ing_mes, ing_acum, CERO, utilidad, ptu, est, perd, base, isr, pagos_ant,
            ret_acum, deter, efe, cap, ajustar_a_pesos(efe), deducciones_acumuladas=ded_acum,
            fuentes_por_confirmar=unicas([x for p in det for x in p.fuentes_por_confirmar])))
        pagos_ant += efe
    return salida
