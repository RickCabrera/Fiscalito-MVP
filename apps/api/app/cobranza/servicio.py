"""
Cuentas por cobrar del despacho (P5-03): igualas, cargos, pagos, saldos y antigüedad.

CÓMO SE CALCULA EL SALDO Y SU ANTIGÜEDAD
----------------------------------------
Saldo = cargos vigentes (no cancelados) - pagos. Los pagos se aplican del cargo MÁS VIEJO al
más nuevo (FIFO, por fecha y id): así "desde cuándo debe" es la fecha del cargo más viejo que
sigue abierto. La antigüedad se mide en días desde la FECHA DEL CARGO (no del vencimiento) y
se reparte en 0-30, 31-60, 61-90 y +90; aparte se informa cuánto está ya VENCIDO (vencimiento
anterior a hoy). Un pago de más deja saldo negativo (a favor del cliente) y no se reparte.

QUIÉN VE ESTO
-------------
Son los honorarios del despacho: sólo `dueno` y `contador` (`ROLES_COBRANZA`). El auxiliar no
ve cobranza ni en su pantalla ni en el dashboard.
"""

from __future__ import annotations

import calendar
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auditoria import registrar
from app.boveda_cfdi.servicio import rfc_del_cliente
from app.exceptions import FiscalAgentError
from app.modelos.cfdi import Comprobante
from app.modelos.cobranza import CargoCobranza, HonorarioCliente, PagoCobranza
from app.modelos.nucleo import Cliente
from app.tenancy import Contexto, exigir_rol

ROLES_COBRANZA = ("dueno", "contador")
CENTAVO = Decimal("0.01")
CERO = Decimal("0")
TRAMOS = ("0_30", "31_60", "61_90", "mas_90")


def exigir_cobranza(ctx: Contexto) -> None:
    exigir_rol(ctx, *ROLES_COBRANZA)


def dinero(valor: Decimal | int | str) -> Decimal:
    return Decimal(valor).quantize(CENTAVO)


def tramo(dias: int) -> str:
    """El tramo de antigüedad de un cargo con `dias` desde su fecha."""
    if dias <= 30:
        return "0_30"
    if dias <= 60:
        return "31_60"
    if dias <= 90:
        return "61_90"
    return "mas_90"


# ── configuración (iguala) ──


def config_de(db: Session, cliente: Cliente) -> HonorarioCliente | None:
    return db.get(HonorarioCliente, cliente.id)


def config_json(h: HonorarioCliente | None) -> dict[str, Any] | None:
    if h is None:
        return None
    return {"iguala_mensual": str(dinero(h.iguala_mensual)), "concepto": h.concepto,
            "dia_cargo": h.dia_cargo, "dias_credito": h.dias_credito, "activo": h.activo,
            "facturar": h.facturar, "correo": h.correo, "telefono": h.telefono,
            "recordatorio_automatico": h.recordatorio_automatico,
            "canal_recordatorio": h.canal_recordatorio,
            "dias_entre_recordatorios": h.dias_entre_recordatorios}


def guardar_config(ctx: Contexto, cliente: Cliente, datos: dict[str, Any]) -> HonorarioCliente:
    exigir_cobranza(ctx)
    h = config_de(ctx.db, cliente)
    if h is None:
        h = HonorarioCliente(cliente_id=cliente.id, despacho_id=ctx.despacho_id)
        ctx.db.add(h)
    for k, v in datos.items():
        setattr(h, k, v)
    ctx.db.flush()
    registrar(ctx, "cobranza.config", "honorario", cliente.id,
              {k: str(v) for k, v in datos.items()}, cliente)
    return h


# ── cargos ──


def _fecha_del_mes(anio: int, mes: int, dia: int) -> date:
    return date(anio, mes, min(max(dia, 1), calendar.monthrange(anio, mes)[1]))


