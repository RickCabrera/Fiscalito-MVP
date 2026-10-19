"""
Fábrica de certificados de PRUEBA con el formato del SAT (nada real).

Genera una CA propia y certificados cuyo sujeto imita los del SAT: RFC en
`x500UniqueIdentifier`, CURP en `serialNumber`, número de serie = dígitos ASCII del
NoCertificado. La e.firma lleva KeyUsage con `dataEncipherment`/`keyAgreement` y EKU
`clientAuth`/`emailProtection`; el CSD sólo `digitalSignature`/`nonRepudiation` y OU de
sucursal. La .key sale como PKCS#8 DER cifrada con contraseña, igual que la del SAT.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.name import _ASN1Type
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID


@dataclass(frozen=True)
class ParPrueba:
    cer: bytes
    key: bytes
    password: str
    numero: str


@lru_cache(maxsize=8)
def _llave(semilla: int) -> rsa.RSAPrivateKey:
    # 2048 como el SAT; cacheada por semilla para que la suite no tarde.
    del semilla
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@lru_cache(maxsize=1)
def _ca() -> tuple[rsa.RSAPrivateKey, x509.Name]:
    llave = _llave(999)
    nombre = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "AC DE PRUEBAS FISCALITO (NO ES EL SAT)"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "PRUEBAS"),
    ])
    return llave, nombre


def generar(
    rfc: str = "XAXX010101AB1",
    tipo: str = "efirma",
    password: str = "clave-prueba-123",
    dias_desde: int = -1,
    dias_hasta: int = 365 * 4,
    semilla: int = 1,
    numero: str = "30001000000500003416",
    rfc_representante: str = "",
) -> ParPrueba:
    """Un par .cer/.key de prueba."""
    llave = _llave(semilla)
    ca_llave, ca_nombre = _ca()
    unico = f"{rfc} / {rfc_representante}" if rfc_representante else rfc
    atributos = [
        x509.NameAttribute(NameOID.COMMON_NAME, "CONTRIBUYENTE DE PRUEBA SA DE CV"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "CONTRIBUYENTE DE PRUEBA SA DE CV"),
        x509.NameAttribute(
            NameOID.X500_UNIQUE_IDENTIFIER, unico, _type=_ASN1Type.PrintableString
        ),
        x509.NameAttribute(NameOID.SERIAL_NUMBER, "XEXX010101HNEXXXA4"),
    ]
    if tipo == "csd":
        atributos.append(x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "MATRIZ"))
    ahora = datetime.now(UTC)
    constructor = (
        x509.CertificateBuilder()
        .subject_name(x509.Name(atributos))
        .issuer_name(ca_nombre)
        .public_key(llave.public_key())
        .serial_number(int.from_bytes(numero.encode("ascii"), "big"))
        .not_valid_before(ahora + timedelta(days=dias_desde))
        .not_valid_after(ahora + timedelta(days=dias_hasta))
    )
    if tipo == "efirma":
        constructor = constructor.add_extension(
            x509.KeyUsage(
                digital_signature=True, content_commitment=True, key_encipherment=False,
                data_encipherment=True, key_agreement=True, key_cert_sign=False,
                crl_sign=False, encipher_only=False, decipher_only=False,
            ),
            critical=True,
        ).add_extension(
            x509.ExtendedKeyUsage(
                [ExtendedKeyUsageOID.EMAIL_PROTECTION, ExtendedKeyUsageOID.CLIENT_AUTH]
            ),
            critical=False,
        )
    else:
        constructor = constructor.add_extension(
            x509.KeyUsage(
                digital_signature=True, content_commitment=True, key_encipherment=False,
                data_encipherment=False, key_agreement=False, key_cert_sign=False,
                crl_sign=False, encipher_only=False, decipher_only=False,
            ),
            critical=True,
        )
    cert = constructor.sign(ca_llave, hashes.SHA256())
    key_der = llave.private_bytes(
        serialization.Encoding.DER,
        serialization.PrivateFormat.PKCS8,
        serialization.BestAvailableEncryption(password.encode("utf-8")),
    )
    return ParPrueba(
        cer=cert.public_bytes(serialization.Encoding.DER),
        key=key_der,
        password=password,
        numero=numero,
    )
