"""
Mensajes SOAP del web service de Descarga Masiva de CFDI y Retenciones del SAT (v1.5).

Este módulo sólo ARMA y LEE mensajes: no abre conexiones. El adaptador
(`app/integraciones/sat_descarga.py`) los manda por HTTP.

FUENTES
-------
- SAT, "WS Solicitud Descarga Masiva V1.5" (2025-05-30), "WS Verificación de Descarga Masiva
  V1.5" y "WS Descarga de Solicitudes Exitosas V1.5" — los documentos del apartado *Documentos
  relacionados* de https://www.sat.gob.mx/portal/public/tramites/factura-electronica.
  De ahí: operaciones y SOAPAction, atributos de `solicitud` y sus valores, encabezado
  `Authorization: WRAP access_token="…"`, algoritmos (rsa-sha1, sha1, exc-c14n en la
  autenticación), códigos 300–305, 404, 5000–5012, EstadoSolicitud 1–6, paquetes de 72 h y
  máximo 2 descargas por paquete.
- phpcfdi/sat-ws-descarga-masiva (MIT, v1.1.x, compatible con el servicio 1.5): forma exacta
  de los mensajes que el SAT acepta en producción (digest del nodo de la operación sin la
  firma, exc-c14n como canonicalización y transformación, `KeyInfo` con `X509IssuerSerial`),
  URLs de producción y formato de la metadata (`~`). Los tests comprueban que este módulo
  produce los mismos `DigestValue` que los fixtures de esa librería.

CANONICALIZACIÓN SIN LIBRERÍA DE XMLDSIG
----------------------------------------
Los mensajes se arman como texto YA canónico (sin espacios entre nodos, atributos en orden
alfabético, etiquetas vacías abiertas y cerradas, namespace declarado en el nodo que se
digiere). Así el SHA-1 del texto es el SHA-1 de su forma exc-c14n, igual que hace phpcfdi.
Los tests lo verifican al revés, con la canonicalización exclusiva de lxml sobre el sobre
ya parseado y la llave pública del certificado.
"""

from __future__ import annotations

import base64
import hashlib
import re
import uuid as uuid_mod
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import IO, Any, Protocol
from xml.sax.saxutils import unescape

from cryptography import x509
from lxml import etree

NS_SOAP = "http://schemas.xmlsoap.org/soap/envelope/"
NS_U = "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd"
NS_O = "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd"
NS_DES = "http://DescargaMasivaTerceros.sat.gob.mx"
NS_AUT = "http://DescargaMasivaTerceros.gob.mx"
NS_DS = "http://www.w3.org/2000/09/xmldsig#"
X509V3 = "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-x509-token-profile-1.0#X509v3"
BASE64BIN = (
    "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-soap-message-security-1.0"
    "#Base64Binary"
)
EXC_C14N = "http://www.w3.org/2001/10/xml-exc-c14n#"
RSA_SHA1 = "http://www.w3.org/2000/09/xmldsig#rsa-sha1"
SHA1 = "http://www.w3.org/2000/09/xmldsig#sha1"

ACCION_AUTENTICA = "http://DescargaMasivaTerceros.gob.mx/IAutenticacion/Autentica"
_ACCION_DES = "http://DescargaMasivaTerceros.sat.gob.mx"
ACCION_EMITIDOS = f"{_ACCION_DES}/ISolicitaDescargaService/SolicitaDescargaEmitidos"
ACCION_RECIBIDOS = f"{_ACCION_DES}/ISolicitaDescargaService/SolicitaDescargaRecibidos"
ACCION_VERIFICA = f"{_ACCION_DES}/IVerificaSolicitudDescargaService/VerificaSolicitudDescarga"
ACCION_DESCARGA = f"{_ACCION_DES}/IDescargaMasivaTercerosService/Descargar"

FORMATO_FECHA = "%Y-%m-%dT%H:%M:%S"
# El SAT rechaza fechas iniciales anteriores a "hoy menos seis años, a medianoche" (v1.5).
ANIOS_ATRAS = 6