def crear_iguala(db: Session, h: HonorarioCliente, anio: int, mes: int,
                 usuario: str = "sistema") -> CargoCobranza | None:
    """El cargo de iguala del mes, si no existe. Idempotente por `iguala:YYYY-MM`."""
    periodo = f"{anio:04d}-{mes:02d}"
    clave = f"iguala:{periodo}"
    existente = db.scalar(select(CargoCobranza.id).where(
        CargoCobranza.cliente_id == h.cliente_id, CargoCobranza.clave == clave))
    if existente is not None or h.iguala_mensual <= 0:
        return None
    fecha = _fecha_del_mes(anio, mes, h.dia_cargo)
    cargo = CargoCobranza(
        despacho_id=h.despacho_id, cliente_id=h.cliente_id, tipo="iguala",
        concepto=f"{h.concepto} {periodo}", periodo=periodo, clave=clave, fecha=fecha,
        vencimiento=fecha + timedelta(days=h.dias_credito), importe=dinero(h.iguala_mensual),
        facturar=h.facturar, creado_por=usuario)
    # Dos corridas simultáneas: el índice único decide y el savepoint salva la transacción.
    try:
        with db.begin_nested():
            db.add(cargo)
            db.flush()
    except IntegrityError:
        return None
    return cargo


def generar_igualas(db: Session, hoy: date, *, despacho_id: str | None = None,
                    cliente_ids: set[int] | None = None, forzar_dia: bool = False,
                    usuario: str = "sistema") -> list[CargoCobranza]:
    """
    Cargos de iguala del mes de `hoy` para las configuraciones activas cuyo día ya llegó
    (`forzar_dia` ignora el día: lo usa la generación manual de un periodo).
    """
    q = select(HonorarioCliente).where(HonorarioCliente.activo.is_(True),
                                       HonorarioCliente.iguala_mensual > 0)
    if despacho_id is not None:
        q = q.where(HonorarioCliente.despacho_id == despacho_id)
    nuevos = []
    for h in db.scalars(q.order_by(HonorarioCliente.cliente_id)):
        if cliente_ids is not None and h.cliente_id not in cliente_ids:
            continue
        if not forzar_dia and hoy.day < min(h.dia_cargo, calendar.monthrange(hoy.year,
                                                                             hoy.month)[1]):
            continue
        cargo = crear_iguala(db, h, hoy.year, hoy.month, usuario)
        if cargo is not None:
            nuevos.append(cargo)
    return nuevos


def crear_servicio(ctx: Contexto, cliente: Cliente, *, concepto: str, importe: Decimal,
                   fecha: date, vencimiento: date | None, facturar: bool) -> CargoCobranza:
    exigir_cobranza(ctx)
    if importe <= 0:
        raise FiscalAgentError("El importe del cargo debe ser mayor a cero.", 422)
    h = config_de(ctx.db, cliente)
    vence = vencimiento or fecha + timedelta(days=h.dias_credito if h else 0)
    if vence < fecha:
        raise FiscalAgentError("El vencimiento no puede ser anterior a la fecha.", 422)
    cargo = CargoCobranza(despacho_id=ctx.despacho_id, cliente_id=cliente.id, tipo="servicio",
                          concepto=concepto, fecha=fecha, vencimiento=vence,
                          importe=dinero(importe), facturar=facturar, creado_por=ctx.uid)
    ctx.db.add(cargo)
    ctx.db.flush()
    registrar(ctx, "cobranza.cargo", "cargo", cargo.id,
              {"concepto": concepto, "importe": str(cargo.importe)}, cliente)
    return cargo


def cargo_de(ctx: Contexto, cliente: Cliente, cargo_id: int) -> CargoCobranza:
    c = ctx.db.get(CargoCobranza, cargo_id)
    if c is None or c.cliente_id != cliente.id or c.despacho_id != ctx.despacho_id:
        raise FiscalAgentError("No existe ese cargo.", 404)
    return c


