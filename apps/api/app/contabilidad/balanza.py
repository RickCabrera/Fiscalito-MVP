"""
Balanza de comprobación, mayor y auxiliares (P2-04).

AGREGA EN SQL
-------------
Dos consultas agrupadas por cuenta afectable: saldo inicial (Σ cargo − Σ abono de todas las
pólizas activas ANTES de `desde`, más el saldo inicial capturado) y movimientos del periodo
(Σ cargos, Σ abonos de pólizas activas entre `desde` y `hasta`). Python sólo sube los
importes de cada cuenta afectable a sus ancestros (el catálogo cabe en memoria; los
movimientos no se leen uno por uno).

SALDOS CON SIGNO
----------------
Internamente todo es deudor positivo (cargo − abono). Para pintar, cada renglón separa su
saldo en columna deudora o acreedora según el signo, que es como el Anexo 24 pide la balanza
(SaldoIni / SaldoFin con la naturaleza de la cuenta) y como la lee un contador: una cuenta de
naturaleza deudora con saldo acreedor se ve en la columna acreedora, a la vista.

CUADRE
------
Σ saldo inicial = 0, Σ cargos = Σ abonos y Σ saldo final = 0 sobre las cuentas afectables (las
de nivel 1 suman lo mismo). Los saldos iniciales capturados pueden no cuadrar (es captura);
`cuadra` lo dice y `diferencias` enseña cuánto.

SALDOS INICIALES
----------------
Se capturan por cuenta afectable. Si la configuración tiene `fecha_saldos_iniciales`, sólo
cuentan para periodos que empiezan en esa fecha o después (antes de arrancar no hay saldo).

PÓLIZAS DE CIERRE Y APERTURA (P2-08)
------------------------------------
El cierre anual (`cierre.py`) deja una póliza con `origen = "cierre"` (31 de diciembre:
salda las cuentas de resultados contra el resultado del ejercicio) y una con
`origen = "apertura"` (1 de enero siguiente: traspasa el resultado del ejercicio a
resultados de ejercicios anteriores). Son el "periodo 13" y el "periodo 0" de la
contabilidad tradicional:
- La apertura fechada el mismo día en que empieza el periodo cuenta como SALDO INICIAL, no
  como movimiento: la balanza de enero arranca con los saldos ya traspasados.
- Con `incluir_cierre=False` (default) las pólizas de cierre y apertura que caen DENTRO del
  periodo no cuentan: diciembre (y el estado de resultados anual) se ven antes del cierre.
  Las anteriores al periodo siempre cuentan: así enero trae resultados en cero.
- Con `incluir_cierre=True` se ve la balanza de cierre (resultados en cero).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.contabilidad import catalogo
from app.contabilidad.asientos import CERO
from app.contabilidad.polizas import folio
from app.exceptions import FiscalAgentError
from app.modelos.cfdi import Comprobante
from app.modelos.contabilidad import (
    ConfigContable,
    CuentaContable,
    MovimientoPoliza,
    Poliza,
    SaldoInicial,
)
from app.modelos.nucleo import Cliente


@dataclass
class Totales:
    inicial: Decimal = CERO
    cargos: Decimal = CERO
    abonos: Decimal = CERO

    @property
    def final(self) -> Decimal:
        return self.inicial + self.cargos - self.abonos

    def sumar(self, otro: Totales) -> None:
        self.inicial += otro.inicial
        self.cargos += otro.cargos
        self.abonos += otro.abonos


def _dec(v: Any) -> Decimal:
    return Decimal(str(v or 0)).quantize(Decimal("0.01"))


def _saldos_capturados(db: Session, cliente: Cliente, desde: date) -> dict[int, Decimal]:
    config = db.get(ConfigContable, cliente.id)
    if config and config.fecha_saldos_iniciales and desde < config.fecha_saldos_iniciales:
        return {}
    filas = db.execute(select(SaldoInicial.cuenta_id, SaldoInicial.deudor - SaldoInicial.acreedor)
                       .where(SaldoInicial.cliente_id == cliente.id))
    return {cid: _dec(s) for cid, s in filas}


ORIGENES_CIERRE = ("cierre", "apertura")


def totales_por_cuenta(db: Session, cliente: Cliente, desde: date, hasta: date, *,
                       incluir_cierre: bool = False) -> dict[int, Totales]:
    """Totales de cada cuenta afectable con algo que decir (en SQL)."""
    activa = [Poliza.cliente_id == cliente.id, Poliza.estado == "activa"]
    apertura_inicial = (Poliza.origen == "apertura") & (Poliza.fecha == desde)
    antes = (Poliza.fecha < desde) | apertura_inicial
    en_periodo = (Poliza.fecha >= desde) & (Poliza.fecha <= hasta) & ~apertura_inicial
    if not incluir_cierre:
        en_periodo = en_periodo & Poliza.origen.not_in(ORIGENES_CIERRE)
    filas = db.execute(
        select(
            MovimientoPoliza.cuenta_id,
            func.sum(case((antes, MovimientoPoliza.cargo - MovimientoPoliza.abono), else_=0)),
            func.sum(case((en_periodo, MovimientoPoliza.cargo), else_=0)),
            func.sum(case((en_periodo, MovimientoPoliza.abono), else_=0)),
        )
        .join(Poliza, Poliza.id == MovimientoPoliza.poliza_id)
        .where(*activa, Poliza.fecha <= hasta)
        .group_by(MovimientoPoliza.cuenta_id)
    )
    salida = {cid: Totales(_dec(ini), _dec(car), _dec(abo)) for cid, ini, car, abo in filas}
    for cid, saldo in _saldos_capturados(db, cliente, desde).items():
        salida.setdefault(cid, Totales()).inicial += saldo
    return salida


def _columnas(saldo: Decimal) -> tuple[Decimal, Decimal]:
    return (saldo, CERO) if saldo >= 0 else (CERO, -saldo)


def _renglon(c: CuentaContable, t: Totales) -> dict[str, Any]:
    ini_d, ini_a = _columnas(t.inicial)
    fin_d, fin_a = _columnas(t.final)
    return {
        "cuenta_id": c.id, "numero": c.numero, "nombre": c.nombre, "nivel": c.nivel,
        "naturaleza": c.naturaleza, "tipo": c.tipo, "afectable": c.afectable,
        "codigo_agrupador": c.codigo_agrupador, "padre_id": c.padre_id,
        "saldo_inicial": f"{t.inicial:.2f}", "saldo_final": f"{t.final:.2f}",
        "inicial_deudor": f"{ini_d:.2f}", "inicial_acreedor": f"{ini_a:.2f}",
        "cargos": f"{t.cargos:.2f}", "abonos": f"{t.abonos:.2f}",
        "final_deudor": f"{fin_d:.2f}", "final_acreedor": f"{fin_a:.2f}",
    }


def balanza(db: Session, cliente: Cliente, desde: date, hasta: date, *, nivel: int | None = None,
            solo: str = "con_saldo_o_movimiento", incluir_cierre: bool = False) -> dict[str, Any]:
    """
    La balanza del rango. `nivel` = mostrar hasta ese nivel (None: todos). `solo`:
    `con_movimiento`, `con_saldo_o_movimiento` (default) o `todas`. `incluir_cierre`: ver
    PÓLIZAS DE CIERRE Y APERTURA arriba.
    """
    if desde > hasta:
        raise FiscalAgentError("'desde' no puede ser posterior a 'hasta'.", 422)
    cuentas = catalogo.cuentas(db, cliente)
    por_id = {c.id: c for c in cuentas}
    hojas = totales_por_cuenta(db, cliente, desde, hasta, incluir_cierre=incluir_cierre)
    acumulado: dict[int, Totales] = {c.id: Totales() for c in cuentas}
    total = Totales()
    deudor_ini = acreedor_ini = deudor_fin = acreedor_fin = CERO
    for cid, t in hojas.items():
        if cid not in por_id:
            continue
        total.sumar(t)
        di, ai = _columnas(t.inicial)
        df, af = _columnas(t.final)
        deudor_ini, acreedor_ini = deudor_ini + di, acreedor_ini + ai
        deudor_fin, acreedor_fin = deudor_fin + df, acreedor_fin + af
        actual: int | None = cid
        while actual is not None:  # sube a los ancestros
            acumulado[actual].sumar(t)
            actual = por_id[actual].padre_id
    renglones = []
    for c in cuentas:
        t = acumulado[c.id]
        if nivel is not None and c.nivel > nivel:
            continue
        movimiento = t.cargos != 0 or t.abonos != 0
        saldo = t.inicial != 0 or t.final != 0
        if solo == "con_movimiento" and not movimiento:
            continue
        if solo == "con_saldo_o_movimiento" and not (movimiento or saldo):
            continue
        renglones.append(_renglon(c, t))
    cuadra = total.inicial == 0 and total.cargos == total.abonos and total.final == 0
    return {
        "desde": desde.isoformat(), "hasta": hasta.isoformat(), "nivel": nivel,
        "incluir_cierre": incluir_cierre, "renglones": renglones,
        "totales": {
            "inicial_deudor": f"{deudor_ini:.2f}", "inicial_acreedor": f"{acreedor_ini:.2f}",
            "cargos": f"{total.cargos:.2f}", "abonos": f"{total.abonos:.2f}",
            "final_deudor": f"{deudor_fin:.2f}", "final_acreedor": f"{acreedor_fin:.2f}",
        },
        "cuadra": cuadra,
        "diferencias": {"saldo_inicial": f"{total.inicial:.2f}",
                        "movimientos": f"{total.cargos - total.abonos:.2f}",
                        "saldo_final": f"{total.final:.2f}"},
    }


def _ids_de_rama(db: Session, cliente: Cliente, cuenta: CuentaContable) -> list[int]:
    """La cuenta y todas sus descendientes."""
    hijos: dict[int | None, list[int]] = {}
    for c in catalogo.cuentas(db, cliente):
        hijos.setdefault(c.padre_id, []).append(c.id)
    salida, pila = [], [cuenta.id]
    while pila:
        cid = pila.pop()
        salida.append(cid)
        pila.extend(hijos.get(cid, []))
    return salida


def auxiliar(db: Session, cliente: Cliente, cuenta_id: int, desde: date, hasta: date,
             *, limite: int = 5000, incluir_cierre: bool = False) -> dict[str, Any]:
    """
    Mayor/auxiliar de una cuenta (con sus subcuentas): saldo inicial, cada movimiento del
    periodo con su póliza y saldo corrido, y saldo final. Cuadra con el renglón de la balanza.
    """
    if desde > hasta:
        raise FiscalAgentError("'desde' no puede ser posterior a 'hasta'.", 422)
    cuenta = catalogo.obtener(db, cliente, cuenta_id)
    ids = _ids_de_rama(db, cliente, cuenta)
    hojas = totales_por_cuenta(db, cliente, desde, hasta, incluir_cierre=incluir_cierre)
    inicial = sum((hojas[i].inicial for i in ids if i in hojas), CERO)
    cond = [Poliza.cliente_id == cliente.id, Poliza.estado == "activa",
            Poliza.fecha >= desde, Poliza.fecha <= hasta, MovimientoPoliza.cuenta_id.in_(ids),
            ~((Poliza.origen == "apertura") & (Poliza.fecha == desde))]
    if not incluir_cierre:
        cond.append(Poliza.origen.not_in(ORIGENES_CIERRE))
    filas = db.execute(
        select(Poliza, MovimientoPoliza, CuentaContable.numero, Comprobante.id)
        .join(MovimientoPoliza, MovimientoPoliza.poliza_id == Poliza.id)
        .join(CuentaContable, CuentaContable.id == MovimientoPoliza.cuenta_id)
        .outerjoin(Comprobante, (Comprobante.cliente_id == Poliza.cliente_id)
                   & (Comprobante.uuid == MovimientoPoliza.uuid_cfdi))
        .where(*cond)
        .order_by(Poliza.fecha, Poliza.tipo, Poliza.numero, MovimientoPoliza.orden)
        .limit(limite + 1)
    ).all()
    saldo = inicial
    cargos = abonos = CERO
    movimientos = []
    for p, m, numero, comp_id in filas[:limite]:
        saldo += m.cargo - m.abono
        cargos += m.cargo
        abonos += m.abono
        movimientos.append({
            "poliza_id": p.id, "folio": folio(p), "fecha": p.fecha.isoformat(),
            "tipo_poliza": p.tipo, "concepto": m.concepto or p.concepto, "cuenta": numero,
            "cargo": f"{m.cargo:.2f}", "abono": f"{m.abono:.2f}", "saldo": f"{saldo:.2f}",
            "uuid": m.uuid_cfdi, "rfc": m.rfc_tercero, "xml_disponible": comp_id is not None,
        })
    truncado = len(filas) > limite
    t = Totales(inicial, *(_suma_rama(hojas, ids)))
    return {
        "cuenta": catalogo.como_dict(cuenta), "desde": desde.isoformat(),
        "hasta": hasta.isoformat(), "saldo_inicial": f"{inicial:.2f}",
        "cargos": f"{t.cargos:.2f}", "abonos": f"{t.abonos:.2f}",
        "saldo_final": f"{t.final:.2f}", "movimientos": movimientos, "truncado": truncado,
    }


def _suma_rama(hojas: dict[int, Totales], ids: list[int]) -> tuple[Decimal, Decimal]:
    return (sum((hojas[i].cargos for i in ids if i in hojas), CERO),
            sum((hojas[i].abonos for i in ids if i in hojas), CERO))


# ── saldos iniciales ──


def saldos_iniciales(db: Session, cliente: Cliente) -> list[dict[str, Any]]:
    filas = db.execute(select(SaldoInicial, CuentaContable.numero, CuentaContable.nombre)
                       .join(CuentaContable, CuentaContable.id == SaldoInicial.cuenta_id)
                       .where(SaldoInicial.cliente_id == cliente.id)
                       .order_by(CuentaContable.numero)).all()
    return [{"cuenta_id": s.cuenta_id, "numero": n, "nombre": nom,
             "deudor": f"{s.deudor:.2f}", "acreedor": f"{s.acreedor:.2f}"} for s, n, nom in filas]


def guardar_saldos_iniciales(db: Session, cliente: Cliente,
                             saldos: list[tuple[int, Decimal, Decimal]]) -> dict[str, Any]:
    """Reemplaza los saldos de las cuentas dadas (0 y 0 lo quita). Devuelve los totales."""
    for cuenta_id, deudor, acreedor in saldos:
        cuenta = catalogo.obtener(db, cliente, cuenta_id)
        if not cuenta.afectable:
            raise FiscalAgentError(
                f"La cuenta {cuenta.numero} tiene subcuentas; captura el saldo en ellas.", 422)
        if deudor < 0 or acreedor < 0:
            raise FiscalAgentError("Los saldos iniciales no pueden ser negativos.", 422)
        previo = db.get(SaldoInicial, cuenta.id)
        if deudor == 0 and acreedor == 0:
            if previo is not None:
                db.delete(previo)
            continue
        if previo is None:
            previo = SaldoInicial(cuenta_id=cuenta.id, cliente_id=cliente.id)
            db.add(previo)
        previo.deudor, previo.acreedor = deudor, acreedor
    db.flush()
    deudor_t, acreedor_t = db.execute(
        select(func.coalesce(func.sum(SaldoInicial.deudor), 0),
               func.coalesce(func.sum(SaldoInicial.acreedor), 0))
        .where(SaldoInicial.cliente_id == cliente.id)).one()
    return {"deudor": f"{_dec(deudor_t):.2f}", "acreedor": f"{_dec(acreedor_t):.2f}",
            "cuadra": _dec(deudor_t) == _dec(acreedor_t)}
