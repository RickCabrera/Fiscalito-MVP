"""
Operaciones de la bóveda: guardar, listar, desactivar y obtener un firmante.

`obtener_firmante(db, cliente, tipo)` es la ÚNICA puerta para usar una llave privada. La
descarga masiva del SAT (P1) y el PAC (P4) la llaman; nadie más descifra nada.
"""

import base64
import logging
from datetime import UTC, datetime

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.credenciales import certificados as cert_mod
from app.credenciales import cifrado
from app.exceptions import FiscalAgentError
from app.modelos.credenciales import CredencialCliente
from app.modelos.nucleo import Cliente

logger = logging.getLogger(__name__)

DIAS_AVISO_VENCIMIENTO = 30


class Firmante:
    """
    Firma con la llave privada de una credencial. La llave sólo vive aquí, en memoria.

    No se serializa: `__repr__`, `__getstate__` y `__reduce__` lo impiden a propósito.
    """

    __slots__ = ("_llave", "rfc", "numero_certificado", "tipo", "_cer_der")

    def __init__(
        self, llave: rsa.RSAPrivateKey, cer_der: bytes, rfc: str, numero: str, tipo: str
    ) -> None:
        self._llave = llave
        self._cer_der = cer_der
        self.rfc = rfc
        self.numero_certificado = numero
        self.tipo = tipo

    def firmar(self, datos: bytes, algoritmo: str = "sha256") -> bytes:
        """
        Firma RSA PKCS#1 v1.5. SHA-256 (sello del CFDI 4.0) por default.

        `algoritmo="sha1"` existe SÓLO para el web service de Descarga Masiva del SAT, cuyo
        SignatureMethod documentado (v1.5) es `xmldsig#rsa-sha1`.
        """
        if algoritmo not in ("sha256", "sha1"):
            raise ValueError("Algoritmo de firma no soportado: usa 'sha256' o 'sha1'.")
        digesto = hashes.SHA256() if algoritmo == "sha256" else hashes.SHA1()  # noqa: S303
        return self._llave.sign(datos, padding.PKCS1v15(), digesto)

    def firmar_base64(self, datos: bytes, algoritmo: str = "sha256") -> str:
        """La firma en base64 (formato del atributo `Sello` y del SignatureValue)."""
        return base64.b64encode(self.firmar(datos, algoritmo)).decode("ascii")

    def firmar_sha1(self, datos: bytes) -> bytes:
        """SHA1withRSA (PKCS#1 v1.5). Sólo para el token del login con e.firma del portal
        del SAT, que sigue pidiendo SHA-1 (P1-05); todo lo demás firma con SHA-256."""
        return self._llave.sign(datos, padding.PKCS1v15(), hashes.SHA1())  # noqa: S303

    @property
    def certificado_der(self) -> bytes:
        return self._cer_der

    @property
    def certificado_base64(self) -> str:
        return cert_mod.certificado_base64(self._cer_der)

    def __repr__(self) -> str:
        return f"Firmante(rfc={self.rfc!r}, tipo={self.tipo!r}, no={self.numero_certificado!r})"

    def __getstate__(self) -> None:
        raise TypeError("Un Firmante no se serializa: contiene una llave privada.")

    def __reduce__(self) -> None:  # type: ignore[override]
        raise TypeError("Un Firmante no se serializa: contiene una llave privada.")


def guardar(
    db: Session,
    cliente: Cliente,
    tipo: str,
    cer_der: bytes,
    key_der: bytes,
    password: str,
    creado_por: str,
) -> CredencialCliente:
    """Valida y guarda cifrada. La credencial previa del mismo tipo queda inactiva."""
    datos = cert_mod.validar(cer_der, key_der, password, tipo, rfc_cliente=cliente.rfc)
    key_cifrada = cifrado.cifrar(key_der)
    password_cifrada = cifrado.cifrar(password.encode("utf-8"))

    db.execute(
        update(CredencialCliente)
        .where(
            CredencialCliente.cliente_id == cliente.id,
            CredencialCliente.tipo == tipo,
            CredencialCliente.activo.is_(True),
        )
        .values(activo=False, key_cifrada=b"", password_cifrada=b"")
    )
    cred = CredencialCliente(
        cliente_id=cliente.id,
        tipo=tipo,
        rfc=datos.rfc,
        numero_certificado=datos.numero_certificado,
        valido_desde=datos.valido_desde,
        valido_hasta=datos.valido_hasta,
        cer_der=cer_der,
        key_cifrada=key_cifrada,
        password_cifrada=password_cifrada,
        creado_por=creado_por,
        activo=True,
    )
    db.add(cred)
    db.flush()
    logger.info(
        "Credencial %s guardada: cliente_id=%s no=%s",
        tipo, cliente.id, datos.numero_certificado,
    )
    return cred