ESTADO_COMPROBANTE = {"vigentes": "Vigente", "cancelados": "Cancelado", "todos": "Todos"}
TIPOS_COMPROBANTE = ("I", "E", "T", "N", "P")

_PARSER = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False)


class Firmante(Protocol):
    """Lo que el WS necesita de la e.firma (ver `app.credenciales.servicio.Firmante`)."""

    rfc: str

    def firmar_base64(self, datos: bytes, algoritmo: str = "sha256") -> str: ...

    @property
    def certificado_der(self) -> bytes: ...

    @property
    def certificado_base64(self) -> str: ...


# ── parámetros ──


@dataclass(frozen=True)
class ParametrosSolicitud:
    """Una solicitud de descarga. Fechas locales (hora de la Ciudad de México), sin zona."""

    direccion: str  # emitidos | recibidos
    tipo: str  # cfdi | metadata
    fecha_inicial: datetime
    fecha_final: datetime
    estado: str = "todos"  # vigentes | cancelados | todos
    rfc_contraparte: str = ""
    tipo_comprobante: str = ""

    def errores(self, hoy: datetime | None = None) -> list[str]:
        """Lo que el SAT rechazaría, dicho antes de mandarlo (reglas del servicio 1.5)."""
        e: list[str] = []
        if self.direccion not in ("emitidos", "recibidos"):
            e.append("La dirección debe ser 'emitidos' o 'recibidos'.")
        if self.tipo not in ("cfdi", "metadata"):
            e.append("El tipo de solicitud debe ser 'cfdi' o 'metadata'.")
        if self.estado not in ESTADO_COMPROBANTE:
            e.append("El estado debe ser 'vigentes', 'cancelados' o 'todos'.")
        if self.tipo_comprobante and self.tipo_comprobante not in TIPOS_COMPROBANTE:
            e.append("El tipo de comprobante debe ser I, E, T, N o P.")
        if self.fecha_inicial >= self.fecha_final:
            e.append("La fecha inicial debe ser anterior a la final (el SAT ya no acepta un "
                     "instante).")
        momento = hoy or datetime.now()
        limite = (momento - timedelta(days=365 * ANIOS_ATRAS + 2)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        if self.fecha_inicial < limite:
            e.append("El SAT sólo permite descargar hasta seis años hacia atrás.")
        if self.direccion == "recibidos" and self.tipo == "cfdi" and self.estado != "vigentes":
            e.append("El SAT no entrega XML de recibidos cancelados: pide sólo vigentes (los "
                     "cancelados se ven en la metadata).")
        return e


# ── utilidades de texto ──


def _esc(valor: str) -> str:
    """Escapa para atributo o texto XML (como htmlspecialchars ENT_XML1|ENT_COMPAT)."""
    return (
        valor.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _sha1_b64(texto: str) -> str:
    return base64.b64encode(hashlib.sha1(texto.encode("utf-8")).digest()).decode("ascii")


def _fecha_sat(momento: datetime) -> str:
    """`2019-08-01T03:38:19.000Z` (UTC con milisegundos), como el Timestamp del SAT."""
    utc = momento.astimezone(UTC) if momento.tzinfo else momento.replace(tzinfo=UTC)
    return utc.strftime("%Y-%m-%dT%H:%M:%S.") + f"{utc.microsecond // 1000:03d}Z"


# Nombres cortos como los imprime OpenSSL (y phpcfdi) para los atributos que usa el SAT.
_NOMBRES_OID = {
    "2.5.4.3": "CN", "2.5.4.10": "O", "2.5.4.11": "OU", "1.2.840.113549.1.9.1": "emailAddress",
    "2.5.4.9": "street", "2.5.4.17": "postalCode", "2.5.4.6": "C", "2.5.4.8": "ST",
    "2.5.4.7": "L", "2.5.4.45": "x500UniqueIdentifier", "1.2.840.113549.1.9.2":
    "unstructuredName", "2.5.4.5": "serialNumber", "2.5.4.41": "name",
}


def _valor_rfc4514(valor: str) -> str:
    salida = "".join(f"\\{c}" if c in ',+"\\<>;' else c for c in valor)
    if salida.startswith((" ", "#")):
        salida = "\\" + salida
    return salida[:-1] + "\\ " if salida.endswith(" ") else salida


def nombre_emisor_certificado(cert_der: bytes) -> str:
    """
    Emisor del certificado para `X509IssuerName`, en el orden en que viene en el .cer y con
    los nombres cortos de OpenSSL. Es el texto que phpcfdi manda y el SAT acepta.
    """
    cert = x509.load_der_x509_certificate(cert_der)
    partes = []
    for rdn in cert.issuer.rdns:
        for a in rdn:
            nombre = _NOMBRES_OID.get(a.oid.dotted_string, a.oid.dotted_string)
            valor = a.value if isinstance(a.value, str) else a.value.decode("utf-8", "replace")
            partes.append(f"{nombre}={_valor_rfc4514(valor)}")
    return ",".join(partes)


def serie_certificado(cert_der: bytes) -> str:
    return str(x509.load_der_x509_certificate(cert_der).serial_number)


# ── firma XMLDSig ──


def _signed_info(digest: str, uri: str) -> str:
    return (
        f'<SignedInfo xmlns="{NS_DS}">'
        f'<CanonicalizationMethod Algorithm="{EXC_C14N}"></CanonicalizationMethod>'
        f'<SignatureMethod Algorithm="{RSA_SHA1}"></SignatureMethod>'
        f'<Reference URI="{uri}"><Transforms>'
        f'<Transform Algorithm="{EXC_C14N}"></Transform></Transforms>'
        f'<DigestMethod Algorithm="{SHA1}"></DigestMethod>'
        f"<DigestValue>{digest}</DigestValue></Reference></SignedInfo>"
    )


def _key_info_x509(firmante: Firmante) -> str:
    der = firmante.certificado_der
    return (
        "<KeyInfo><X509Data><X509IssuerSerial>"
        f"<X509IssuerName>{_esc(nombre_emisor_certificado(der))}</X509IssuerName>"
        f"<X509SerialNumber>{serie_certificado(der)}</X509SerialNumber>"
        "</X509IssuerSerial>"
        f"<X509Certificate>{firmante.certificado_base64}</X509Certificate>"
        "</X509Data></KeyInfo>"
    )


def firma(firmante: Firmante, canonico: str, uri: str = "", key_info: str = "") -> str:
    """
    Nodo `<Signature>` sobre `canonico` (texto ya en forma exc-c14n).

    El SignedInfo se firma con su `xmlns` (así es su forma canónica) y se inserta sin él,
    porque lo hereda de `<Signature xmlns=…>`.
    """
    info = _signed_info(_sha1_b64(canonico), uri)
    valor = firmante.firmar_base64(info.encode("utf-8"), "sha1")
    info_sin_ns = info.replace(f'<SignedInfo xmlns="{NS_DS}">', "<SignedInfo>", 1)
    return (
        f'<Signature xmlns="{NS_DS}">{info_sin_ns}<SignatureValue>{valor}</SignatureValue>'
        f"{key_info or _key_info_x509(firmante)}</Signature>"
    )


# ── mensajes ──


def sobre_autenticacion(
    firmante: Firmante, creado: datetime, expira: datetime, token_id: str = ""
) -> str:
    """`Autentica` con WS-Security: Timestamp firmado y el certificado como token binario."""
    tid = token_id or f"uuid-{uuid_mod.uuid4()}-1"
    c, x = _fecha_sat(creado), _fecha_sat(expira)
    timestamp = f"<u:Created>{c}</u:Created><u:Expires>{x}</u:Expires>"
    canonico = f'<u:Timestamp xmlns:u="{NS_U}" u:Id="_0">{timestamp}</u:Timestamp>'
    key_info = (
        f'<KeyInfo><o:SecurityTokenReference><o:Reference URI="#{tid}" '
        f'ValueType="{X509V3}"/></o:SecurityTokenReference></KeyInfo>'
    )
    sig = firma(firmante, canonico, "#_0", key_info)
    return (
        f'<s:Envelope xmlns:s="{NS_SOAP}" xmlns:u="{NS_U}"><s:Header>'
        f'<o:Security xmlns:o="{NS_O}" s:mustUnderstand="1">'
        f'<u:Timestamp u:Id="_0">{timestamp}</u:Timestamp>'
        f'<o:BinarySecurityToken u:Id="{tid}" ValueType="{X509V3}" '
        f'EncodingType="{BASE64BIN}">{firmante.certificado_base64}</o:BinarySecurityToken>'
        f"{sig}</o:Security></s:Header>"
        f'<s:Body><Autentica xmlns="{NS_AUT}"/></s:Body></s:Envelope>'
    )


def _sobre_des(operacion: str, nodo: str, atributos: dict[str, str], extra: str,
               firmante: Firmante) -> str:
    attrs = " ".join(
        f'{k}="{_esc(v)}"' for k, v in sorted(atributos.items()) if v != ""
    )
    canonico = (
        f'<des:{operacion} xmlns:des="{NS_DES}"><des:{nodo} {attrs}>{extra}</des:{nodo}>'
        f"</des:{operacion}>"
    )
    sig = firma(firmante, canonico)
    return (
        f'<s:Envelope xmlns:s="{NS_SOAP}" xmlns:des="{NS_DES}" xmlns:xd="{NS_DS}">'
        f"<s:Header/><s:Body><des:{operacion}><des:{nodo} {attrs}>{extra}{sig}</des:{nodo}>"
        f"</des:{operacion}></s:Body></s:Envelope>"
    )


def sobre_solicitud(firmante: Firmante, p: ParametrosSolicitud) -> tuple[str, str]:
    """(SOAPAction, sobre) de SolicitaDescargaEmitidos / SolicitaDescargaRecibidos."""
    rfc = firmante.rfc.upper()
    atributos = {
        "RfcSolicitante": rfc,
        "TipoSolicitud": "CFDI" if p.tipo == "cfdi" else "Metadata",
        "FechaInicial": p.fecha_inicial.strftime(FORMATO_FECHA),
        "FechaFinal": p.fecha_final.strftime(FORMATO_FECHA),
        "TipoComprobante": p.tipo_comprobante,
        "EstadoComprobante": ESTADO_COMPROBANTE[p.estado],
    }
    extra = ""
    if p.direccion == "emitidos":
        atributos["RfcEmisor"] = rfc
        if p.rfc_contraparte:
            extra = (f"<des:RfcReceptores><des:RfcReceptor>{_esc(p.rfc_contraparte.upper())}"
                     "</des:RfcReceptor></des:RfcReceptores>")
        operacion, accion = "SolicitaDescargaEmitidos", ACCION_EMITIDOS
    else:
        atributos["RfcReceptor"] = rfc
        atributos["RfcEmisor"] = p.rfc_contraparte.upper()
        operacion, accion = "SolicitaDescargaRecibidos", ACCION_RECIBIDOS
    return accion, _sobre_des(operacion, "solicitud", atributos, extra, firmante)


def sobre_verificacion(firmante: Firmante, id_solicitud: str) -> str:
    atributos = {"IdSolicitud": id_solicitud, "RfcSolicitante": firmante.rfc.upper()}
    return _sobre_des("VerificaSolicitudDescarga", "solicitud", atributos, "", firmante)


def sobre_descarga(firmante: Firmante, id_paquete: str) -> str:
    atributos = {"IdPaquete": id_paquete, "RfcSolicitante": firmante.rfc.upper()}
    return _sobre_des(
        "PeticionDescargaMasivaTercerosEntrada", "peticionDescarga", atributos, "", firmante
    )


# ── lectura de respuestas ──


class RespuestaIlegible(ValueError):
    """La respuesta no es el XML que el SAT documenta."""


def _local(nodo: Any) -> str:
    return etree.QName(nodo).localname.lower() if isinstance(nodo.tag, str) else ""


def _hijo(nodo: Any, nombre: str) -> Any:
    for h in nodo:
        if _local(h) == nombre.lower():
            return h
    return None


def buscar(raiz: Any, *ruta: str) -> Any:
    """Baja por nombres locales sin importar namespace ni mayúsculas (como phpcfdi)."""
    nodo = raiz
    for nombre in ruta:
        nodo = _hijo(nodo, nombre)
        if nodo is None:
            return None
    return nodo


def atributos(nodo: Any) -> dict[str, str]:
    """Atributos con llave en minúsculas y sin namespace."""
    if nodo is None:
        return {}
    return {etree.QName(k).localname.lower(): v for k, v in nodo.attrib.items()}


def leer(contenido: bytes) -> Any:
    try:
        return etree.fromstring(contenido, _PARSER)
    except etree.XMLSyntaxError as e:
        raise RespuestaIlegible(f"El SAT respondió algo que no es XML: {e}") from e


def falla_soap(raiz: Any) -> tuple[str, str] | None:
    """(faultcode, faultstring) si el cuerpo es un `Fault`."""
    f = buscar(raiz, "body", "fault")
    if f is None:
        return None
    codigo = buscar(f, "faultcode")
    texto = buscar(f, "faultstring")
    return (
        (codigo.text or "").strip() if codigo is not None else "",
        (texto.text or "").strip() if texto is not None else "",
    )


@dataclass(frozen=True)
class Token:
    valor: str
    creado: datetime
    expira: datetime

    def vigente(self, ahora: datetime, margen: timedelta = timedelta(seconds=30)) -> bool:
        return bool(self.valor) and ahora + margen < self.expira


def _fecha_utc(texto: str | None) -> datetime | None:
    if not texto:
        return None
    try:
        return datetime.fromisoformat(texto.strip().replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


def leer_token(contenido: bytes, ahora: datetime) -> Token:
    raiz = leer(contenido)
    valor_nodo = buscar(raiz, "body", "autenticaResponse", "autenticaResult")
    if valor_nodo is None or not (valor_nodo.text or "").strip():
        raise RespuestaIlegible("La autenticación del SAT no devolvió token.")
    ts = buscar(raiz, "header", "security", "timestamp")
    creado = _fecha_utc(buscar(ts, "created").text if ts is not None and
                        buscar(ts, "created") is not None else None) or ahora
    expira = _fecha_utc(buscar(ts, "expires").text if ts is not None and
                        buscar(ts, "expires") is not None else None)
    # Sin Expires se asume la vida documentada de cinco minutos.
    return Token((valor_nodo.text or "").strip(), creado, expira or creado + timedelta(minutes=5))


@dataclass(frozen=True)
class ResultadoSolicitud:
    codigo: str
    mensaje: str
    id_solicitud: str = ""


def leer_solicitud(contenido: bytes) -> ResultadoSolicitud:
    raiz = leer(contenido)
    cuerpo = buscar(raiz, "body")
    resultado = None
    if cuerpo is not None:
        for respuesta in cuerpo:
            nombre = _local(respuesta)
            if nombre.startswith("solicitadescarga") and nombre.endswith("response"):
                resultado = _hijo(respuesta, nombre[: -len("response")] + "result")
    if resultado is None:
        raise RespuestaIlegible("La respuesta de la solicitud no trae SolicitaDescarga*Result.")
    a = atributos(resultado)
    return ResultadoSolicitud(a.get("codestatus", ""), a.get("mensaje", ""),
                              a.get("idsolicitud", ""))


@dataclass(frozen=True)
class ResultadoVerificacion:
    codigo: str
    mensaje: str
    estado: int = 0
    codigo_estado: str = ""
    numero_cfdis: int = 0
    paquetes: list[str] = field(default_factory=list)


def leer_verificacion(contenido: bytes) -> ResultadoVerificacion:
    raiz = leer(contenido)
    r = buscar(raiz, "body", "VerificaSolicitudDescargaResponse",
               "VerificaSolicitudDescargaResult")
    if r is None:
        raise RespuestaIlegible("La respuesta no trae VerificaSolicitudDescargaResult.")
    a = atributos(r)

    def entero(llave: str) -> int:
        try:
            return int(a.get(llave, "0") or 0)
        except ValueError:
            return 0

    paquetes = [(h.text or "").strip() for h in r if _local(h) == "idspaquetes"]
    return ResultadoVerificacion(
        codigo=a.get("codestatus", ""), mensaje=a.get("mensaje", ""),
        estado=entero("estadosolicitud"), codigo_estado=a.get("codigoestadosolicitud", ""),
        numero_cfdis=entero("numerocfdis"), paquetes=[p for p in paquetes if p],
    )


# ── descarga en streaming ──


@dataclass(frozen=True)
class ResultadoDescarga:
    codigo: str
    mensaje: str
    bytes_paquete: int = 0


_RE_PAQUETE = re.compile(rb"<(?:[\w.-]+:)?Paquete\b[^>]*?(/?)>")
_RE_COD = re.compile(rb'CodEstatus\s*=\s*"([^"]*)"')
_RE_MSG = re.compile(rb'Mensaje\s*=\s*"([^"]*)"')
BLOQUE = 64 * 1024


def _trozos(archivo: IO[bytes]) -> Iterator[bytes]:
    while True:
        b = archivo.read(BLOQUE)
        if not b:
            return
        yield b


def extraer_paquete(respuesta: IO[bytes], destino: IO[bytes]) -> ResultadoDescarga:
    """
    Lee la respuesta de `Descargar` (ya en disco) y escribe el ZIP decodificado en `destino`
    SIN cargar el base64 completo en memoria: el paquete puede traer 200,000 XML.

    El encabezado `respuesta` (CodEstatus, Mensaje) va antes del cuerpo; se toma con una
    expresión regular del pedazo previo a `<Paquete>`, que es pequeño.
    """
    respuesta.seek(0)
    cabeza = b""
    trozos = _trozos(respuesta)
    m = None
    for t in trozos:
        cabeza += t
        m = _RE_PAQUETE.search(cabeza)
        if m or len(cabeza) > 4 * BLOQUE:
            break
    if m is None:
        # Sin paquete: un error (5007, 5008, Fault). La respuesta es chica: se lee completa.
        respuesta.seek(0)
        raiz = leer(respuesta.read(4 * BLOQUE + 1))
        falla = falla_soap(raiz)
        if falla:
            return ResultadoDescarga("fault", falla[1] or falla[0])
        a = atributos(buscar(raiz, "header", "respuesta"))
        return ResultadoDescarga(a.get("codestatus", ""), a.get("mensaje", ""))

    previo = cabeza[: m.start()]
    cod = _RE_COD.search(previo)
    msg = _RE_MSG.search(previo)
    codigo = cod.group(1).decode() if cod else ""
    mensaje = unescape(msg.group(1).decode("utf-8", "replace"), {"&quot;": '"'}) if msg else ""
    if m.group(1) == b"/":  # <Paquete/>
        return ResultadoDescarga(codigo, mensaje, 0)

    resto = b""
    escritos = 0
    pendiente = cabeza[m.end():]
    fin = False
    while True:
        corte = pendiente.find(b"<")
        if corte >= 0:
            pendiente, fin = pendiente[:corte], True
        limpio = resto + bytes(b for b in pendiente if b not in b" \t\r\n")
        usable = len(limpio) - len(limpio) % 4
        if usable:
            datos = base64.b64decode(limpio[:usable], validate=False)
            destino.write(datos)
            escritos += len(datos)
        resto = limpio[usable:]
        if fin:
            break
        pendiente = next(trozos, b"")
        if not pendiente:
            break
    if resto:
        raise RespuestaIlegible("El paquete del SAT llegó cortado (base64 incompleto).")
    destino.flush()
    return ResultadoDescarga(codigo, mensaje, escritos)
