"""
Personas morales: constantes y lectura de las fuentes del cálculo —bóveda (devengado y
flujo) y contabilidad (cuentas fiscales, saldos para el ajuste anual por inflación)—.

Salió de `impuestos/personas_morales.py` en P6-05 (tope de 300 líneas) sin cambiar nada;
ese módulo lo importa.
"""

from __future__ import annotations

from calendar import monthrange
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.boveda_cfdi.servicio import comprobantes_vigentes
from app.contabilidad import catalogo
from app.contabilidad.balanza import totales_por_cuenta
from app.contabilidad.reportes import seccion
from app.impuestos.flujo import Efectivo, flujo_del_mes, nominas_del_mes
from app.impuestos.servicio import USOS_NO_ACREDITABLES
from app.modelos.cfdi import Comprobante
from app.modelos.contabilidad import CuentaContable, Poliza
from app.modelos.nucleo import Cliente
from app.redondeo import redondear
from app.schemas.personas_morales import DatosAnualesPMSchema

CERO = Decimal("0.00")
MESES = range(1, 13)
CREDITOS_DEFAULT = ("102", "103", "104", "105", "106", "107", "113", "186", "190")
DEUDAS_DEFAULT = ("201", "202", "203", "204", "205", "206", "207", "208", "210", "211", "212",
                  "213", "214", "215", "216", "217", "218", "251", "252", "253", "254", "255",
                  "256")
NO_DEDUCIBLES = (
    ("601.83", "602.83", "603.81", "604.81", "607", "608", "609", "610", "611", "612", "613",
     "614") + tuple(f"504.{n:02d}" for n in range(7, 25))
)
USOS_INVERSION = {f"I{n:02d}" for n in range(1, 9)}
SECCIONES_INGRESO = ("ingresos", "otros_ingresos")
SECCIONES_DEDUCCION = ("costo", "gastos", "otros_gastos", "impuestos")


def _prefijo(codigo: str, lista: Iterable[str]) -> bool:
    return any(codigo == p or codigo.startswith(p + ".") for p in lista)



# ── bóveda ──


def _rango(anio: int) -> tuple[datetime, datetime]:
    return datetime(anio, 1, 1), datetime(anio + 1, 1, 1)


def _pesos(c: Comprobante, importe: Decimal) -> Decimal:
    if c.moneda not in ("MXN", "XXX", "") and c.tipo_cambio:
        return importe * c.tipo_cambio
    return importe


def _dec(v: object) -> Decimal:
    try:
        return Decimal(str(v)) if v not in (None, "") else Decimal("0")
    except Exception:  # noqa: BLE001 - importe ilegible: cuenta como cero
        return Decimal("0")


def _deducible_nomina(c: Comprobante, factor: Decimal) -> Decimal:
    p = (c.datos or {}).get("nomina", {}).get("percepciones", {})
    return _dec(p.get("TotalGravado")) + factor * _dec(p.get("TotalExento"))


def _no_deducible_nomina(c: Comprobante, factor: Decimal) -> Decimal:
    """Art. 28 fr. XXX: la parte del exento que NO se dedujo (1 − factor)."""
    p = (c.datos or {}).get("nomina", {}).get("percepciones", {})
    return (1 - factor) * _dec(p.get("TotalExento"))


def art28_xxx_boveda(db: Session, cliente: Cliente, anio: int, d: DatosAnualesPMSchema
                     ) -> Decimal:
    """No deducible del Art. 28 fr. XXX de la nómina emitida del ejercicio (bóveda)."""
    total = sum((_no_deducible_nomina(n, d.factor_exentos_nomina)
                 for m in MESES for n in nominas_del_mes(db, cliente, anio, m)), CERO)
    return redondear(total)


def _es_deduccion(c: Comprobante) -> bool:
    uso = (c.uso_cfdi or "").upper()
    return uso not in USOS_NO_ACREDITABLES and uso not in USOS_INVERSION


def boveda_devengada(
    db: Session, cliente: Cliente, anio: int, d: DatosAnualesPMSchema
) -> tuple[dict[int, Decimal], dict[int, Decimal]]:
    """(ingresos, deducciones) por mes por fecha de emisión (Art. 17 LISR)."""
    ini, fin = _rango(anio)
    comps = db.scalars(comprobantes_vigentes(select(Comprobante).where(
        Comprobante.cliente_id == cliente.id, Comprobante.tipo.in_(("I", "E")),
        Comprobante.fecha >= ini, Comprobante.fecha < fin)))
    ing = {m: CERO for m in MESES}
    ded = {m: CERO for m in MESES}
    for c in comps:
        signo = -1 if c.tipo == "E" else 1
        neto = _pesos(c, c.subtotal - c.descuento) * signo
        if c.direccion == "emitido":
            ing[c.fecha.month] += neto
        elif _es_deduccion(c):
            ded[c.fecha.month] += neto
    for m in MESES:
        for n in nominas_del_mes(db, cliente, anio, m):
            ded[m] += _deducible_nomina(n, d.factor_exentos_nomina)
    return ({m: redondear(v) for m, v in ing.items()}, {m: redondear(v) for m, v in ded.items()})


