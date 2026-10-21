"""
Personas morales: ingresos, deducciones y saldos desde la bóveda y la contabilidad (P3-01).
Salió de `personas_morales.py` por el tope de 300 líneas (P6-07); sólo se movió el código.
No calcula impuestos: suma importes para el motor puro `app/fiscal_engine/personas_morales.py`.

DE DÓNDE SALE CADA IMPORTE
--------------------------
- **Régimen general (601)** — ingresos acumulables y deducciones autorizadas, por mes:
  - `contabilidad` (P2): movimientos del mes de las cuentas de resultados. Ingresos = 401/402 +
    403 + 702 + 704 (abonos − cargos). Deducciones = costo (5xx), gastos (6xx) y otros gastos
    (701, 703) (cargos − abonos), SALVO las no deducibles: `NO_DEDUCIBLES` (PTU 607/610,
    participación en subsidiarias 608/609, ISR 611, no deducibles 612 y x.83/x.81, depreciación
    y amortización contables 504.07-504.24, 613, 614) y las que el despacho agregue. La
    deducción fiscal de inversiones (Arts. 31-38) se captura aparte.
  - `boveda`: CFDI vigentes por fecha de emisión (Art. 17 LISR: el ingreso se acumula al
    expedir el comprobante). Ingresos = emitidos I − emitidos E (las notas de crédito, que
    también aplican los anticipos). Deducciones = recibidos I − recibidos E sin UsoCFDI
    personal (D01-D10), sin efectos (S01, CN01) ni de inversión (I01-I08, que van a la
    deducción de inversiones), más la nómina emitida (gravado + `factor_exentos_nomina` ×
    exento, Art. 28 fr. XXX). DECISIÓN PROVISIONAL: la bóveda no distingue costo de lo vendido
    de compras (Art. 39); con inventarios, la contabilidad manda.
  - `auto` (default): contabilidad si el cliente tiene pólizas activas en el ejercicio.
- **RESICO PM** — flujo de efectivo (Arts. 207 y 210): los mismos CFDI por `flujo_del_mes`
  (PUE en su fecha, PPD por complemento de pago) y la nómina por fecha de pago.
- **No deducibles del Art. 28 fr. XXX para la renta gravable de PTU** (Art. 9 quinto párrafo)
  — capturado (`no_deducibles_art28_xxx`); si no, con contabilidad, la suma de las cuentas
  `cuentas_art28_xxx` del despacho (el código agrupador del SAT no tiene una cuenta propia
  para esto); con bóveda, (1 − `factor_exentos_nomina`) × exentos de la nómina emitida. Con
  contabilidad y sin cuentas designadas: cero y nota (no se baja la PTU sin dato).
- **Ajuste anual por inflación** — saldos de fin de mes de la contabilidad en las cuentas de
  créditos y deudas (`CREDITOS_DEFAULT`, `DEUDAS_DEFAULT`, por código agrupador; criterio del
  despacho configurable) o los 12 saldos capturados.

CUENTAS DE CRÉDITOS Y DEUDAS (Arts. 45 y 46 LISR) — DEFAULT, CRITERIO DEL DESPACHO
-------------------------------------------------------------------------------------
Créditos: 102 bancos, 103 inversiones, 104 instrumentos financieros, 105 clientes, 106 cuentas
por cobrar, 107 deudores diversos, 113 impuestos a favor, 186 cuentas por cobrar a largo plazo,
190 instrumentos financieros a largo plazo. Fuera: 101 caja (el efectivo en caja no es
crédito), 114 pagos provisionales, 118/119 IVA acreditable, 120 anticipo a proveedores
(DECISIÓN PROVISIONAL conservadora: no es un derecho a recibir numerario), 188 acciones.
Deudas: 201-208, 210-218 y 251-256 (incluye anticipos de clientes y contribuciones causadas);
fuera 209 (IVA trasladado no cobrado: aún no se causa). El 213 puede incluir ISR propio por
pagar, que el Art. 46 excluye (partida no deducible): se avisa en notas.
FUENTE POR CONFIRMAR: la lista exacta de exclusiones de los Arts. 45 y 46 contra el texto
vigente; por eso es configurable por cliente (`cuentas_creditos`, `cuentas_deudas`).
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
