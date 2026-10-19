"""
Catálogo de cuentas por cliente (P2-01): catálogo base sembrable y CRUD con validaciones.

NUMERACIÓN DEL CATÁLOGO BASE
----------------------------
Las cuentas de nivel 1 y 2 llevan el mismo número que su código agrupador (`102`,
`102.01`) y las de nivel 3 agregan un consecutivo (`102.01.01`). El despacho puede usar
cualquier otra numeración en las cuentas que agregue: el número es texto libre y único por
cliente; lo que se valida es la jerarquía.

REGLAS
------
- El nivel lo dicta el padre (nivel del padre + 1; sin padre, 1). Si se manda un nivel que
  no coincide, se rechaza en vez de corregirlo en silencio.
- El código agrupador debe existir en el Anexo 24 y no ser un encabezado de rubro.
- Una cuenta con subcuentas NO es afectable (no recibe movimientos). Agregar la primera
  subcuenta a una cuenta afectable la vuelve acumulativa, salvo que ya tenga movimientos o
  saldo inicial: entonces se rechaza, porque esos importes quedarían colgados del padre.
- No se borra una cuenta con subcuentas, con movimientos (aunque sean de pólizas
  canceladas: la historia se conserva) o que use la configuración de pólizas automáticas.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.contabilidad import agrupador
from app.exceptions import FiscalAgentError
from app.modelos.contabilidad import (
    ConfigContable,
    CuentaContable,
    MovimientoPoliza,
    ReglaEgreso,
    SaldoInicial,
)
from app.modelos.nucleo import Cliente

NATURALEZAS = ("deudora", "acreedora")
TIPOS = ("activo", "pasivo", "capital", "ingreso", "costo", "gasto", "orden")


@dataclass(frozen=True)
class CuentaBase:
    """Una cuenta del catálogo base. `nombre` vacío = el nombre del agrupador."""

    numero: str
    agrupador: str
    nombre: str = ""


# Catálogo estándar mexicano con las subcuentas que usan las pólizas automáticas. Cada
# número de nivel 1-2 ES su código agrupador; los de nivel 3 cuelgan del de nivel 2.
CATALOGO_BASE: tuple[CuentaBase, ...] = (
    # ── Activo circulante ──
    CuentaBase("101", "101"), CuentaBase("101.01", "101.01", "Caja general"),
    CuentaBase("102", "102"), CuentaBase("102.01", "102.01"),
    CuentaBase("102.01.01", "102.01", "Banco principal"),
    CuentaBase("102.02", "102.02"),
    CuentaBase("103", "103"), CuentaBase("103.01", "103.01"),
    CuentaBase("105", "105"), CuentaBase("105.01", "105.01"), CuentaBase("105.02", "105.02"),
    CuentaBase("107", "107"), CuentaBase("107.01", "107.01"), CuentaBase("107.05", "107.05"),
    CuentaBase("110", "110"), CuentaBase("110.01", "110.01"),
    CuentaBase("113", "113"),
    CuentaBase("113.01", "113.01", "IVA a favor (incluye IVA retenido por clientes)"),
    CuentaBase("113.02", "113.02", "ISR a favor (incluye ISR retenido por clientes)"),
    CuentaBase("113.08", "113.08"),
    CuentaBase("114", "114"), CuentaBase("114.01", "114.01"),
    CuentaBase("115", "115"), CuentaBase("115.01", "115.01"),
    CuentaBase("118", "118"), CuentaBase("118.01", "118.01"),
    CuentaBase("119", "119"), CuentaBase("119.01", "119.01"),
    CuentaBase("120", "120"), CuentaBase("120.01", "120.01"),
    # ── Activo fijo ──
    CuentaBase("151", "151"), CuentaBase("151.01", "151.01"),
    CuentaBase("152", "152"), CuentaBase("152.01", "152.01"),
    CuentaBase("153", "153"), CuentaBase("153.01", "153.01"),
    CuentaBase("154", "154"), CuentaBase("154.01", "154.01", "Equipo de transporte"),
    CuentaBase("155", "155"), CuentaBase("155.01", "155.01"),
    CuentaBase("156", "156"), CuentaBase("156.01", "156.01"),
    CuentaBase("160", "160"), CuentaBase("160.01", "160.01"),
    CuentaBase("171", "171"),
    CuentaBase("171.02", "171.02"), CuentaBase("171.03", "171.03",
                                               "Depreciación acumulada de equipo de transporte"),
    CuentaBase("171.04", "171.04"), CuentaBase("171.05", "171.05"),
    CuentaBase("184", "184"), CuentaBase("184.03", "184.03"),
    # ── Pasivo ──
    CuentaBase("201", "201"), CuentaBase("201.01", "201.01"), CuentaBase("201.02", "201.02"),
    CuentaBase("205", "205"), CuentaBase("205.02", "205.02"), CuentaBase("205.06", "205.06"),
    CuentaBase("206", "206"), CuentaBase("206.01", "206.01"),
    CuentaBase("208", "208"), CuentaBase("208.01", "208.01"), CuentaBase("208.02", "208.02"),
    CuentaBase("209", "209"), CuentaBase("209.01", "209.01"), CuentaBase("209.02", "209.02"),
    CuentaBase("210", "210"), CuentaBase("210.01", "210.01"),
    CuentaBase("211", "211"), CuentaBase("211.01", "211.01"),
    CuentaBase("213", "213"), CuentaBase("213.01", "213.01"), CuentaBase("213.03", "213.03"),
    CuentaBase("216", "216"),
    CuentaBase("216.01", "216.01"), CuentaBase("216.02", "216.02"),
    CuentaBase("216.03", "216.03"), CuentaBase("216.04", "216.04"),
    CuentaBase("216.10", "216.10"), CuentaBase("216.11", "216.11"),
    # ── Capital ──
    CuentaBase("301", "301"), CuentaBase("301.01", "301.01"), CuentaBase("301.02", "301.02"),
    CuentaBase("304", "304"), CuentaBase("304.01", "304.01"), CuentaBase("304.02", "304.02"),
    CuentaBase("305", "305"), CuentaBase("305.01", "305.01"), CuentaBase("305.02", "305.02"),
    # ── Ingresos ──
    CuentaBase("401", "401"), CuentaBase("401.01", "401.01"), CuentaBase("401.04", "401.04"),
    CuentaBase("401.07", "401.07"),
    CuentaBase("402", "402"), CuentaBase("402.01", "402.01"),
    CuentaBase("403", "403"), CuentaBase("403.01", "403.01"),
    # ── Costos ──
    CuentaBase("501", "501"), CuentaBase("501.01", "501.01"),
    # ── Gastos ──
    CuentaBase("601", "601"),
    CuentaBase("601.01", "601.01"), CuentaBase("601.26", "601.26"),
    CuentaBase("601.31", "601.31"), CuentaBase("601.34", "601.34"),
    CuentaBase("601.38", "601.38"), CuentaBase("601.45", "601.45"),
    CuentaBase("601.46", "601.46"), CuentaBase("601.48", "601.48"),
    CuentaBase("601.49", "601.49"), CuentaBase("601.50", "601.50"),
    CuentaBase("601.52", "601.52"), CuentaBase("601.55", "601.55"),
    CuentaBase("601.56", "601.56"), CuentaBase("601.57", "601.57"),
    CuentaBase("601.61", "601.61"), CuentaBase("601.83", "601.83"),
    CuentaBase("601.84", "601.84"),
    CuentaBase("602", "602"), CuentaBase("602.84", "602.84"),
    CuentaBase("603", "603"), CuentaBase("603.82", "603.82"),
    CuentaBase("613", "613"), CuentaBase("613.05", "613.05"),
    # ── Resultado integral de financiamiento ──
    CuentaBase("701", "701"), CuentaBase("701.10", "701.10"), CuentaBase("701.11", "701.11"),
    CuentaBase("702", "702"), CuentaBase("702.04", "702.04"), CuentaBase("702.10", "702.10"),
    CuentaBase("703", "703"), CuentaBase("703.21", "703.21"),
    CuentaBase("704", "704"), CuentaBase("704.23", "704.23"),
)


def _padre_numero(numero: str) -> str | None:
    return numero.rsplit(".", 1)[0] if "." in numero else None


# ── consultas ──


def cuentas(db: Session, cliente: Cliente) -> list[CuentaContable]:
    """Todas las cuentas del cliente, en orden de número."""
    return list(db.scalars(
        select(CuentaContable).where(CuentaContable.cliente_id == cliente.id)
        .order_by(CuentaContable.numero)
    ))


def por_numero(db: Session, cliente: Cliente) -> dict[str, CuentaContable]:
    return {c.numero: c for c in cuentas(db, cliente)}


def obtener(db: Session, cliente: Cliente, cuenta_id: int) -> CuentaContable:
    """La cuenta del cliente, o 404 (una cuenta de otro cliente también es 404)."""
    cuenta = db.scalar(select(CuentaContable).where(
        CuentaContable.id == cuenta_id, CuentaContable.cliente_id == cliente.id))
    if cuenta is None:
        raise FiscalAgentError("No existe esa cuenta en el catálogo de este cliente.", 404)
    return cuenta


def tiene_movimientos(db: Session, cuenta_id: int) -> bool:
    return db.scalar(select(func.count(MovimientoPoliza.id))
                     .where(MovimientoPoliza.cuenta_id == cuenta_id)) not in (None, 0)


def _tiene_saldo_inicial(db: Session, cuenta_id: int) -> bool:
    si = db.get(SaldoInicial, cuenta_id)
    return si is not None and (si.deudor != 0 or si.acreedor != 0)


def _tiene_hijas(db: Session, cuenta_id: int) -> bool:
    return db.scalar(select(func.count(CuentaContable.id))
                     .where(CuentaContable.padre_id == cuenta_id)) not in (None, 0)


# ── sembrar ──


def sembrar_base(db: Session, cliente: Cliente) -> int:
    """
    Agrega al catálogo del cliente las cuentas base que le falten. Idempotente.

    No toca las que ya existen (ni su nombre): el catálogo ya es del despacho.
    """
    existentes = por_numero(db, cliente)
    creadas = 0
    numeros_con_hijas = {_padre_numero(b.numero) for b in CATALOGO_BASE}
    for base in CATALOGO_BASE:
        if base.numero in existentes:
            continue
        codigo = agrupador.obtener(base.agrupador)
        if codigo is None or not codigo.asignable:
            raise ValueError(f"Código agrupador inválido en el catálogo base: {base.agrupador}")
        padre = existentes.get(_padre_numero(base.numero) or "")
        cuenta = CuentaContable(
            cliente_id=cliente.id, numero=base.numero, nombre=base.nombre or codigo.nombre,
            nivel=(padre.nivel + 1) if padre else 1, naturaleza=codigo.naturaleza,
            tipo=codigo.tipo, padre_id=padre.id if padre else None,
            codigo_agrupador=codigo.codigo, afectable=base.numero not in numeros_con_hijas,
        )
        db.add(cuenta)
        db.flush()
        if padre is not None and padre.afectable:
            padre.afectable = False
        existentes[base.numero] = cuenta
        creadas += 1
    db.flush()
    return creadas


# ── CRUD ──


def _validar_agrupador(codigo: str) -> agrupador.CodigoAgrupador:
    dato = agrupador.obtener(codigo)
    if dato is None:
        raise FiscalAgentError(f"El código agrupador '{codigo}' no existe en el Anexo 24.", 422)
    if not dato.asignable:
        raise FiscalAgentError(
            f"'{codigo}' es un encabezado de rubro; asigna una cuenta o subcuenta del agrupador.",
            422)
    return dato


def crear(
    db: Session, cliente: Cliente, *, numero: str, nombre: str, codigo_agrupador: str,
    padre_id: int | None = None, nivel: int | None = None, naturaleza: str | None = None,
    tipo: str | None = None,
) -> CuentaContable:
    """Agrega una cuenta (o subcuenta) al catálogo del cliente."""
    numero, nombre = numero.strip(), nombre.strip()
    if not numero or not nombre:
        raise FiscalAgentError("La cuenta necesita número y nombre.", 422)
    if db.scalar(select(CuentaContable.id).where(
            CuentaContable.cliente_id == cliente.id, CuentaContable.numero == numero)):
        raise FiscalAgentError(f"Ya existe la cuenta {numero} en este catálogo.", 409)
    codigo = _validar_agrupador(codigo_agrupador)
    padre = obtener(db, cliente, padre_id) if padre_id is not None else None
    nivel_real = padre.nivel + 1 if padre else 1
    if nivel is not None and nivel != nivel_real:
        raise FiscalAgentError(
            f"Nivel incoherente: con {'esa cuenta padre' if padre else 'ninguna cuenta padre'} "
            f"el nivel es {nivel_real}, no {nivel}.", 422)
    if padre is not None and padre.afectable:
        if tiene_movimientos(db, padre.id) or _tiene_saldo_inicial(db, padre.id):
            raise FiscalAgentError(
                f"La cuenta {padre.numero} ya tiene movimientos o saldo inicial; no puede "
                "tener subcuentas. Crea la subcuenta en otra cuenta o reclasifica primero.", 409)
        padre.afectable = False
    naturaleza = naturaleza or (padre.naturaleza if padre else codigo.naturaleza)
    tipo = tipo or (padre.tipo if padre else codigo.tipo)
    if naturaleza not in NATURALEZAS or tipo not in TIPOS:
        raise FiscalAgentError("Naturaleza o tipo de cuenta inválidos.", 422)
    cuenta = CuentaContable(
        cliente_id=cliente.id, numero=numero, nombre=nombre, nivel=nivel_real,
        naturaleza=naturaleza, tipo=tipo, padre_id=padre.id if padre else None,
        codigo_agrupador=codigo.codigo, afectable=True,
    )
    db.add(cuenta)
    db.flush()
    return cuenta


def actualizar(
    db: Session, cliente: Cliente, cuenta_id: int, *, nombre: str | None = None,
    numero: str | None = None, codigo_agrupador: str | None = None,
    naturaleza: str | None = None, tipo: str | None = None,
) -> CuentaContable:
    """Cambia datos de una cuenta. La jerarquía (padre, nivel) no se edita: se reclasifica."""
    cuenta = obtener(db, cliente, cuenta_id)
    if nombre is not None:
        if not nombre.strip():
            raise FiscalAgentError("El nombre no puede quedar vacío.", 422)
        cuenta.nombre = nombre.strip()
    if numero is not None and numero.strip() != cuenta.numero:
        nuevo = numero.strip()
        if db.scalar(select(CuentaContable.id).where(
                CuentaContable.cliente_id == cliente.id, CuentaContable.numero == nuevo)):
            raise FiscalAgentError(f"Ya existe la cuenta {nuevo} en este catálogo.", 409)
        if _en_configuracion(db, cliente, cuenta.numero):
            raise FiscalAgentError(
                f"La cuenta {cuenta.numero} se usa en la configuración de pólizas; cámbiala "
                "ahí antes de renumerarla.", 409)
        cuenta.numero = nuevo
    if codigo_agrupador is not None:
        cuenta.codigo_agrupador = _validar_agrupador(codigo_agrupador).codigo
    if naturaleza is not None:
        if naturaleza not in NATURALEZAS:
            raise FiscalAgentError("Naturaleza inválida.", 422)
        cuenta.naturaleza = naturaleza
    if tipo is not None:
        if tipo not in TIPOS:
            raise FiscalAgentError("Tipo de cuenta inválido.", 422)
        cuenta.tipo = tipo
    db.flush()
    return cuenta


def _en_configuracion(db: Session, cliente: Cliente, numero: str) -> bool:
    """La cuenta la usa la configuración efectiva (default o personalizada) o una regla."""
    from app.contabilidad.config import ROLES  # config importa este módulo

    config = db.get(ConfigContable, cliente.id)
    personal = dict((config.cuentas or {}) if config else {})
    efectivas = {**{rol: d for rol, (d, _t) in ROLES.items()}, **personal}
    if numero in efectivas.values() or (
            config is not None and numero in (config.formas_pago or {}).values()):
        return True
    return db.scalar(select(func.count(ReglaEgreso.id)).where(
        ReglaEgreso.cliente_id == cliente.id, ReglaEgreso.cuenta_numero == numero)) not in (None, 0)


def borrar(db: Session, cliente: Cliente, cuenta_id: int) -> None:
    """Quita una cuenta sin subcuentas, sin movimientos y que no use la configuración."""
    cuenta = obtener(db, cliente, cuenta_id)
    if _tiene_hijas(db, cuenta.id):
        raise FiscalAgentError(f"La cuenta {cuenta.numero} tiene subcuentas; bórralas antes.", 409)
    if tiene_movimientos(db, cuenta.id):
        raise FiscalAgentError(
            f"La cuenta {cuenta.numero} tiene movimientos en pólizas; no se puede borrar.", 409)
    if _en_configuracion(db, cliente, cuenta.numero):
        raise FiscalAgentError(
            f"La cuenta {cuenta.numero} se usa en la configuración de pólizas automáticas.", 409)
    padre_id = cuenta.padre_id
    si = db.get(SaldoInicial, cuenta.id)
    if si is not None:
        db.delete(si)
    db.delete(cuenta)
    db.flush()
    # Un padre que se queda sin subcuentas vuelve a poder recibir movimientos.
    if padre_id is not None and not _tiene_hijas(db, padre_id):
        padre = db.get(CuentaContable, padre_id)
        if padre is not None:
            padre.afectable = True
            db.flush()


def como_dict(c: CuentaContable) -> dict[str, object]:
    return {
        "id": c.id, "numero": c.numero, "nombre": c.nombre, "nivel": c.nivel,
        "naturaleza": c.naturaleza, "tipo": c.tipo, "padre_id": c.padre_id,
        "codigo_agrupador": c.codigo_agrupador, "afectable": c.afectable,
    }
