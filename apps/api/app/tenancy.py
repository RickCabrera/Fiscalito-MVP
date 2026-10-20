"""
Contexto del request: quién es, de qué despacho, con qué rol (plan P, P0-02).

Toda ruta con datos de un despacho depende de `contexto_actual` y obtiene a sus clientes
con `cliente_o_404`. Nunca se consulta un cliente sin pasar por aquí: así un despacho no
puede pedir datos de otro ni adivinando ids, y un auxiliar sólo ve lo que tiene asignado.
"""

from dataclasses import dataclass

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auditoria import anotar_cliente, anotar_contexto
from app.auth_firebase import usuario_actual
from app.db.session import obtener_db
from app.exceptions import FiscalAgentError
from app.modelos.nucleo import AsignacionCliente, Cliente, Despacho, Usuario
from app.suscripciones.vigencia import exigir_escritura


@dataclass(frozen=True)
class Contexto:
    """Lo que toda ruta de negocio necesita saber del request."""

    uid: str
    despacho_id: str
    rol: str
    db: Session

    @property
    def es_auxiliar(self) -> bool:
        return self.rol == "auxiliar"


def asegurar_usuario(db: Session, uid: str) -> Usuario:
    """
    El usuario del uid; si es su primera vez, se le crea su propio despacho.

    El despacho nace con id = uid: así lo que ya existía en Firestore bajo
    `users/{uid}/...` migra a este despacho sin traducir nada (P0-01).
    """
    usuario = db.get(Usuario, uid)
    if usuario is not None:
        if not usuario.activo:
            raise FiscalAgentError("Tu usuario está desactivado en este despacho.", status_code=403)
        return usuario
    # Dos primeros requests simultáneos del mismo uid compiten por crear lo mismo: el que
    # pierde la carrera relee lo que creó el otro en vez de responder 500 (revisor P0).
    try:
        with db.begin_nested():
            if db.get(Despacho, uid) is None:
                db.add(Despacho(id=uid))
                db.flush()
            usuario = Usuario(uid=uid, despacho_id=uid, rol="dueno")
            db.add(usuario)
            db.flush()
    except IntegrityError:
        usuario = db.get(Usuario, uid)
        if usuario is None:
            raise
    return usuario


def contexto_actual(
    request: Request, uid: str = Depends(usuario_actual), db: Session = Depends(obtener_db)
) -> Contexto:
    """
    Dependencia de FastAPI: el contexto autenticado del request.

    P5-08: si el request ESCRIBE y la suscripción del despacho no está vigente, 402 (modo
    solo lectura, ver `app/suscripciones/vigencia.py`). Leer nunca se bloquea.
    """
    usuario = asegurar_usuario(db, uid)
    anotar_contexto(uid, usuario.despacho_id, db)  # P0-07: el middleware sabe quién fue
    exigir_escritura(db, usuario.despacho_id, request.method, request.url.path)
    return Contexto(uid=uid, despacho_id=usuario.despacho_id, rol=usuario.rol, db=db)


def clientes_visibles(ctx: Contexto) -> list[Cliente]:
    """Clientes del despacho que este usuario puede ver, ordenados por nombre."""
    consulta = select(Cliente).where(Cliente.despacho_id == ctx.despacho_id)
    if ctx.es_auxiliar:
        consulta = consulta.join(
            AsignacionCliente, AsignacionCliente.cliente_id == Cliente.id
        ).where(AsignacionCliente.usuario_uid == ctx.uid)
    return list(ctx.db.scalars(consulta.order_by(Cliente.nombre, Cliente.clave)))


def cliente_o_404(ctx: Contexto, clave: str) -> Cliente:
    """
    El cliente `clave` del despacho del contexto, o 404.

    404 y no 403 cuando el cliente es de otro despacho: un 403 confirmaría que existe.
    """
    cliente = ctx.db.scalar(
        select(Cliente).where(Cliente.despacho_id == ctx.despacho_id, Cliente.clave == clave)
    )
    if cliente is None:
        raise FiscalAgentError(f"No existe el cliente '{clave}' en tu despacho.", status_code=404)
    if ctx.es_auxiliar:
        asignado = ctx.db.get(AsignacionCliente, (ctx.uid, cliente.id))
        if asignado is None:
            raise FiscalAgentError(
                f"No existe el cliente '{clave}' en tu despacho.", status_code=404
            )
    anotar_cliente(cliente)  # P0-07: el renglón de auditoría del request lleva el cliente
    return cliente


# Roles que escriben en la contabilidad (config, catálogo, reglas, pólizas manuales, cierres,
# conciliación manual, Anexo 24). El auxiliar sólo lee, genera las pólizas automáticas e
# importa estados de cuenta (revisión P2, punto 11).
ROLES_CONTABLES = ("dueno", "contador")


def exigir_rol(ctx: Contexto, *roles: str) -> None:
    """403 si el rol del usuario no está entre `roles`."""
    if ctx.rol not in roles:
        raise FiscalAgentError("Tu rol no permite esta acción.", status_code=403)
