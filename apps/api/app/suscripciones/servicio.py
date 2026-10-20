"""
Suscripción del despacho (P5-08): alta, cambio, cancelación, webhook e historial de pagos.

DUEÑOS DE CADA DATO
-------------------
- El PLAN vigente: `despachos.plan` (lo leen todos los límites). Sólo cambia aquí.
- El ESTADO del cobro y su periodo: `suscripciones` (ver `vigencia.py` para el efectivo).
- Lo que incluye cada plan y su precio: `app/planes.py`.
- El cobro: el adaptador `pagos` (`app/integraciones/pagos.py`). El dominio nunca habla con
  Stripe o Mercado Pago directo.

BAJAR DE PLAN NO BORRA NADA
---------------------------
Un despacho con 30 clientes puede pasarse al plan de 25: los conserva todos, pero no da de
alta el 31 (lo bloquea `almacen_cartera.crear_cliente`); igual con usuarios. `bloqueos()` dice
qué queda bloqueado y por qué, con el número.

WEBHOOK IDEMPOTENTE
-------------------
Cada evento se guarda en `eventos_pago` con llave única (proveedor, evento). Si llega otra vez
se contesta 200 `duplicado: true` sin tocar nada: un `pago_exitoso` repetido NO extiende el
periodo dos veces. Un evento sin id usa el SHA-256 del cuerpo como id.
"""

from __future__ import annotations

import calendar
import hashlib
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auditoria import registrar
from app.exceptions import FiscalAgentError
from app.integraciones import registro
from app.integraciones.pagos import EventoPago
from app.modelos.equipo import Invitacion
from app.modelos.nucleo import Cliente, Despacho, Usuario
from app.modelos.suscripciones import EventoPagoRecibido, PagoSuscripcion, Suscripcion
from app.planes import (
    MODULOS,
    PLANES,
    Plan,
    modulos_del_plan,
    moneda,
    precio_del_plan,
    precio_externo,
)
from app.suscripciones.vigencia import (
    ahora,
    asegurar,
    motivo_modulo,
    plan_del_despacho,
    vigencia,
)
from app.tenancy import Contexto, exigir_rol

# Estados del proveedor que significan "ya está cobrando".
_EXTERNO_ACTIVO = {"active", "trialing", "authorized"}
_EXTERNO_A_ESTADO = {"active": "activa", "trialing": "activa", "authorized": "activa",
                     "past_due": "morosa", "unpaid": "morosa", "canceled": "cancelada",
                     "cancelled": "cancelada", "incomplete_expired": "vencida"}


def _mas_un_mes(d: datetime) -> datetime:
    """Mismo día del mes siguiente (o el último día, si no existe)."""
    anio, mes = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    dia = min(d.day, calendar.monthrange(anio, mes)[1])
    return d.replace(year=anio, month=mes, day=dia)


def _plan_valido(id_plan: str) -> Plan:
    if id_plan not in PLANES:
        raise FiscalAgentError(f"Plan inválido: usa uno de {', '.join(PLANES)}.", 422)
    return PLANES[id_plan]


def _precio_externo_o_error(p: Plan, proveedor: str) -> str:
    externo = precio_externo(p)
    if externo:
        return externo
    if proveedor == "falso":
        return p.id
    raise FiscalAgentError(
        f"Falta configurar el precio del plan {p.nombre} en el proveedor de pagos: "
        f"define FISCALITO_PAGOS_PRECIO_{p.id.upper()}.", 503)


# ── uso y bloqueos ──


def uso(db: Session, despacho_id: str) -> dict[str, int]:
    clientes = db.scalar(select(func.count()).select_from(Cliente).where(
        Cliente.despacho_id == despacho_id)) or 0
    usuarios = db.scalar(select(func.count()).select_from(Usuario).where(
        Usuario.despacho_id == despacho_id, Usuario.activo.is_(True))) or 0
    invitaciones = db.scalar(select(func.count()).select_from(Invitacion).where(
        Invitacion.despacho_id == despacho_id, Invitacion.aceptada_en.is_(None),
        Invitacion.revocada.is_(False), Invitacion.expira_en > ahora())) or 0
    return {"clientes": int(clientes), "usuarios": int(usuarios),
            "invitaciones_pendientes": int(invitaciones)}