def cancelar_cargo(ctx: Contexto, cliente: Cliente, cargo_id: int) -> CargoCobranza:
    exigir_cobranza(ctx)
    c = cargo_de(ctx, cliente, cargo_id)
    if c.uuid_cfdi:
        raise FiscalAgentError("El cargo ya está facturado: cancela primero el CFDI.", 409)
    c.cancelado = True
    ctx.db.flush()
    registrar(ctx, "cobranza.cancelar_cargo", "cargo", c.id, {"importe": str(c.importe)},
              cliente)
    return c


def marcar_factura(ctx: Contexto, cliente: Cliente, cargo_id: int, *, facturar: bool,
                   uuid_cfdi: str | None) -> CargoCobranza:
    """Gancho de P5-04: marcar un cargo "facturar" y guardar el UUID cuando exista."""
    exigir_cobranza(ctx)
    c = cargo_de(ctx, cliente, cargo_id)
    c.facturar = facturar
    if uuid_cfdi is not None:
        c.uuid_cfdi = uuid_cfdi.strip().upper() or None
    ctx.db.flush()
    registrar(ctx, "cobranza.factura_cargo", "cargo", c.id,
              {"facturar": facturar, "uuid": c.uuid_cfdi}, cliente)
    return c


def cargo_json(c: CargoCobranza) -> dict[str, Any]:
    return {"id": c.id, "tipo": c.tipo, "concepto": c.concepto, "periodo": c.periodo,
            "fecha": c.fecha.isoformat(), "vencimiento": c.vencimiento.isoformat(),
            "importe": str(dinero(c.importe)), "cancelado": c.cancelado,
            "facturar": c.facturar, "uuid_cfdi": c.uuid_cfdi}


# ── pagos ──


def _validar_cfdi(ctx: Contexto, cliente: Cliente, uuid: str) -> str:
    """
    El UUID debe ser un CFDI EMITIDO que esté en la bóveda de algún cliente del despacho (el
    despacho dado de alta como cliente propio). Si el CFDI trae receptor y el cliente RFC, deben
    coincidir: un pago ligado a la factura de otro cliente es un error de captura.
    """
    uuid = uuid.strip().upper()
    cfdi = ctx.db.scalar(select(Comprobante).join(Cliente, Cliente.id == Comprobante.cliente_id)
                         .where(Cliente.despacho_id == ctx.despacho_id,
                                Comprobante.uuid == uuid,
                                Comprobante.direccion == "emitido"))
    if cfdi is None:
        raise FiscalAgentError(
            "Ese CFDI no está en la bóveda como emitido por el despacho. Da de alta al "
            "despacho como cliente propio e importa sus facturas, o deja el pago sin ligar.",
            422)
    rfc = rfc_del_cliente(cliente)
    if rfc and cfdi.rfc_receptor and cfdi.rfc_receptor.upper() != rfc:
        raise FiscalAgentError("Ese CFDI se emitió a otro RFC, no a este cliente.", 422)
    return uuid


def registrar_pago(ctx: Contexto, cliente: Cliente, *, fecha: date, importe: Decimal,
                   forma_pago: str, referencia: str, cfdi_uuid: str | None,
                   nota: str) -> PagoCobranza:
    exigir_cobranza(ctx)
    if importe <= 0:
        raise FiscalAgentError("El importe del pago debe ser mayor a cero.", 422)
    uuid = _validar_cfdi(ctx, cliente, cfdi_uuid) if cfdi_uuid else None
    p = PagoCobranza(despacho_id=ctx.despacho_id, cliente_id=cliente.id, fecha=fecha,
                     importe=dinero(importe), forma_pago=forma_pago, referencia=referencia,
                     cfdi_uuid=uuid, nota=nota, creado_por=ctx.uid)
    ctx.db.add(p)
    ctx.db.flush()
    registrar(ctx, "cobranza.pago", "pago", p.id,
              {"importe": str(p.importe), "cfdi": uuid}, cliente)
    return p


