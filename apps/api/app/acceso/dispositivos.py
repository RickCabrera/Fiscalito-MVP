"""
Token por dispositivo para el push del checador (P0-02).

El Hikvision no puede mandar un ID token de Firebase, así que cada checador lleva un
secreto propio. Se emite UNA vez (la respuesta de `emitir` es la única vez que se ve en
claro), se guarda su SHA-256 y viaja de vuelta en `X-Token-Dispositivo` o en `?token=` (el
aparato sólo deja configurar una URL, así que el query param es el camino real; el
encabezado es el preferido para todo lo demás, porque las URLs terminan en logs).

El token decide el despacho y el cliente del evento. Lo que diga `?cliente=` no puede
moverlo a otro: si no coincide, 403.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.exceptions import FiscalAgentError
from app.modelos.acceso import TokenDispositivo
from app.modelos.nucleo import Cliente, Dispositivo

PREFIJO = "fdt_"


def hash_de(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Emitido:
    """El token en claro (sólo existe en esta respuesta) y su renglón."""

    token: str
    registro: TokenDispositivo


@dataclass(frozen=True)
class Checador:
    """Quién empuja: el despacho y el cliente dueños del token."""

    token_id: int
    despacho_id: str
    cliente_clave: str


def emitir(
    db: Session,
    despacho_id: str,
    cliente_clave: str,
    cliente: Cliente | None,
    dispositivo: Dispositivo | None,
    etiqueta: str,
    creado_por: str,
) -> Emitido:
    """Crea un token nuevo para el cliente (y opcionalmente un dispositivo concreto)."""
    token = PREFIJO + secrets.token_urlsafe(32)
    registro = TokenDispositivo(
        despacho_id=despacho_id,
        cliente_id=cliente.id if cliente is not None else None,
        cliente_clave=cliente_clave,
        dispositivo_id=dispositivo.id if dispositivo is not None else None,
        etiqueta=etiqueta.strip()[:120],
        hash_token=hash_de(token),
        prefijo=token[:12],
        creado_por=creado_por,
    )
    db.add(registro)
    db.flush()
    return Emitido(token=token, registro=registro)


def resolver(db: Session, token: str) -> Checador:
    """El checador dueño del token, o 401. Anota el último uso."""
    registro = db.scalar(
        select(TokenDispositivo).where(
            TokenDispositivo.hash_token == hash_de(token.strip()),
            TokenDispositivo.activo.is_(True),
        )
    )
    if registro is None:
        # Mismo mensaje para "no existe" y "revocado": distinguirlos le sirve a quien sondea.
        raise FiscalAgentError("El token del dispositivo no es válido.", status_code=401)
    registro.ultimo_uso = datetime.now(UTC)
    return Checador(
        token_id=registro.id,
        despacho_id=registro.despacho_id,
        cliente_clave=registro.cliente_clave,
    )


def listar(db: Session, despacho_id: str, cliente_clave: str | None) -> list[TokenDispositivo]:
    consulta = select(TokenDispositivo).where(
        TokenDispositivo.despacho_id == despacho_id, TokenDispositivo.activo.is_(True)
    )
    if cliente_clave is not None:
        consulta = consulta.where(TokenDispositivo.cliente_clave == cliente_clave)
    return list(db.scalars(consulta.order_by(TokenDispositivo.id)))


def revocar(db: Session, despacho_id: str, token_id: int) -> TokenDispositivo:
    """Desactiva el token. De otro despacho = 404 (no se confirma que exista)."""
    registro = db.get(TokenDispositivo, token_id)
    if registro is None or registro.despacho_id != despacho_id or not registro.activo:
        raise FiscalAgentError(f"No existe el token {token_id} en tu despacho.", status_code=404)
    registro.activo = False
    db.flush()
    return registro


def metadatos(registro: TokenDispositivo) -> dict:
    """Lo que se puede mostrar de un token: nunca el hash ni el secreto."""
    return {
        "id": registro.id,
        "cliente": registro.cliente_clave,
        "dispositivo_id": registro.dispositivo_id,
        "etiqueta": registro.etiqueta,
        "prefijo": registro.prefijo,
        "creado_en": registro.creado_en.isoformat() if registro.creado_en else None,
        "ultimo_uso": registro.ultimo_uso.isoformat() if registro.ultimo_uso else None,
    }