def _excesos(p: Plan, u: dict[str, int]) -> list[dict[str, str]]:
    """Lo que el plan `p` bloquearía con el uso `u` (sin borrar nada)."""
    fuera: list[dict[str, str]] = []
    ocupados = u["usuarios"] + u["invitaciones_pendientes"]
    if u["clientes"] >= p.max_clientes:
        extra = (f" Llevas {u['clientes']}: los conservas todos." if u["clientes"] > p.max_clientes
                 else "")
        fuera.append({"tipo": "clientes", "motivo": (
            f"El plan {p.nombre} llega hasta {p.max_clientes} clientes.{extra} No puedes dar "
            "de alta más.")})
    if ocupados >= p.max_usuarios:
        extra = (f" Llevas {ocupados} (con invitaciones pendientes): conservas a todos."
                 if ocupados > p.max_usuarios else "")
        fuera.append({"tipo": "usuarios", "motivo": (
            f"El plan {p.nombre} llega hasta {p.max_usuarios} "
            f"{'usuario' if p.max_usuarios == 1 else 'usuarios'}.{extra} No puedes invitar "
            "ni reactivar a nadie más.")})
    for m in MODULOS:
        if m not in modulos_del_plan(p):
            fuera.append({"tipo": f"modulo:{m}", "motivo": motivo_modulo(p, m)})
    return fuera


def bloqueos(db: Session, despacho_id: str) -> list[dict[str, str]]:
    """Todo lo que hoy está bloqueado para el despacho, con su motivo escrito."""
    v = vigencia(asegurar(db, despacho_id))
    fuera = [] if v.vigente else [{"tipo": "solo_lectura", "motivo": v.aviso}]
    return fuera + _excesos(plan_del_despacho(db, despacho_id), uso(db, despacho_id))


# ── lectura ──


def _pago_json(p: PagoSuscripcion) -> dict[str, Any]:
    return {"id": p.id, "fecha": p.creado_en.isoformat(), "estado": p.estado, "plan": p.plan,
            "monto": str(p.monto) if p.monto is not None else None, "moneda": p.moneda,
            "fin_periodo": p.fin_periodo.isoformat() if p.fin_periodo else None}


def _plan_json(p: Plan, u: dict[str, int]) -> dict[str, Any]:
    precio = precio_del_plan(p)
    return {"id": p.id, "nombre": p.nombre, "max_usuarios": p.max_usuarios,
            "max_clientes": p.max_clientes,
            "modulos": [{"id": m, "nombre": MODULOS[m]} for m in MODULOS
                        if m in modulos_del_plan(p)],
            "precio_mensual": str(precio) if precio is not None else None, "moneda": moneda(),
            "bloquearia": [x for x in _excesos(p, u) if not x["tipo"].startswith("modulo:")]}


def resumen(ctx: Contexto) -> dict[str, Any]:
    """Plan, estado, periodo, uso, bloqueos, catálogo de planes e historial de pagos."""
    db = ctx.db
    s = asegurar(db, ctx.despacho_id)
    v = vigencia(s)
    p = plan_del_despacho(db, ctx.despacho_id)
    u = uso(db, ctx.despacho_id)
    pagos = db.scalars(select(PagoSuscripcion).where(
        PagoSuscripcion.despacho_id == ctx.despacho_id)
        .order_by(PagoSuscripcion.id.desc()).limit(50))
    return {
        "exito": True,
        "puede_gestionar": ctx.rol == "dueno",
        "proveedor": registro.elegida("pagos") or None,
        "suscripcion": {
            "plan": p.id, "plan_nombre": p.nombre, "estado": v.estado, "vigente": v.vigente,
            "solo_lectura": not v.vigente, "aviso": v.aviso,
            "inicio_periodo": s.inicio_periodo.isoformat(),
            "fin_periodo": s.fin_periodo.isoformat(), "acceso_hasta": v.acceso_hasta.isoformat(),
            "plan_pendiente": s.plan_pendiente or None,
            "con_cobro": bool(s.suscripcion_externa),
        },
        "uso": u,
        "bloqueos": bloqueos(db, ctx.despacho_id),
        "planes": [_plan_json(x, u) for x in PLANES.values()],
        "pagos": [_pago_json(x) for x in pagos],
    }


# ── alta, cambio y cancelación ──


def _aplicar_plan(ctx: Contexto, nuevo: Plan, accion: str) -> None:
    despacho = ctx.db.get(Despacho, ctx.despacho_id)
    if despacho is None:
        raise FiscalAgentError("No existe tu despacho.", 404)
    anterior, despacho.plan = despacho.plan, nuevo.id
    ctx.db.flush()
    registrar(ctx, accion, "despacho", ctx.despacho_id, {"de": anterior, "a": nuevo.id})


