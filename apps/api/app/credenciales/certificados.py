"""
Lectura y validación de certificados del SAT (.cer DER + .key PKCS#8 DER cifrada).

CÓMO VIENEN LOS CERTIFICADOS DEL SAT
------------------------------------
- **RFC**: en el sujeto, atributo `x500UniqueIdentifier` (OID 2.5.4.45). Persona física:
  `"AAAA000101AAA"`; persona moral: `"AAA000101AAA / RERR800101XXX"` (RFC de la empresa y,
  tras la diagonal, el del representante legal). Se toma lo que va antes de la diagonal.
  Si faltara, se intenta `serialNumber` (2.5.4.5) por si trae el RFC; normalmente trae CURP.
- **Número de certificado** (20 dígitos, el `NoCertificado` del CFDI): el número de serie
  X.509 en hexadecimal son los códigos ASCII de esos dígitos (p. ej. `0x3330303031...` →
  `"30001..."`).
- **e.firma vs CSD**: la e.firma (FIEL) permite también cifrar/acordar llaves y autenticar
  (KeyUsage con `dataEncipherment`/`keyAgreement`, ExtendedKeyUsage con `clientAuth` o
  `emailProtection`). El CSD sólo firma (`digitalSignature` + `nonRepudiation`) y suele traer
  `OU` con el nombre de la sucursal. Ver `tipo_detectado`.
"""

import base64
from dataclasses import dataclass
from datetime import UTC, datetime

from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from app.exceptions import FiscalAgentError

TIPOS = ("efirma", "csd")
NOMBRE_TIPO = {"efirma": "e.firma (FIEL)", "csd": "Certificado de Sello Digital (CSD)"}


class CredencialInvalida(FiscalAgentError):
    """El .cer/.key/contraseña no pasan la validación. Siempre 422 con mensaje claro."""

    def __init__(self, mensaje: str) -> None:
        super().__init__(mensaje, status_code=422)


@dataclass(frozen=True)
class DatosCertificado:
    """Lo que se puede saber de un .cer sin la llave privada."""

    rfc: str
    numero_certificado: str
    valido_desde: datetime
    valido_hasta: datetime
    tipo_detectado: str
    titular: str


def leer_certificado(cer_der: bytes) -> x509.Certificate:
    """Carga un .cer en DER (o PEM, por si lo convirtieron)."""
    if not cer_der:
        raise CredencialInvalida("El archivo .cer está vacío.")
    try:
        return x509.load_der_x509_certificate(cer_der)
    except ValueError:
        try:
            return x509.load_pem_x509_certificate(cer_der)
        except ValueError as e:
            raise CredencialInvalida(
                "El archivo .cer no es un certificado válido. Sube el .cer tal como lo "
                "entregó el SAT."
            ) from e


