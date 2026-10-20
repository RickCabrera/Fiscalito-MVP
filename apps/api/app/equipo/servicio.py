"""
Equipo del despacho (P5-01): invitar, aceptar, roles, desactivar y asignar clientes.

QUIÉN GESTIONA
--------------
Sólo el `dueno`. El contador y el auxiliar ven la lista del equipo, nada más. Todo cambio deja
un renglón explícito en la bitácora (`app/auditoria.registrar`).

LÍMITE DEL PLAN (`app/planes.py`)
---------------------------------
Usuarios activos + invitaciones vigentes sin aceptar no pasan de `max_usuarios`: una
invitación aparta su lugar, así el dueño no manda diez correos para un plan de tres. Al
aceptar se vuelve a revisar (activos < tope) y al reactivar a alguien también.

ACEPTAR UNA INVITACIÓN
----------------------
El que inicia sesión con Firebase y presenta el token se une a ESE despacho. Si en su primer
acceso se le autocreó un despacho propio (id = su uid, ver `tenancy.asegurar_usuario`) y está
VACÍO (sin clientes ni otros usuarios), se mueve; el despacho vacío se queda como renglón sin
usuarios (no se borra: su bitácora sigue siendo historia). Si tiene datos, error claro: mover
a alguien con clientes propios los dejaría huérfanos.
"""

from __future__ import annotations

import hashlib
import os
import secrets
from datetime import UTC, datetime, timedelta
from html import escape
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.auditoria import registrar
from app.exceptions import FiscalAgentError
from app.integraciones import registro
from app.modelos.equipo import DIAS_VIGENCIA_INVITACION, ROLES, Invitacion
from app.modelos.nucleo import AsignacionCliente, Cliente, Despacho, Usuario
from app.planes import Plan
from app.planes import plan as plan_de
from app.tenancy import Contexto, cliente_o_404, exigir_rol

URL_APP_DEFAULT = "http://localhost:5173"


def _ahora() -> datetime:
    return datetime.now(UTC)