def suscribirse(ctx: Contexto, id_plan: str, correo: str = "") -> dict[str, Any]:
    """
    Alta de la suscripción de cobro al plan `id_plan`. Si el proveedor ya la deja activa, el
    plan se aplica y arranca el periodo; si pide pagar primero ("incomplete", Mercado Pago),
    queda `plan_pendiente` y se devuelve `url_pago`: el webhook del primer pago lo aplica.
    """
    exigir_rol(ctx, "dueno")
    nuevo = _plan_valido(id_plan)
    db = ctx.db
    s = asegurar(db, ctx.despacho_id)
    v = vigencia(s)
    if s.suscripcion_externa and v.estado in ("activa", "morosa"):
        raise FiscalAgentError("Ya tienes una suscripción con cobro: cambia de plan en vez de "
                               "suscribirte otra vez.", 409)
    proveedor = registro.elegida("pagos")
    pagos = registro.obtener("pagos")
    usuario = db.get(Usuario, ctx.uid)
    correo = (correo or (usuario.email if usuario else "")).strip().lower()
    if not correo and proveedor != "falso":
        raise FiscalAgentError("Indica el correo al que llegarán los cobros.", 422)
    despacho = db.get(Despacho, ctx.despacho_id)
    nombre = (despacho.nombre if despacho else "") or ctx.despacho_id
    if not s.cliente_externo or s.proveedor != proveedor:
        s.cliente_externo = pagos.crear_cliente(correo, nombre, ctx.despacho_id)
    if s.suscripcion_externa and s.plan_pendiente and s.proveedor == proveedor:
        # Un alta anterior que nunca se pagó: se cancela para no dejar dos cobros vivos.
        pagos.cancelar(s.suscripcion_externa)
    # Mercado Pago identifica al pagador por correo en `preapproval` (ver el adaptador).
    pagador = correo if proveedor == "mercadopago" else s.cliente_externo
    externa = pagos.crear_suscripcion(pagador, _precio_externo_o_error(nuevo, proveedor))
    s.proveedor, s.suscripcion_externa, s.cancelada_en = proveedor, externa.id, None
    if externa.estado in _EXTERNO_ACTIVO:
        inicio = ahora()
        s.estado, s.plan_pendiente = "activa", ""
        s.inicio_periodo, s.fin_periodo = inicio, _mas_un_mes(inicio)
        _aplicar_plan(ctx, nuevo, "suscripcion.alta")
    else:
        s.plan_pendiente = nuevo.id
        registrar(ctx, "suscripcion.alta_pendiente", "despacho", ctx.despacho_id,
                  {"plan": nuevo.id, "estado_externo": externa.estado})
    db.flush()
    return {"exito": True, "estado": vigencia(s).estado, "plan": plan_del_despacho(
        db, ctx.despacho_id).id, "plan_pendiente": s.plan_pendiente or None,
        "url_pago": externa.url_pago or None}


def cambiar_plan(ctx: Contexto, id_plan: str, accion: str = "suscripcion.cambiar_plan") -> Plan:
    """
    Cambia el plan. Con suscripción de cobro viva, primero se cambia en el proveedor (si
    falla, no se toca nada aquí). En prueba (o sin cobro) sólo cambia el plan local.
    Bajar a un plan más chico que lo usado se permite: no se borra nada (ver encabezado).
    """
    exigir_rol(ctx, "dueno")
    nuevo = _plan_valido(id_plan)
    s = asegurar(ctx.db, ctx.despacho_id)
    mismo = plan_del_despacho(ctx.db, ctx.despacho_id).id == nuevo.id
    if not mismo and s.suscripcion_externa and s.estado in ("activa", "morosa"):
        proveedor = registro.elegida("pagos")
        registro.obtener("pagos").cambiar_plan(
            s.suscripcion_externa, _precio_externo_o_error(nuevo, proveedor))
    s.plan_pendiente = ""
    _aplicar_plan(ctx, nuevo, accion)
    return nuevo