def _neto_flujo(e: Efectivo) -> Decimal:
    c = e.comprobante
    return (c.subtotal - c.descuento) * e.factor_pesos * (-1 if c.tipo == "E" else 1)


def boveda_flujo(
    db: Session, cliente: Cliente, anio: int, d: DatosAnualesPMSchema
) -> tuple[dict[int, Decimal], dict[int, Decimal]]:
    """(ingresos cobrados, deducciones pagadas) por mes (RESICO PM, Arts. 207 y 210)."""
    ing = {m: CERO for m in MESES}
    ded = {m: CERO for m in MESES}
    for m in MESES:
        for e in flujo_del_mes(db, cliente, anio, m):
            if e.comprobante.direccion == "emitido":
                ing[m] += _neto_flujo(e)
            elif _es_deduccion(e.comprobante):
                ded[m] += _neto_flujo(e)
        for n in nominas_del_mes(db, cliente, anio, m):
            ded[m] += _deducible_nomina(n, d.factor_exentos_nomina)
    return ({m: redondear(v) for m, v in ing.items()}, {m: redondear(v) for m, v in ded.items()})


# ── contabilidad ──


def hay_polizas(db: Session, cliente: Cliente, anio: int) -> bool:
    return bool(db.scalar(select(func.count(Poliza.id)).where(
        Poliza.cliente_id == cliente.id, Poliza.estado == "activa",
        Poliza.fecha >= date(anio, 1, 1), Poliza.fecha <= date(anio, 12, 31))))


def _fin(anio: int, mes: int) -> date:
    return date(anio, mes, monthrange(anio, mes)[1])


@dataclass
class CuentaFiscal:
    numero: str
    nombre: str
    codigo: str
    clase: str  # ingreso | deduccion | no_deducible
    meses: dict[int, Decimal] = field(default_factory=lambda: {m: CERO for m in MESES})

    @property
    def total(self) -> Decimal:
        return sum(self.meses.values(), CERO)


def clase_cuenta(c: CuentaContable, no_deducibles: Iterable[str]) -> str | None:
    """Clase fiscal de una cuenta de resultados, o None si no es de resultados."""
    sec = seccion(c)
    codigo = c.codigo_agrupador or ""
    if sec in SECCIONES_INGRESO:
        return "ingreso"
    if sec not in SECCIONES_DEDUCCION:
        return None
    extra = list(no_deducibles)
    if (sec == "impuestos" or _prefijo(codigo, NO_DEDUCIBLES) or _prefijo(codigo, extra)
            or c.numero in extra):
        return "no_deducible"
    return "deduccion"


def contabilidad_por_mes(
    db: Session, cliente: Cliente, anio: int, d: DatosAnualesPMSchema
) -> list[CuentaFiscal]:
    """Movimientos del mes de cada cuenta de resultados, con su clase fiscal."""
    cuentas = {c.id: c for c in catalogo.cuentas(db, cliente)}
    salida: dict[int, CuentaFiscal] = {}
    for m in MESES:
        for cid, t in totales_por_cuenta(db, cliente, date(anio, m, 1), _fin(anio, m)).items():
            c = cuentas.get(cid)
            clase = clase_cuenta(c, [*d.cuentas_no_deducibles, *d.cuentas_art28_xxx]
                                 ) if c else None
            if clase is None:
                continue
            importe = t.abonos - t.cargos if clase == "ingreso" else t.cargos - t.abonos
            if cid not in salida:
                salida[cid] = CuentaFiscal(c.numero, c.nombre, c.codigo_agrupador, clase)
            salida[cid].meses[m] += importe
    return sorted(salida.values(), key=lambda x: x.numero)


def saldos_aai(
    db: Session, cliente: Cliente, anio: int, d: DatosAnualesPMSchema, fuente: str
) -> tuple[list[Decimal], list[Decimal], str]:
    """Saldos de fin de mes de créditos y deudas: capturados o de la contabilidad."""
    if d.saldos_creditos:
        return list(d.saldos_creditos), list(d.saldos_deudas), "capturados"
    if fuente != "contabilidad":
        return [], [], "sin datos"
    cuentas = {c.id: c for c in catalogo.cuentas(db, cliente)}
    cred_pref = d.cuentas_creditos or list(CREDITOS_DEFAULT)
    deud_pref = d.cuentas_deudas or list(DEUDAS_DEFAULT)
    creditos, deudas = [], []
    for m in MESES:
        sc = sd = CERO
        for cid, t in totales_por_cuenta(db, cliente, date(anio, m, 1), _fin(anio, m)).items():
            c = cuentas.get(cid)
            codigo = (c.codigo_agrupador if c else "") or ""
            if _prefijo(codigo, cred_pref):
                sc += t.final
            elif _prefijo(codigo, deud_pref):
                sd -= t.final  # acreedora: saldo deudor negativo
        creditos.append(redondear(sc))
        deudas.append(redondear(sd))
    return creditos, deudas, "contabilidad"
