"""
P1-01: mensajes SOAP del web service de Descarga Masiva del SAT y su firma XMLDSig.

La firma se verifica DE FORMA INDEPENDIENTE a como se armó: se parsea el sobre con lxml, se
canonicaliza con exc-c14n de lxml, se recalcula el digest y se valida el SignatureValue con la
llave PÚBLICA del certificado de prueba. Además se comparan los DigestValue contra los que
phpcfdi/sat-ws-descarga-masiva obtuvo para los mismos parámetros (mensajes que el SAT acepta).
"""

import base64
import copy
import hashlib
import io
from datetime import UTC, datetime

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.x509 import load_der_x509_certificate
from lxml import etree

from app.credenciales.certificados import abrir_llave
from app.credenciales.servicio import Firmante
from app.integraciones import sat_soap
from app.integraciones.sat_soap import ParametrosSolicitud
from tests.plan_p import certs_sat
from tests.plan_p.sat_simulado import plantilla, zip_de

DS = "{http://www.w3.org/2000/09/xmldsig#}"
DES = "http://DescargaMasivaTerceros.sat.gob.mx"
RFC = "XEXX010101AB1"


@pytest.fixture(scope="module")
def firmante() -> Firmante:
    par = certs_sat.generar(rfc=RFC)
    return Firmante(abrir_llave(par.key, par.password), par.cer, RFC, par.numero, "efirma")


def _verificar_firma(sobre: str, nodo_firmado: etree._Element, cer_der: bytes) -> None:
    """Digest y SignatureValue, recalculados con lxml y la llave pública."""
    raiz = etree.fromstring(sobre.encode())
    firma = raiz.find(f".//{DS}Signature")
    assert firma is not None
    info = firma.find(f"{DS}SignedInfo")
    assert info.find(f"{DS}SignatureMethod").get("Algorithm").endswith("rsa-sha1")
    assert info.find(f"{DS}CanonicalizationMethod").get("Algorithm") == sat_soap.EXC_C14N
    assert info.find(f".//{DS}DigestMethod").get("Algorithm").endswith("#sha1")

    copia = copy.deepcopy(nodo_firmado(raiz))
    for s in copia.iter(f"{DS}Signature"):
        s.getparent().remove(s)
    canonico = etree.tostring(copia, method="c14n", exclusive=True)
    digest = base64.b64encode(hashlib.sha1(canonico).digest()).decode()
    assert info.find(f".//{DS}DigestValue").text == digest

    info_c14n = etree.tostring(info, method="c14n", exclusive=True)
    valor = base64.b64decode(firma.find(f"{DS}SignatureValue").text)
    publica = load_der_x509_certificate(cer_der).public_key()
    publica.verify(valor, info_c14n, padding.PKCS1v15(), hashes.SHA1())  # lanza si no cuadra


def test_autenticacion_firma_el_timestamp_con_la_efirma(firmante):
    creado = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
    sobre = sat_soap.sobre_autenticacion(firmante, creado, creado.replace(minute=5), "uuid-x-1")
    ts = "{http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd}"
    _verificar_firma(sobre, lambda r: r.find(f".//{ts}Timestamp"), firmante.certificado_der)
    raiz = etree.fromstring(sobre.encode())
    assert raiz.find(f".//{ts}Created").text == "2026-10-01T12:00:00.000Z"
    assert raiz.find(f".//{ts}Expires").text == "2026-10-01T12:05:00.000Z"
    token = raiz.find(".//{*}BinarySecurityToken")
    assert base64.b64decode(token.text) == firmante.certificado_der
    assert raiz.find(f".//{DS}KeyInfo/{{*}}SecurityTokenReference/{{*}}Reference").get(
        "URI") == "#uuid-x-1"