def borrar_pago(ctx: Contexto, cliente: Cliente, pago_id: int) -> None:
    exigir_cobranza(ctx)
    p = ctx.db.get(PagoCobranza, pago_id)
    if p is None or p.cliente_id != cliente.id or p.despacho_id != ctx.despacho_id:
        raise FiscalAgentError("No existe ese pago.", 404)
    registrar(ctx, "cobranza.borrar_pago", "pago", p.id, {"importe": str(p.importe)}, cliente)
    ctx.db.delete(p)
    ctx.db.flush()


def pago_json(p: PagoCobranza) -> dict[str, Any]:
    return {"id": p.id, "fecha": p.fecha.isoformat(), "importe": str(dinero(p.importe)),
            "forma_pago": p.forma_pago, "referencia": p.referencia, "cfdi_uuid": p.cfdi_uuid,
            "nota": p.nota}


# ── saldos y antigüedad ──


@dataclass
class Saldo:
    """Saldo de un cliente con su antigüedad."""

    cargos: Decimal = CERO
    pagos: Decimal = CERO
    tramos: dict[str, Decimal] = field(default_factory=lambda: {t: CERO for t in TRAMOS})
    vencido: Decimal = CERO
    desde: date | None = None
    vencido_desde: date | None = None
    abiertos: list[tuple[CargoCobranza, Decimal]] = field(default_factory=list)

    @property
    def saldo(self) -> Decimal:
        return dinero(self.cargos - self.pagos)

    def a_dict(self) -> dict[str, Any]:
        return {"total_cargos": str(dinero(self.cargos)),
                "total_pagos": str(dinero(self.pagos)),
                "saldo": str(self.saldo), "vencido": str(dinero(self.vencido)),
                "antiguedad": {t: str(dinero(v)) for t, v in self.tramos.items()},
                "desde": self.desde.isoformat() if self.desde else None,
                "vencido_desde": self.vencido_desde.isoformat() if self.vencido_desde else None}


def calcular_saldo(cargos: list[CargoCobranza], pagos: list[PagoCobranza],
                   hoy: date) -> Saldo:
    """Saldo y antigüedad FIFO (ver encabezado). Función pura."""
    s = Saldo()
    vivos = sorted((c for c in cargos if not c.cancelado), key=lambda c: (c.fecha, c.id or 0))
    s.cargos = sum((Decimal(c.importe) for c in vivos), CERO)
    s.pagos = sum((Decimal(p.importe) for p in pagos), CERO)
    por_aplicar = s.pagos
    for c in vivos:
        importe = Decimal(c.importe)
        aplicado = min(importe, por_aplicar)
        por_aplicar -= aplicado
        pendiente = importe - aplicado
        if pendiente <= 0:
            continue
        s.abiertos.append((c, dinero(pendiente)))
        s.tramos[tramo((hoy - c.fecha).days)] += pendiente
        s.desde = s.desde or c.fecha
        if c.vencimiento < hoy:
            s.vencido += pendiente
            s.vencido_desde = min(s.vencido_desde or c.vencimiento, c.vencimiento)
    return s


def saldos_por_cliente(db: Session, cliente_ids: list[int], hoy: date) -> dict[int, Saldo]:
    """Saldo de varios clientes con DOS consultas (cargos y pagos), sin N+1."""
    if not cliente_ids:
        return {}
    cargos: dict[int, list[CargoCobranza]] = defaultdict(list)
    pagos: dict[int, list[PagoCobranza]] = defaultdict(list)
    for c in db.scalars(select(CargoCobranza).where(CargoCobranza.cliente_id.in_(cliente_ids),
                                                    CargoCobranza.cancelado.is_(False))):
        cargos[c.cliente_id].append(c)
    for p in db.scalars(select(PagoCobranza).where(PagoCobranza.cliente_id.in_(cliente_ids))):
        pagos[p.cliente_id].append(p)
    return {cid: calcular_saldo(cargos[cid], pagos[cid], hoy) for cid in cliente_ids
            if cargos.get(cid) or pagos.get(cid)}


