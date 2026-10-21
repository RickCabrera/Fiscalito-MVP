"""
Cuotas obrero-patronales del MES y del BIMESTRE de un trabajador (P4-10).

No duplica el motor: cada tramo se calcula con `cuotas.cuotas_empleado` (mismas tablas, mismo
redondeo por concepto, misma regla de días por ramo del §D3). Lo único que agrega este módulo
es partir el mes en TRAMOS con el SBC que estuvo vigente cada día (historial de SBC, Art. 30
LSS) y repartir en ellos los días de ausentismo e incapacidad.

QUÉ SE ENTERA CUÁNDO (Art. 39 LSS)
----------------------------------
- Mensual (EMA): RT, EyM (cuota fija, excedente, prestaciones en dinero, gastos médicos de
  pensionados), IyV y Guarderías.
- Bimestral (EBA): Retiro, CEAV e Infonavit — la suma de los dos meses del bimestre.
La periodicidad la declara cada `Ramo` de `tablas_imss.py`; aquí no se reclasifica nada.

DÍAS
----
Los días del mes son los NATURALES en que la relación estuvo vigente (alta y baja inclusive).

DECISIONES PROVISIONALES (marcadas también en `docs/decisiones-nomina.md` §D36)
-------------------------------------------------------------------------------
1. **Tope de ausentismo de 7 días por mes.** El SUA no descuenta más de 7 días de ausentismo
   en un mes (Art. 31 fr. I LSS). # FUENTE POR CONFIRMAR: el texto del Art. 31 no está
   transcrito en el repo (§D20). Es la dirección conservadora: con tope se cobra igual o MÁS
   que sin tope. Parámetro `tope_ausentismo` (None = sin tope, como el cálculo por periodo).
2. **Reparto de ausencias entre tramos.** Las incidencias de la nómina no traen fecha, sólo
   días. Se asignan al primer tramo del mes y lo que no cabe pasa al siguiente.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from app.constants import ZonaSalarioMinimo
from app.exceptions import FiscalValidationError
from app.nomina_engine.cuotas import CuotasEmpleado, DiasDelPeriodo, cuotas_empleado
from app.nomina_engine.integracion import clamp_sbc
from app.nomina_engine.tablas_imss import PeriodicidadCuota

TOPE_AUSENTISMO_MES = 7
CERO = Decimal("0.00")


@dataclass(frozen=True)
class TramoSBC:
    """El SBC declarado a partir de `desde` (hasta el siguiente tramo)."""

    desde: date
    sbc: Decimal


@dataclass(frozen=True)
class SegmentoMes:
    desde: date
    hasta: date
    sbc: Decimal
    dias: int
    dias_ausentismo: int
    dias_incapacidad: int
    cuotas: CuotasEmpleado


@dataclass(frozen=True)
class CuotaRamoMes:
    clave: str
    nombre: str
    periodicidad: PeriodicidadCuota
    patron: Decimal
    obrero: Decimal

    @property
    def total(self) -> Decimal:
        return self.patron + self.obrero


@dataclass(frozen=True)
class CuotasMes:
    """Las cuotas de un trabajador en un mes, con tramos y desglose por ramo."""

    anio: int
    mes: int
    dias: int
    dias_ausentismo: int
    dias_incapacidad: int
    sbc: Decimal
    segmentos: tuple[SegmentoMes, ...]
    ramos: tuple[CuotaRamoMes, ...]
    absorbio_cuota_obrera: bool
    avisos: tuple[str, ...] = field(default_factory=tuple)

    @property
    def dias_cotizados(self) -> int:
        """Días de los ramos que sí se reducen (IyV, RCV...): naturales − ausencias."""
        return self.dias - self.dias_ausentismo - self.dias_incapacidad

    def total(self, periodicidad: PeriodicidadCuota) -> Decimal:
        return sum((r.total for r in self.ramos if r.periodicidad is periodicidad), start=CERO)


def _ultimo_dia(anio: int, mes: int) -> date:
    return date(anio, mes, calendar.monthrange(anio, mes)[1])


def sbc_vigente(tramos: tuple[TramoSBC, ...], dia: date) -> Decimal | None:
    """El SBC del último tramo con `desde <= dia`."""
    vigente = None
    for t in sorted(tramos, key=lambda x: x.desde):
        if t.desde <= dia:
            vigente = t.sbc
    return vigente


def cuotas_del_mes(
    tramos: tuple[TramoSBC, ...],
    anio: int,
    mes: int,
    zona: ZonaSalarioMinimo,
    prima_riesgo: Decimal,
    *,
    alta: date | None = None,
    baja: date | None = None,
    dias_ausentismo: int = 0,
    dias_incapacidad: int = 0,
    tope_ausentismo: int | None = TOPE_AUSENTISMO_MES,
) -> CuotasMes | None:
    """
    Cuotas del mes. `None` si el trabajador no estuvo vigente ningún día del mes.

    Raises:
        FiscalValidationError: si hay días vigentes sin SBC declarado (no se inventa uno).
    """
    if not 1 <= mes <= 12:
        raise FiscalValidationError(f"Mes inválido: {mes}.")
    if dias_ausentismo < 0 or dias_incapacidad < 0:
        raise FiscalValidationError("Las ausencias no pueden ser negativas.")
    inicio, fin = date(anio, mes, 1), _ultimo_dia(anio, mes)
    desde = max(inicio, alta) if alta else inicio
    hasta = min(fin, baja) if baja else fin
    if desde > hasta:
        return None

    cortes = sorted({desde, *(t.desde for t in tramos if desde < t.desde <= hasta)})
    avisos: list[str] = []
    aus = dias_ausentismo
    if tope_ausentismo is not None and aus > tope_ausentismo:
        avisos.append(
            f"{anio}-{mes:02d}: {aus} días de ausentismo; se descuentan {tope_ausentismo} "
            "(tope mensual del SUA, Art. 31 fr. I LSS — POR CONFIRMAR)."
        )
        aus = tope_ausentismo
    inc = dias_incapacidad
    dias_mes = (hasta - desde).days + 1
    if aus + inc > dias_mes:
        avisos.append(
            f"{anio}-{mes:02d}: las ausencias ({aus} + {inc}) exceden los {dias_mes} días "
            "vigentes del mes; se acotan."
        )
        inc = min(inc, dias_mes)
        aus = min(aus, dias_mes - inc)
    aus_total, inc_total = aus, inc

    segmentos: list[SegmentoMes] = []
    for i, corte in enumerate(cortes):
        fin_seg = cortes[i + 1] - timedelta(days=1) if i + 1 < len(cortes) else hasta
        sbc = sbc_vigente(tramos, corte)
        if sbc is None:
            raise FiscalValidationError(
                f"No hay SBC declarado vigente al {corte.isoformat()}: captura el historial "
                "de SBC (alta) antes de calcular las cuotas."
            )
        dias = (fin_seg - corte).days + 1
        inc_seg = min(inc, dias)
        aus_seg = min(aus, dias - inc_seg)
        inc, aus = inc - inc_seg, aus - aus_seg
        acotado = clamp_sbc(sbc, corte, zona)
        cuotas = cuotas_empleado(
            acotado, DiasDelPeriodo(dias, aus_seg, inc_seg), corte, zona, prima_riesgo
        )
        segmentos.append(SegmentoMes(corte, fin_seg, acotado.valor, dias, aus_seg, inc_seg, cuotas))

    por_ramo: dict[str, CuotaRamoMes] = {}
    for s in segmentos:
        for r in s.cuotas.ramos:
            previo = por_ramo.get(r.clave)
            por_ramo[r.clave] = CuotaRamoMes(
                r.clave,
                r.nombre,
                r.periodicidad,
                (previo.patron if previo else CERO) + r.patron,
                (previo.obrero if previo else CERO) + r.obrero,
            )
    return CuotasMes(
        anio=anio,
        mes=mes,
        dias=dias_mes,
        dias_ausentismo=aus_total,
        dias_incapacidad=inc_total,
        sbc=segmentos[-1].sbc,
        segmentos=tuple(segmentos),
        ramos=tuple(por_ramo.values()),
        absorbio_cuota_obrera=any(s.cuotas.absorbio_cuota_obrera for s in segmentos),
        avisos=tuple(avisos),
    )


def meses_del_bimestre(bimestre: int) -> tuple[int, int]:
    """Bimestre 1 = enero-febrero ... 6 = noviembre-diciembre."""
    if not 1 <= bimestre <= 6:
        raise FiscalValidationError(f"Bimestre inválido: {bimestre} (1 a 6).")
    return 2 * bimestre - 1, 2 * bimestre


def ramos_bimestrales(meses: tuple[CuotasMes, ...]) -> tuple[CuotaRamoMes, ...]:
    """Retiro, CEAV e Infonavit sumados sobre los meses dados. No re-redondea (§D2)."""
    suma: dict[str, CuotaRamoMes] = {}
    for m in meses:
        for r in m.ramos:
            if r.periodicidad is not PeriodicidadCuota.BIMESTRAL:
                continue
            p = suma.get(r.clave)
            suma[r.clave] = CuotaRamoMes(
                r.clave,
                r.nombre,
                r.periodicidad,
                (p.patron if p else CERO) + r.patron,
                (p.obrero if p else CERO) + r.obrero,
            )
    return tuple(suma.values())