@pytest.mark.parametrize("direccion", ["emitidos", "recibidos"])
def test_solicitud_firmada_con_atributos_del_sat(firmante, direccion):
    p = ParametrosSolicitud(direccion, "cfdi", datetime(2026, 3, 1), datetime(2026, 3, 31, 23,
                            59, 59), "vigentes", "PRO010101AA1", "I")
    accion, sobre = sat_soap.sobre_solicitud(firmante, p)
    operacion = "SolicitaDescargaEmitidos" if direccion == "emitidos" else \
        "SolicitaDescargaRecibidos"
    assert accion.endswith(f"/ISolicitaDescargaService/{operacion}")
    _verificar_firma(sobre, lambda r: r.find(f".//{{{DES}}}{operacion}"),
                     firmante.certificado_der)
    sol = etree.fromstring(sobre.encode()).find(f".//{{{DES}}}solicitud")
    assert sol.get("TipoSolicitud") == "CFDI"
    assert sol.get("FechaInicial") == "2026-03-01T00:00:00"
    assert sol.get("FechaFinal") == "2026-03-31T23:59:59"
    assert sol.get("EstadoComprobante") == "Vigente"
    assert sol.get("TipoComprobante") == "I"
    assert sol.get("RfcSolicitante") == RFC
    if direccion == "emitidos":
        assert sol.get("RfcEmisor") == RFC
        assert sol.find(f"{{{DES}}}RfcReceptores/{{{DES}}}RfcReceptor").text == "PRO010101AA1"
    else:
        assert (sol.get("RfcReceptor"), sol.get("RfcEmisor")) == (RFC, "PRO010101AA1")
    x509 = etree.fromstring(sobre.encode()).find(f".//{DS}X509IssuerSerial")
    assert x509.find(f"{DS}X509SerialNumber").text == str(
        load_der_x509_certificate(firmante.certificado_der).serial_number)


def test_verificacion_y_descarga_firmadas(firmante):
    sobre = sat_soap.sobre_verificacion(firmante, "abc-123")
    _verificar_firma(sobre, lambda r: r.find(f".//{{{DES}}}VerificaSolicitudDescarga"),
                     firmante.certificado_der)
    sobre = sat_soap.sobre_descarga(firmante, "abc-123_01")
    _verificar_firma(
        sobre, lambda r: r.find(f".//{{{DES}}}PeticionDescargaMasivaTercerosEntrada"),
        firmante.certificado_der,
    )
    nodo = etree.fromstring(sobre.encode()).find(f".//{{{DES}}}peticionDescarga")
    assert (nodo.get("IdPaquete"), nodo.get("RfcSolicitante")) == ("abc-123_01", RFC)


class _FirmanteSinLlave:
    """Para comparar digests contra phpcfdi: el digest no depende de la llave."""

    rfc = "EKU9003173C9"

    def __init__(self, cer: bytes) -> None:
        self.certificado_der = cer
        self.certificado_base64 = base64.b64encode(cer).decode()

    def firmar_base64(self, datos: bytes, algoritmo: str = "sha256") -> str:
        return "AA=="


@pytest.mark.parametrize(("armar", "esperado"), [
    # tests/_files/verify/request.xml de phpcfdi
    (lambda f: sat_soap.sobre_verificacion(f, "3f30a4e1-af73-4085-8991-e4d97eef16bd"),
     "DVHsbfyUP1fm7CPdctOp8N6132E="),
    # tests/_files/download/request.xml
    (lambda f: sat_soap.sobre_descarga(f, "4e80345d-917f-40bb-a98f-4a73939343c5_01"),
     "f0UuGyvdRtYmUtV7HA3c6lVwhdQ="),
    # tests/_files/authenticate/request.xml
    (lambda f: sat_soap.sobre_autenticacion(
        f, datetime(2019, 8, 1, 3, 38, 19, tzinfo=UTC), datetime(2019, 8, 1, 3, 43, 19,
                                                                 tzinfo=UTC), "uuid-x"),
     "nQnU35aTer+opzz7HKZiemZZRj8="),
    # tests/_files/query/request-issued.xml (Metadata, Todos, sin filtros)
    (lambda f: sat_soap.sobre_solicitud(f, ParametrosSolicitud(
        "emitidos", "metadata", datetime(2019, 1, 1), datetime(2019, 1, 1, 0, 4), "todos"))[1],
     "BELGF9WsFcnEbvXILi03IoOZkjg="),
])
def test_digest_igual_al_de_phpcfdi(armar, esperado):
    f = _FirmanteSinLlave(certs_sat.generar().cer)
    raiz = etree.fromstring(armar(f).encode())
    assert raiz.find(f".//{DS}DigestValue").text == esperado


def test_nombre_del_emisor_con_nombres_cortos_de_openssl():
    cer = certs_sat.generar().cer
    nombre = sat_soap.nombre_emisor_certificado(cer)
    assert nombre == "CN=AC DE PRUEBAS FISCALITO (NO ES EL SAT),O=PRUEBAS"