def resumen_cartera(ctx: Contexto, clientes: list[Cliente], hoy: date) -> dict[str, Any]:
    """Saldo por cliente y totales de la cartera visible."""
    exigir_cobranza(ctx)
    ids = [c.id for c in clientes]
    saldos = saldos_por_cliente(ctx.db, ids, hoy)
    configs = {h.cliente_id: h for h in ctx.db.scalars(
        select(HonorarioCliente).where(HonorarioCliente.cliente_id.in_(ids)))} if ids else {}
    filas = []
    total = Saldo()
    for c in clientes:
        s = saldos.get(c.id, Saldo())
        h = configs.get(c.id)
        filas.append({"cliente": c.clave, "cliente_nombre": c.nombre,
                      "iguala_mensual": str(dinero(h.iguala_mensual)) if h else None,
                      **s.a_dict()})
        total.cargos += s.cargos
        total.pagos += s.pagos
        total.vencido += s.vencido
        for t in TRAMOS:
            total.tramos[t] += s.tramos[t]
    filas.sort(key=lambda f: (-Decimal(f["saldo"]), f["cliente_nombre"]))
    return {"exito": True, "hoy": hoy.isoformat(), "clientes": filas,
            "totales": total.a_dict()}


def estado_cuenta(db: Session, cliente: Cliente, hoy: date) -> dict[str, Any]:
    """Movimientos (cargos y pagos) con saldo corrido, más saldo y antigüedad."""
    cargos = list(db.scalars(select(CargoCobranza).where(
        CargoCobranza.cliente_id == cliente.id).order_by(CargoCobranza.fecha, CargoCobranza.id)))
    pagos = list(db.scalars(select(PagoCobranza).where(
        PagoCobranza.cliente_id == cliente.id).order_by(PagoCobranza.fecha, PagoCobranza.id)))
    movs: list[dict[str, Any]] = []
    for c in cargos:
        if not c.cancelado:
            movs.append({"fecha": c.fecha, "orden": 0, "tipo": "cargo", "id": c.id,
                         "concepto": c.concepto, "cargo": dinero(c.importe), "abono": CERO,
                         "vencimiento": c.vencimiento.isoformat(),
                         "uuid": c.uuid_cfdi})
    for p in pagos:
        concepto = f"Pago {p.forma_pago}".strip() + (f" ({p.referencia})" if p.referencia else "")
        movs.append({"fecha": p.fecha, "orden": 1, "tipo": "pago", "id": p.id,
                     "concepto": concepto, "cargo": CERO, "abono": dinero(p.importe),
                     "vencimiento": None, "uuid": p.cfdi_uuid})
    movs.sort(key=lambda m: (m["fecha"], m["orden"], m["id"]))
    corrido = CERO
    for m in movs:
        corrido += m["cargo"] - m["abono"]
        m["saldo"] = str(dinero(corrido))
        m["cargo"], m["abono"] = str(m["cargo"]), str(m["abono"])
        m["fecha"] = m["fecha"].isoformat()
        del m["orden"]
    s = calcular_saldo(cargos, pagos, hoy)
    return {"exito": True, "cliente": cliente.clave, "cliente_nombre": cliente.nombre,
            "hoy": hoy.isoformat(), "movimientos": movs, "cargos": [cargo_json(c) for c in cargos],
            "pagos": [pago_json(p) for p in pagos], **s.a_dict(),
            "abiertos": [{"cargo_id": c.id, "concepto": c.concepto, "fecha": c.fecha.isoformat(),
                          "vencimiento": c.vencimiento.isoformat(), "pendiente": str(pend),
                          "dias": (hoy - c.fecha).days} for c, pend in s.abiertos]}