def numero_certificado(cert: x509.Certificate) -> str:
    """El NoCertificado del SAT: serie X.509 decodificada como ASCII (o hex si no lo es)."""
    serie = cert.serial_number
    crudo = serie.to_bytes((serie.bit_length() + 7) // 8 or 1, "big")
    try:
        texto = crudo.decode("ascii")
    except UnicodeDecodeError:
        return format(serie, "x")
    return texto if texto.isdigit() else format(serie, "x")


def _atributo(cert: x509.Certificate, oid: x509.ObjectIdentifier) -> str:
    valores = cert.subject.get_attributes_for_oid(oid)
    if not valores:
        return ""
    v = valores[0].value
    return v.decode("utf-8", "replace") if isinstance(v, bytes) else str(v)


def rfc_del_certificado(cert: x509.Certificate) -> str:
    """RFC del titular (x500UniqueIdentifier; si no, serialNumber si parece RFC)."""
    for oid in (NameOID.X500_UNIQUE_IDENTIFIER, NameOID.SERIAL_NUMBER):
        valor = _atributo(cert, oid).split("/")[0].strip().upper()
        if 12 <= len(valor) <= 13 and valor[-3:].isalnum() and not valor[:4].isdigit():
            # Una CURP tiene 18 caracteres; un RFC, 12 (moral) o 13 (física).
            return valor
    return ""


def tipo_detectado(cert: x509.Certificate) -> str:
    """`efirma` o `csd` según el uso declarado del certificado."""
    try:
        ku = cert.extensions.get_extension_for_class(x509.KeyUsage).value
        if ku.data_encipherment or ku.key_agreement or ku.key_encipherment:
            return "efirma"
    except x509.ExtensionNotFound:
        pass
    try:
        eku = cert.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value
        if ExtendedKeyUsageOID.CLIENT_AUTH in eku or ExtendedKeyUsageOID.EMAIL_PROTECTION in eku:
            return "efirma"
    except x509.ExtensionNotFound:
        pass
    return "csd"


def datos_certificado(cert: x509.Certificate) -> DatosCertificado:
    """Metadatos legibles del certificado."""
    return DatosCertificado(
        rfc=rfc_del_certificado(cert),
        numero_certificado=numero_certificado(cert),
        valido_desde=cert.not_valid_before_utc,
        valido_hasta=cert.not_valid_after_utc,
        tipo_detectado=tipo_detectado(cert),
        titular=_atributo(cert, NameOID.COMMON_NAME),
    )


def abrir_llave(key_der: bytes, password: str) -> rsa.RSAPrivateKey:
    """Abre la .key (PKCS#8 DER cifrada) con la contraseña. 422 si no abre."""
    if not key_der:
        raise CredencialInvalida("El archivo .key está vacío.")
    if not password:
        raise CredencialInvalida("Falta la contraseña de la llave privada.")
    try:
        llave = serialization.load_der_private_key(key_der, password=password.encode("utf-8"))
    except TypeError as e:
        # La .key no estaba cifrada: el SAT siempre la entrega cifrada.
        raise CredencialInvalida(
            "El archivo .key no está protegido con contraseña; sube la .key original del SAT."
        ) from e
    except ValueError as e:
        raise CredencialInvalida(
            "La contraseña no abre la llave privada (.key). Revisa la contraseña o que el "
            "archivo sea la .key y no el .cer."
        ) from e
    if not isinstance(llave, rsa.RSAPrivateKey):
        raise CredencialInvalida("La llave privada no es RSA; no es una llave del SAT.")
    return llave


def validar(
    cer_der: bytes,
    key_der: bytes,
    password: str,
    tipo: str,
    rfc_cliente: str = "",
    ahora: datetime | None = None,
) -> DatosCertificado:
    """
    Valida un par .cer/.key para el cliente. Devuelve los metadatos si todo cuadra.

    Comprueba: tipo pedido válido, certificado legible, llave que abre con la contraseña,
    que la llave corresponda al certificado, RFC igual al del cliente (si el cliente lo
    tiene), tipo e.firma/CSD consistente y vigencia.
    """
    if tipo not in TIPOS:
        raise CredencialInvalida("El tipo debe ser 'efirma' o 'csd'.")
    cert = leer_certificado(cer_der)
    llave = abrir_llave(key_der, password)

    publica_cert = cert.public_key()
    if not isinstance(publica_cert, rsa.RSAPublicKey) or (
        publica_cert.public_numbers() != llave.public_key().public_numbers()
    ):
        raise CredencialInvalida(
            "La llave privada (.key) no corresponde a este certificado (.cer). Sube el par "
            "que el SAT entregó junto."
        )

    datos = datos_certificado(cert)
    if not datos.rfc:
        raise CredencialInvalida(
            "El certificado no trae RFC (x500UniqueIdentifier). No parece un certificado del SAT."
        )
    rfc_cliente = (rfc_cliente or "").strip().upper()
    if rfc_cliente and datos.rfc != rfc_cliente:
        raise CredencialInvalida(
            f"El certificado es del RFC {datos.rfc}, pero el cliente tiene RFC {rfc_cliente}."
        )

    if datos.tipo_detectado != tipo:
        raise CredencialInvalida(
            f"Este certificado es {NOMBRE_TIPO[datos.tipo_detectado]}, no "
            f"{NOMBRE_TIPO[tipo]}. Súbelo en la sección que le corresponde."
        )

    momento = ahora or datetime.now(UTC)
    if datos.valido_hasta <= momento:
        raise CredencialInvalida(
            f"El certificado venció el {datos.valido_hasta.date().isoformat()}. Renueva "
            f"la {NOMBRE_TIPO[tipo]} en el SAT y sube la nueva."
        )
    if datos.valido_desde > momento:
        raise CredencialInvalida(
            f"El certificado todavía no es válido: empieza el "
            f"{datos.valido_desde.date().isoformat()}."
        )
    return datos


def certificado_base64(cer_der: bytes) -> str:
    """El .cer en base64 (lo que va en `Certificado` del CFDI y en el WS del SAT)."""
    return base64.b64encode(cer_der).decode("ascii")