def activas(db: Session, cliente: Cliente) -> list[CredencialCliente]:
    """Credenciales activas del cliente, e.firma primero."""
    return list(
        db.scalars(
            select(CredencialCliente)
            .where(CredencialCliente.cliente_id == cliente.id, CredencialCliente.activo.is_(True))
            .order_by(CredencialCliente.tipo, CredencialCliente.id.desc())
        )
    )


def desactivar(db: Session, cliente: Cliente, credencial_id: int) -> None:
    """Borra la credencial: se destruyen los secretos y queda inactiva. 404 si no es suya."""
    cred = db.get(CredencialCliente, credencial_id)
    if cred is None or cred.cliente_id != cliente.id or not cred.activo:
        raise FiscalAgentError("No existe esa credencial para este cliente.", status_code=404)
    cred.activo = False
    # Borrar = que no quede nada usable: se sobrescriben los secretos cifrados.
    cred.key_cifrada = b""
    cred.password_cifrada = b""
    db.flush()


def _a_utc(fecha: datetime) -> datetime:
    # SQLite devuelve datetimes sin zona aunque la columna diga timezone=True.
    return fecha if fecha.tzinfo else fecha.replace(tzinfo=UTC)


def metadatos(cred: CredencialCliente, ahora: datetime | None = None) -> dict:
    """Lo que el front puede ver de una credencial. Nunca la llave ni la contraseña."""
    momento = ahora or datetime.now(UTC)
    hasta = _a_utc(cred.valido_hasta)
    dias = (hasta - momento).days
    return {
        "id": cred.id,
        "tipo": cred.tipo,
        "rfc": cred.rfc,
        "numero_certificado": cred.numero_certificado,
        "valido_desde": _a_utc(cred.valido_desde).isoformat(),
        "valido_hasta": hasta.isoformat(),
        "dias_para_vencer": dias,
        "vencida": hasta <= momento,
        "por_vencer": 0 <= dias < DIAS_AVISO_VENCIMIENTO,
        "creado_por": cred.creado_por,
        "creado_en": _a_utc(cred.creado_en).isoformat() if cred.creado_en else None,
    }


def obtener_firmante(db: Session, cliente: Cliente, tipo: str) -> Firmante:
    """
    Firmante con la credencial activa `tipo` del cliente.

    404 si no hay; 422 si está vencida; 503 si la llave maestra no la abre.
    """
    if tipo not in cert_mod.TIPOS:
        raise FiscalAgentError("El tipo debe ser 'efirma' o 'csd'.", status_code=422)
    cred = db.scalar(
        select(CredencialCliente)
        .where(
            CredencialCliente.cliente_id == cliente.id,
            CredencialCliente.tipo == tipo,
            CredencialCliente.activo.is_(True),
        )
        .order_by(CredencialCliente.id.desc())
    )
    if cred is None:
        raise FiscalAgentError(
            f"El cliente no tiene {cert_mod.NOMBRE_TIPO[tipo]} cargada en la bóveda.",
            status_code=404,
        )
    if _a_utc(cred.valido_hasta) <= datetime.now(UTC):
        raise FiscalAgentError(
            f"La {cert_mod.NOMBRE_TIPO[tipo]} del cliente venció el "
            f"{_a_utc(cred.valido_hasta).date().isoformat()}.",
            status_code=422,
        )
    key_der = cifrado.descifrar(cred.key_cifrada)
    password = cifrado.descifrar(cred.password_cifrada).decode("utf-8")
    llave = cert_mod.abrir_llave(key_der, password)
    return Firmante(llave, cred.cer_der, cred.rfc, cred.numero_certificado, cred.tipo)


def recifrar_todo(db: Session) -> int:
    """Rotación: re-cifra todas las credenciales activas con la llave primaria. Idempotente."""
    total = 0
    for cred in db.scalars(select(CredencialCliente).where(CredencialCliente.activo.is_(True))):
        cred.key_cifrada = cifrado.recifrar(cred.key_cifrada)
        cred.password_cifrada = cifrado.recifrar(cred.password_cifrada)
        total += 1
    db.flush()
    return total