def test_parametros_que_el_sat_rechaza_se_dicen_antes():
    hoy = datetime(2026, 10, 1)
    errores = ParametrosSolicitud("recibidos", "cfdi", datetime(2026, 1, 1),
                                  datetime(2026, 1, 1), "todos").errores(hoy)
    assert any("anterior a la final" in e for e in errores)
    assert any("recibidos cancelados" in e for e in errores)
    viejo = ParametrosSolicitud("emitidos", "cfdi", datetime(2019, 1, 1), datetime(2019, 2, 1))
    assert any("seis años" in e for e in viejo.errores(hoy))
    assert ParametrosSolicitud("emitidos", "metadata", datetime(2026, 1, 1),
                               datetime(2026, 1, 31)).errores(hoy) == []


# ── lectura de respuestas ──


def test_lee_token_solicitud_y_verificacion():
    ahora = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
    tok = sat_soap.leer_token(plantilla(
        "autenticacion_token.xml", CREADO="2026-10-01T12:00:00.000Z",
        EXPIRA="2026-10-01T12:05:00.000Z", TOKEN="eyJ.abc").encode(), ahora)
    assert tok.valor == "eyJ.abc" and tok.expira == ahora.replace(minute=5)
    assert tok.vigente(ahora) and not tok.vigente(ahora.replace(minute=5))

    r = sat_soap.leer_solicitud(plantilla(
        "solicitud.xml", OPERACION="SolicitaDescargaRecibidos", ID="id-1", CODIGO="5000",
        MENSAJE="Solicitud Aceptada").encode())
    assert (r.codigo, r.id_solicitud) == ("5000", "id-1")

    v = sat_soap.leer_verificacion(plantilla(
        "verificacion.xml", CODIGO="5000", ESTADO="3", CODIGO_ESTADO="5000", NUMERO="12345",
        MENSAJE="ok", PAQUETES="<IdsPaquetes>p_01</IdsPaquetes><IdsPaquetes>p_02</IdsPaquetes>",
    ).encode())
    assert (v.estado, v.numero_cfdis, v.paquetes) == (3, 12345, ["p_01", "p_02"])


def test_respuesta_que_no_es_xml_es_ilegible():
    with pytest.raises(sat_soap.RespuestaIlegible):
        sat_soap.leer_solicitud(b"<html>Service Unavailable")


def test_extrae_el_paquete_en_streaming_sin_tenerlo_entero():
    # ~3 MB de ZIP poco comprimible: el base64 cruza muchos bloques de lectura.
    import os

    contenido = zip_de({f"{n}.bin": os.urandom(30_000) for n in range(100)})
    b64 = base64.b64encode(contenido).decode()
    partido = "\r\n".join(b64[i:i + 76] for i in range(0, len(b64), 76))
    respuesta = plantilla("descarga.xml", CODIGO="5000", MENSAJE="Solicitud Aceptada",
                          PAQUETE=f"<Paquete>{partido}</Paquete>").encode()
    destino = io.BytesIO()
    r = sat_soap.extraer_paquete(io.BytesIO(respuesta), destino)
    assert (r.codigo, r.bytes_paquete) == ("5000", len(contenido))
    assert destino.getvalue() == contenido


def test_base64_de_un_paquete_grande_se_decodifica_rapido():
    """Revisión P1: sin generador byte a byte. ~24 MB de base64 con saltos en < 3 s."""
    import os
    import time

    contenido = os.urandom(18 * 1024 * 1024)
    b64 = base64.b64encode(contenido).decode()
    partido = "\r\n\t ".join(b64[i:i + 76] for i in range(0, len(b64), 76))
    respuesta = plantilla("descarga.xml", CODIGO="5000", MENSAJE="Solicitud Aceptada",
                          PAQUETE=f"<Paquete>{partido}</Paquete>").encode()
    destino = io.BytesIO()
    inicio = time.perf_counter()
    r = sat_soap.extraer_paquete(io.BytesIO(respuesta), destino)
    assert time.perf_counter() - inicio < 3
    assert r.bytes_paquete == len(contenido) and destino.getvalue() == contenido


def test_paquete_inexistente_trae_su_codigo():
    respuesta = plantilla("descarga.xml", CODIGO="5007", MENSAJE="No existe el paquete",
                          PAQUETE="<Paquete />").encode()
    r = sat_soap.extraer_paquete(io.BytesIO(respuesta), io.BytesIO())
    assert (r.codigo, r.bytes_paquete) == ("5007", 0)