def cancelar(ctx: Contexto) -> dict[str, Any]:
    """Cancela el cobro. Se conserva el acceso hasta el fin del periodo ya pagado."""
    exigir_rol(ctx, "dueno")
    s = asegurar(ctx.db, ctx.despacho_id)
    if s.estado == "cancelada":
        raise FiscalAgentError("Tu suscripción ya está cancelada.", 409)
    if s.suscripcion_externa:
        registro.obtener("pagos").cancelar(s.suscripcion_externa)
    s.estado, s.cancelada_en, s.plan_pendiente = "cancelada", ahora(), ""
    ctx.db.flush()
    registrar(ctx, "suscripcion.cancelar", "despacho", ctx.despacho_id,
              {"acceso_hasta": s.fin_periodo.isoformat()})
    return {"exito": True, "estado": "cancelada", "acceso_hasta": s.fin_periodo.isoformat()}


# ── webhook ──


def _aplicar_evento(db: Session, s: Suscripcion, ev: EventoPago, evento_id: str) -> str:
    despacho = db.get(Despacho, s.despacho_id)
    if ev.clase == "pago_exitoso":
        if s.plan_pendiente and despacho is not None:
            despacho.plan, s.plan_pendiente = s.plan_pendiente, ""
        momento = ahora()
        base = s.fin_periodo if s.estado in ("activa", "morosa") and s.fin_periodo > momento \
            else momento
        s.inicio_periodo = base
        s.fin_periodo = ev.fin_periodo or _mas_un_mes(base)
        s.estado, s.cancelada_en = "activa", None
    elif ev.clase == "pago_fallido":
        if s.estado != "cancelada":
            s.estado = "morosa"
    elif ev.clase == "suscripcion_actualizada":
        nuevo = _EXTERNO_A_ESTADO.get(ev.estado_externo)
        if nuevo and not (nuevo == "activa" and s.plan_pendiente):
            s.estado = nuevo
        if ev.fin_periodo is not None and nuevo in ("activa", "morosa"):
            s.fin_periodo = ev.fin_periodo
    elif ev.clase == "suscripcion_cancelada":
        s.estado = "cancelada"
        s.cancelada_en = s.cancelada_en or ahora()
        if ev.fin_periodo is not None:
            s.fin_periodo = ev.fin_periodo
    else:
        return "ignorado"
    if ev.clase in ("pago_exitoso", "pago_fallido"):
        db.add(PagoSuscripcion(
            despacho_id=s.despacho_id, evento_id=evento_id,
            estado="pagado" if ev.clase == "pago_exitoso" else "fallido",
            plan=despacho.plan if despacho is not None else "", monto=ev.monto,
            moneda=ev.moneda, fin_periodo=s.fin_periodo if ev.clase == "pago_exitoso" else None))
    db.flush()
    ctx = Contexto(uid="webhook:pagos", despacho_id=s.despacho_id, rol="sistema", db=db)
    registrar(ctx, f"suscripcion.webhook.{ev.clase}", "despacho", s.despacho_id,
              {"evento": evento_id, "estado": s.estado})
    return "aplicado"


def procesar_webhook(db: Session, cuerpo: bytes, encabezados: Mapping[str, str]
                     ) -> dict[str, Any]:
    """Verifica la firma (400 si no cuadra), deduplica y aplica el evento."""
    proveedor = registro.elegida("pagos")
    ev = registro.obtener("pagos").parsear_webhook(cuerpo, encabezados)
    evento_id = ev.id_evento or "sha256:" + hashlib.sha256(cuerpo).hexdigest()
    previo = db.scalar(select(EventoPagoRecibido).where(
        EventoPagoRecibido.proveedor == proveedor, EventoPagoRecibido.evento_id == evento_id))
    if previo is not None:
        return {"exito": True, "duplicado": True, "resultado": previo.resultado}
    s = db.scalar(select(Suscripcion).where(
        Suscripcion.proveedor == proveedor,
        Suscripcion.suscripcion_externa == ev.suscripcion_externa)) \
        if ev.suscripcion_externa else None
    registro_ev = EventoPagoRecibido(
        proveedor=proveedor, evento_id=evento_id, tipo=ev.tipo,
        despacho_id=s.despacho_id if s else None, resultado="",
        datos={"clase": ev.clase, "suscripcion": ev.suscripcion_externa})
    try:
        with db.begin_nested():
            db.add(registro_ev)
            db.flush()
    except IntegrityError:  # el mismo evento llegó dos veces a la vez
        return {"exito": True, "duplicado": True, "resultado": "concurrente"}
    resultado = _aplicar_evento(db, s, ev, evento_id) if s is not None else "sin_suscripcion"
    registro_ev.resultado = resultado
    db.flush()
    return {"exito": True, "duplicado": False, "resultado": resultado}