def hash_token(token: str) -> str:
    """SHA-256 del token: lo único que se guarda."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def url_app() -> str:
    """Base del front para el enlace del correo (`FISCALITO_URL_APP`)."""
    return (os.environ.get("FISCALITO_URL_APP", "").strip() or URL_APP_DEFAULT).rstrip("/")


def plan_del_despacho(db: Session, despacho_id: str) -> Plan:
    despacho = db.get(Despacho, despacho_id)
    return plan_de(despacho.plan if despacho is not None else None)


def usuarios_activos(db: Session, despacho_id: str) -> int:
    return int(db.scalar(select(func.count()).select_from(Usuario).where(
        Usuario.despacho_id == despacho_id, Usuario.activo.is_(True))) or 0)


def _pendientes(db: Session, despacho_id: str) -> list[Invitacion]:
    """Invitaciones vigentes: sin aceptar, sin revocar y sin vencer."""
    return list(db.scalars(select(Invitacion).where(
        Invitacion.despacho_id == despacho_id, Invitacion.aceptada_en.is_(None),
        Invitacion.revocada.is_(False), Invitacion.expira_en > _ahora(),
    ).order_by(Invitacion.id)))


def _validar_rol(rol: str) -> None:
    if rol not in ROLES:
        raise FiscalAgentError(f"Rol inválido: usa uno de {', '.join(ROLES)}.", 422)


def _usuario_del_despacho(ctx: Contexto, uid: str) -> Usuario:
    u = ctx.db.get(Usuario, uid)
    if u is None or u.despacho_id != ctx.despacho_id:
        raise FiscalAgentError("Ese usuario no es de tu despacho.", 404)
    return u


def _dueños_activos(db: Session, despacho_id: str) -> int:
    return int(db.scalar(select(func.count()).select_from(Usuario).where(
        Usuario.despacho_id == despacho_id, Usuario.activo.is_(True),
        Usuario.rol == "dueno")) or 0)


# ── lectura ──


def invitacion_json(inv: Invitacion) -> dict[str, Any]:
    return {"id": inv.id, "correo": inv.correo, "rol": inv.rol,
            "expira_en": inv.expira_en.isoformat(), "creado_por": inv.creado_por}


def resumen(ctx: Contexto) -> dict[str, Any]:
    """Equipo, asignaciones, plan y (para el dueño) invitaciones pendientes."""
    db = ctx.db
    usuarios = list(db.scalars(select(Usuario).where(
        Usuario.despacho_id == ctx.despacho_id).order_by(Usuario.creado_en, Usuario.uid)))
    asignados: dict[str, list[str]] = {}
    for uid, clave in db.execute(
            select(AsignacionCliente.usuario_uid, Cliente.clave)
            .join(Cliente, Cliente.id == AsignacionCliente.cliente_id)
            .where(Cliente.despacho_id == ctx.despacho_id).order_by(Cliente.clave)):
        asignados.setdefault(uid, []).append(clave)
    el_plan = plan_del_despacho(db, ctx.despacho_id)
    es_dueno = ctx.rol == "dueno"
    pendientes = _pendientes(db, ctx.despacho_id) if es_dueno else []
    clientes = int(db.scalar(select(func.count()).select_from(Cliente).where(
        Cliente.despacho_id == ctx.despacho_id)) or 0)
    return {
        "exito": True,
        "yo": {"uid": ctx.uid, "rol": ctx.rol, "despacho_id": ctx.despacho_id},
        "puede_gestionar": es_dueno,
        "plan": {"id": el_plan.id, "nombre": el_plan.nombre,
                 "max_usuarios": el_plan.max_usuarios, "max_clientes": el_plan.max_clientes,
                 "usuarios_activos": sum(1 for u in usuarios if u.activo),
                 "invitaciones_pendientes": len(pendientes), "clientes": clientes},
        "usuarios": [{"uid": u.uid, "nombre": u.nombre, "email": u.email, "rol": u.rol,
                      "activo": u.activo, "clientes": asignados.get(u.uid, [])}
                     for u in usuarios],
        "invitaciones": [invitacion_json(i) for i in pendientes],
    }


# ── invitaciones ──


def _correo_invitacion(correo: str, despacho: str, rol: str, enlace: str) -> None:
    html = (
        f"<p>Te invitaron a unirte al despacho <b>{escape(despacho)}</b> en Fiscalito "
        f"con el rol <b>{escape(rol)}</b>.</p>"
        f'<p><a href="{escape(enlace)}">Aceptar la invitación</a></p>'
        f"<p>El enlace sirve una sola vez y vence en {DIAS_VIGENCIA_INVITACION} días. "
        "Si no esperabas este correo, ignóralo.</p>"
    )
    registro.obtener("correo").enviar([correo], "Invitación a un despacho en Fiscalito", html)


def invitar(ctx: Contexto, correo: str, rol: str) -> tuple[Invitacion, str]:
    """Crea la invitación y manda el correo. Devuelve (invitación, token en claro)."""
    exigir_rol(ctx, "dueno")
    _validar_rol(rol)
    correo = correo.strip().lower()
    if "@" not in correo or len(correo) > 320:
        raise FiscalAgentError("Correo inválido.", 422)
    db = ctx.db
    if db.scalar(select(Usuario.uid).where(Usuario.despacho_id == ctx.despacho_id,
                                           func.lower(Usuario.email) == correo,
                                           Usuario.activo.is_(True))) is not None:
        raise FiscalAgentError("Ese correo ya es usuario activo de tu despacho.", 409)
    # Reenviar a un correo con invitación vigente: la anterior se revoca (un solo enlace vivo).
    previas = [i for i in _pendientes(db, ctx.despacho_id) if i.correo == correo]
    for p in previas:
        p.revocada = True
    el_plan = plan_del_despacho(db, ctx.despacho_id)
    ocupados = usuarios_activos(db, ctx.despacho_id) + len(_pendientes(db, ctx.despacho_id)) \
        - len(previas)
    if ocupados >= el_plan.max_usuarios:
        raise FiscalAgentError(
            f"El plan {el_plan.nombre} llega hasta {el_plan.max_usuarios} "
            f"{'usuario' if el_plan.max_usuarios == 1 else 'usuarios'} (contando invitaciones "
            "pendientes). Cambia de plan o revoca una invitación.", 409)
    token = secrets.token_urlsafe(32)
    inv = Invitacion(despacho_id=ctx.despacho_id, correo=correo, rol=rol,
                     token_hash=hash_token(token), creado_por=ctx.uid,
                     expira_en=_ahora() + timedelta(days=DIAS_VIGENCIA_INVITACION))
    db.add(inv)
    db.flush()
    despacho = db.get(Despacho, ctx.despacho_id)
    nombre = (despacho.nombre if despacho is not None else "") or "tu despacho"
    _correo_invitacion(correo, nombre, rol, f"{url_app()}/aceptar-invitacion?token={token}")
    registrar(ctx, "equipo.invitar", "invitacion", inv.id, {"correo": correo, "rol": rol})
    return inv, token


def revocar(ctx: Contexto, invitacion_id: int) -> None:
    exigir_rol(ctx, "dueno")
    inv = ctx.db.get(Invitacion, invitacion_id)
    if inv is None or inv.despacho_id != ctx.despacho_id:
        raise FiscalAgentError("No existe esa invitación en tu despacho.", 404)
    if inv.aceptada_en is not None:
        raise FiscalAgentError("Esa invitación ya se aceptó.", 409)
    inv.revocada = True
    ctx.db.flush()
    registrar(ctx, "equipo.revocar_invitacion", "invitacion", inv.id, {"correo": inv.correo})


def aceptar(db: Session, uid: str, token: str, nombre: str = "") -> Usuario:
    """El usuario `uid` se une al despacho de la invitación (ver encabezado)."""
    inv = db.scalar(select(Invitacion).where(Invitacion.token_hash == hash_token(token or "")))
    if inv is None or inv.revocada:
        raise FiscalAgentError("La invitación no es válida.", 404)
    if inv.aceptada_en is not None:
        raise FiscalAgentError("Esta invitación ya se usó.", 409)
    if inv.expira_en <= _ahora():
        raise FiscalAgentError("La invitación venció. Pide al dueño que te mande otra.", 410)
    usuario = db.get(Usuario, uid)
    if usuario is not None:
        if usuario.despacho_id == inv.despacho_id:
            raise FiscalAgentError("Ya eres parte de este despacho.", 409)
        if usuario.despacho_id != uid:
            raise FiscalAgentError(
                "Ya perteneces a otro despacho. Pide que te den de baja allá antes de aceptar.",
                409)
        clientes = int(db.scalar(select(func.count()).select_from(Cliente).where(
            Cliente.despacho_id == uid)) or 0)
        otros = int(db.scalar(select(func.count()).select_from(Usuario).where(
            Usuario.despacho_id == uid, Usuario.uid != uid)) or 0)
        if clientes or otros:
            raise FiscalAgentError(
                f"Tu cuenta ya tiene su propio despacho con datos ({clientes} clientes, "
                f"{otros} usuarios más). No se puede mover a otro despacho sin perderlos: "
                "usa otra cuenta para aceptar la invitación.", 409)
    el_plan = plan_del_despacho(db, inv.despacho_id)
    if usuarios_activos(db, inv.despacho_id) >= el_plan.max_usuarios:
        raise FiscalAgentError(
            f"El despacho ya llegó al tope de {el_plan.max_usuarios} usuarios de su plan.", 409)
    if usuario is None:
        usuario = Usuario(uid=uid, despacho_id=inv.despacho_id)
        db.add(usuario)
    previo = usuario.despacho_id
    usuario.despacho_id, usuario.rol, usuario.activo = inv.despacho_id, inv.rol, True
    if not usuario.email:
        usuario.email = inv.correo
    if nombre.strip():
        usuario.nombre = nombre.strip()[:300]
    # Asignaciones que viniera arrastrando no aplican en el despacho nuevo.
    db.execute(delete(AsignacionCliente).where(AsignacionCliente.usuario_uid == uid))
    inv.aceptada_en, inv.aceptada_por = _ahora(), uid
    db.flush()
    ctx = Contexto(uid=uid, despacho_id=inv.despacho_id, rol=inv.rol, db=db)
    registrar(ctx, "equipo.aceptar_invitacion", "invitacion", inv.id,
              {"correo": inv.correo, "rol": inv.rol, "despacho_previo": previo})
    return usuario


# ── usuarios ──


def cambiar_rol(ctx: Contexto, uid: str, rol: str) -> Usuario:
    exigir_rol(ctx, "dueno")
    _validar_rol(rol)
    u = _usuario_del_despacho(ctx, uid)
    if u.rol == rol:
        return u
    if u.rol == "dueno" and u.activo and _dueños_activos(ctx.db, ctx.despacho_id) <= 1:
        raise FiscalAgentError("El despacho necesita al menos un dueño activo.", 409)
    anterior, u.rol = u.rol, rol
    ctx.db.flush()
    registrar(ctx, "equipo.cambiar_rol", "usuario", uid, {"de": anterior, "a": rol})
    return u


def desactivar(ctx: Contexto, uid: str) -> Usuario:
    exigir_rol(ctx, "dueno")
    if uid == ctx.uid:
        raise FiscalAgentError("No puedes desactivarte a ti mismo.", 422)
    u = _usuario_del_despacho(ctx, uid)
    if not u.activo:
        return u
    if u.rol == "dueno" and _dueños_activos(ctx.db, ctx.despacho_id) <= 1:
        raise FiscalAgentError("El despacho necesita al menos un dueño activo.", 409)
    u.activo = False
    ctx.db.flush()
    registrar(ctx, "equipo.desactivar", "usuario", uid, {"rol": u.rol})
    return u


def reactivar(ctx: Contexto, uid: str) -> Usuario:
    exigir_rol(ctx, "dueno")
    u = _usuario_del_despacho(ctx, uid)
    if u.activo:
        return u
    el_plan = plan_del_despacho(ctx.db, ctx.despacho_id)
    ocupados = usuarios_activos(ctx.db, ctx.despacho_id) + len(_pendientes(ctx.db,
                                                                           ctx.despacho_id))
    if ocupados >= el_plan.max_usuarios:
        raise FiscalAgentError(
            f"El plan {el_plan.nombre} llega hasta {el_plan.max_usuarios} usuarios.", 409)
    u.activo = True
    ctx.db.flush()
    registrar(ctx, "equipo.reactivar", "usuario", uid, {"rol": u.rol})
    return u


def asignar(ctx: Contexto, uid: str, clave: str) -> None:
    exigir_rol(ctx, "dueno")
    u = _usuario_del_despacho(ctx, uid)
    cliente = cliente_o_404(ctx, clave)
    if ctx.db.get(AsignacionCliente, (u.uid, cliente.id)) is None:
        ctx.db.add(AsignacionCliente(usuario_uid=u.uid, cliente_id=cliente.id))
        ctx.db.flush()
    registrar(ctx, "equipo.asignar_cliente", "usuario", uid, {"cliente": clave}, cliente)


def desasignar(ctx: Contexto, uid: str, clave: str) -> None:
    exigir_rol(ctx, "dueno")
    u = _usuario_del_despacho(ctx, uid)
    cliente = cliente_o_404(ctx, clave)
    fila = ctx.db.get(AsignacionCliente, (u.uid, cliente.id))
    if fila is not None:
        ctx.db.delete(fila)
        ctx.db.flush()
    registrar(ctx, "equipo.desasignar_cliente", "usuario", uid, {"cliente": clave}, cliente)


def cambiar_plan(ctx: Contexto, id_plan: str) -> Plan:
    """
    El dueño elige el plan. Bajar a uno más chico que lo que ya hay SE PERMITE (mismo criterio
    que la pantalla de planes, T8): se conserva todo, pero no entra ni un cliente ni un usuario
    más hasta quedar debajo del tope.

    P5-08: delega en `app/suscripciones/servicio.cambiar_plan`, que también cambia el plan
    en el proveedor de pagos cuando hay una suscripción con cobro.
    """
    from app.suscripciones import servicio as suscripciones

    return suscripciones.cambiar_plan(ctx, id_plan, accion="equipo.cambiar_plan")
