"""
P3-04: adaptador de PAC y CFDI de Retenciones e información de pagos 2.0.

- El XML generado valida contra el XSD versionado en `tests/xsd/retenciones/` (con el
  catCFDI y el tdCFDI oficiales de `tests/xsd/`) y su sello verifica con el CSD.
- El PAC falso inserta un TFD 1.1 que valida contra el XSD OFICIAL (byte-idéntico al SAT).
- Las respuestas grabadas de Finkok, SW Sapien y Facturama se parsean sin red.
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
from pathlib import Path

import httpx
import pytest
from cryptography import x509
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from lxml import etree
from pypdf import PdfReader

from app.config import settings
from app.credenciales import servicio as cred_servicio
from app.integraciones import pac as pac_mod
from app.integraciones import registro
from app.integraciones.comun import ErrorServicioExterno
from app.modelos.nucleo import Cliente
from app.retenciones_cfdi import esquemas, generador
from app.tenancy import asegurar_usuario
from tests.nomina.validacion_xsd import ResolverLocal
from tests.plan_p import certs_sat
from tests.plan_p.cfdi_p3 import cfdi_tasas
from tests.plan_p.cfdi_sintetico import RFC_CLIENTE, RFC_PROVEEDOR, uuid_n

XSD = Path(__file__).resolve().parents[1] / "xsd"
FIX = Path(__file__).resolve().parents[1] / "fixtures" / "pac"
RFC_PF = "PERJ800101AB1"


# ── esquemas offline ──


class _ResolverRetenciones(etree.Resolver):
    """`retencionpagov2.xsd` importa por ruta relativa: se mapea al snapshot de tests/xsd."""

    def resolve(self, url, public_id, context):  # noqa: D102
        nombre = (url or "").rsplit("/", 1)[-1]
        for candidato in (XSD / "retenciones" / nombre, XSD / nombre):
            if candidato.exists():
                return self.resolve_filename(str(candidato), context)
        return None


def _esquema_tests() -> etree.XMLSchema:
    parser = etree.XMLParser(no_network=True)
    parser.resolvers.add(_ResolverRetenciones())
    return etree.XMLSchema(etree.parse(str(XSD / "retenciones" / "retencionpagov2.xsd"), parser))


def _sin_tfd(xml: bytes) -> etree._Element:
    raiz = etree.fromstring(xml)
    comp = raiz.find(f"{{{esquemas.NS}}}Complemento")
    if comp is not None:
        raiz.remove(comp)
    return raiz


def test_copias_de_los_xsd_son_identicas():
    app = esquemas.RAIZ / "esquemas" / "retencionpago"
    for nombre, ruta in (("retencionpagov2.xsd", app / "2" / "retencionpagov2.xsd"),
                         ("catRetenciones.xsd", app / "1" / "catalogos" / "catRetenciones.xsd")):
        assert (XSD / "retenciones" / nombre).read_bytes() == ruta.read_bytes()
    leeme = (XSD / "retenciones" / "README.md").read_text(encoding="utf-8")
    for nombre in ("retencionpagov2.xsd", "catRetenciones.xsd"):
        assert hashlib.sha256((XSD / "retenciones" / nombre).read_bytes()).hexdigest() in leeme


# ── PAC falso ──


class _FirmantePrueba:
    def __init__(self, rfc: str = RFC_CLIENTE) -> None:
        par = certs_sat.generar(rfc=rfc, tipo="csd", numero="30001000000500003416")
        from app.credenciales import certificados

        self._llave = certificados.abrir_llave(par.key, par.password)
        self._cer = par.cer
        self.numero_certificado = par.numero

    def firmar_base64(self, datos: bytes, algoritmo: str = "sha256") -> str:
        return base64.b64encode(self._llave.sign(datos, padding.PKCS1v15(),
                                                 hashes.SHA256())).decode()

    @property
    def certificado_base64(self) -> str:
        return base64.b64encode(self._cer).decode()


def _datos() -> generador.DatosRetencion:
    from decimal import Decimal as D

    return generador.DatosRetencion(
        rfc_emisor=RFC_CLIENTE, nombre_emisor="EMPRESA SINTETICA", regimen_emisor="601",
        lugar_expedicion="91000", rfc_receptor=RFC_PF, nombre_receptor="PERSONA SINTETICA",
        domicilio_receptor="91000", ejercicio=2026, mes_ini=3, mes_fin=3, cve_retenc="01",
        monto_operacion=D("10000"), monto_gravado=D("10000"), monto_exento=D("0"),
        impuestos=[generador.ImpuestoRetenido("001", D("10000"), D("1000"), "04"),
                   generador.ImpuestoRetenido("002", D("10000"), D("1066.67"), "01")])


def test_generado_y_sellado_valida_contra_xsd_y_verifica_sello():
    doc = generador.armar(_datos())
    firmante = _FirmantePrueba()
    cadena = generador.sellar(doc, firmante)
    assert cadena.startswith("||2.0|30001000000500003416|") and cadena.endswith("||")
    assert _esquema_tests().validate(doc), _esquema_tests().error_log
    assert esquemas.validar(doc) == []
    cert = x509.load_der_x509_certificate(base64.b64decode(doc.get("Certificado")))
    cert.public_key().verify(base64.b64decode(doc.get("Sello")), cadena.encode(),
                             padding.PKCS1v15(), hashes.SHA256())


def test_falso_inserta_tfd_valido_contra_el_xsd_oficial_y_no_fiscal():
    doc = generador.armar(_datos())
    generador.sellar(doc, _FirmantePrueba())
    timbre = pac_mod.PacFalso().timbrar(generador.a_bytes(doc), "retenciones")
    raiz = etree.fromstring(timbre.xml_timbrado)
    tfd = raiz.find(f".//{{{pac_mod.NS_TFD}}}TimbreFiscalDigital")
    parser = etree.XMLParser(no_network=True)
    parser.resolvers.add(ResolverLocal())
    oficial = etree.XMLSchema(etree.parse(str(XSD / "TimbreFiscalDigitalv11.xsd"), parser))
    assert oficial.validate(tfd), oficial.error_log
    assert "NO FISCAL" in tfd.get("Leyenda") and tfd.get("NoCertificadoSAT") == "0" * 20
    assert tfd.get("SelloCFD") == raiz.get("Sello") and tfd.get("UUID") == timbre.uuid
    assert esquemas.validar(raiz) == []
    assert _esquema_tests().validate(_sin_tfd(timbre.xml_timbrado))
    otro = pac_mod.PacFalso().timbrar(generador.a_bytes(doc), "retenciones")
    assert otro.uuid != timbre.uuid


def test_falso_rechaza_sin_sello_y_cancela_con_motivo():
    falso = pac_mod.PacFalso()
    with pytest.raises(pac_mod.ErrorTimbrado):
        falso.timbrar(generador.a_bytes(generador.armar(_datos())))
    with pytest.raises(ValueError):
        falso.cancelar(uuid_n(1), RFC_CLIENTE, "01")
    acuse = falso.cancelar(uuid_n(1), RFC_CLIENTE, "02")
    assert acuse.estatus == "cancelado" and falso.consultar_estatus(uuid_n(1), "x").estado == \
        "cancelado"


# ── PAC reales con respuestas grabadas ──


class Grabadora:
    def __init__(self, respuestas: dict[str, httpx.Response]) -> None:
        self.peticiones: list[httpx.Request] = []
        self.respuestas = respuestas

    def __call__(self, peticion: httpx.Request) -> httpx.Response:
        self.peticiones.append(peticion)
        for fragmento, resp in self.respuestas.items():
            if fragmento in str(peticion.url):
                return resp
        raise AssertionError(f"Petición inesperada: {peticion.method} {peticion.url}")

    def cliente(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self))


def _fx(nombre: str) -> bytes:
    return (FIX / nombre).read_bytes()


@pytest.fixture
def credenciales_pac(monkeypatch):
    for k, v in {"FISCALITO_FINKOK_USUARIO": "u", "FISCALITO_FINKOK_PASSWORD": "p",
                 "FISCALITO_SW_TOKEN": "tok", "FISCALITO_FACTURAMA_USUARIO": "u",
                 "FISCALITO_FACTURAMA_PASSWORD": "p"}.items():
        monkeypatch.setenv(k, v)


def test_finkok_timbra_y_parsea_respuesta(credenciales_pac):
    g = Grabadora({"retentions.wsdl": httpx.Response(200, content=_fx("finkok_stamp_ok.xml"))})
    t = pac_mod.PacFinkok(g.cliente()).timbrar(b"<xml-sellado/>", "retenciones")
    assert t.uuid == "5E2D6AFF-2DD7-43D1-83D3-14C1ACA396D9"
    assert t.fecha.isoformat() == "2026-04-05T10:00:05"
    assert b"TimbreFiscalDigital" in t.xml_timbrado
    cuerpo = etree.fromstring(g.peticiones[0].content)
    assert etree.QName(cuerpo[1][0]).localname == "stamp"
    assert base64.b64decode(cuerpo.find(".//{*}xml").text) == b"<xml-sellado/>"
    assert cuerpo.find(".//{*}username").text == "u"


def test_finkok_incidencia_es_422(credenciales_pac):
    g = Grabadora({"stamp.wsdl": httpx.Response(200, content=_fx("finkok_stamp_error.xml"))})
    with pytest.raises(pac_mod.ErrorTimbrado) as e:
        pac_mod.PacFinkok(g.cliente()).timbrar(b"<x/>")
    assert "302" in str(e.value) and e.value.status_code == 422


def test_finkok_cancela_con_solicitud_firmada(credenciales_pac):
    g = Grabadora({"cancel.wsdl": httpx.Response(200, content=_fx("finkok_cancel_ok.xml"))})
    uuid = "5E2D6AFF-2DD7-43D1-83D3-14C1ACA396D9"

    class F:
        rfc = RFC_CLIENTE
        _f = _FirmantePrueba()
        certificado_der = base64.b64decode(_f.certificado_base64)
        certificado_base64 = _f.certificado_base64

        def firmar_base64(self, datos: bytes, algoritmo: str = "sha256") -> str:
            return "RklSTUE="

    acuse = pac_mod.PacFinkok(g.cliente()).cancelar(uuid, RFC_CLIENTE, "02", firmante=F())
    assert acuse.estatus == "cancelado" and acuse.codigo == "201" and b"<Acuse>" in \
        acuse.acuse_xml
    solicitud = base64.b64decode(etree.fromstring(g.peticiones[0].content)
                                 .find(".//{*}xml").text)
    assert b'Motivo="02"' in solicitud and b"<Signature" in solicitud


def test_sw_sapien_timbra_cancela_y_rechaza(credenciales_pac):
    g = Grabadora({"retencion/stamp": httpx.Response(200, content=_fx("sw_stamp_ok.json")),
                   "cancel/": httpx.Response(200, content=_fx("sw_cancel_ok.json"))})
    sw = pac_mod.PacSwSapien(g.cliente())
    t = sw.timbrar(b"<x/>", "retenciones")
    assert t.uuid == "5E2D6AFF-2DD7-43D1-83D3-14C1ACA396D9"
    assert g.peticiones[0].headers["Authorization"] == "Bearer tok"
    assert b'name="xml"' in g.peticiones[0].content
    acuse = sw.cancelar(t.uuid, RFC_CLIENTE, "01", uuid_n(9), tipo="retenciones")
    assert acuse.estatus == "cancelado"
    assert str(g.peticiones[1].url).endswith(f"/{RFC_CLIENTE}/{t.uuid}/01/{uuid_n(9)}")
    malo = Grabadora({"stamp": httpx.Response(400, content=_fx("sw_stamp_error.json"))})
    with pytest.raises(pac_mod.ErrorTimbrado):
        pac_mod.PacSwSapien(malo.cliente()).timbrar(b"<x/>")


def test_facturama_traduce_a_json_timbra_y_cancela(credenciales_pac):
    doc = generador.armar(_datos())
    generador.sellar(doc, _FirmantePrueba())
    g = Grabadora({
        "2/retenciones": httpx.Response(200, content=_fx("facturama_retencion_creada.json")),
        "Retenciones/xml/ret-abc123": httpx.Response(200, content=_fx("facturama_xml.json")),
        "api/Retenciones?keyword": httpx.Response(200, content=_fx("facturama_lista.json")),
        "api/Retenciones/ret-abc123": httpx.Response(200, content=_fx("facturama_cancel_ok.json")),
    })
    fa = pac_mod.PacFacturama(g.cliente())
    t = fa.timbrar(generador.a_bytes(doc), "retenciones")
    assert t.uuid == "5E2D6AFF-2DD7-43D1-83D3-14C1ACA396D9"
    enviado = json.loads(g.peticiones[0].content)
    assert enviado["Emisor"]["RFCEmisor"] == RFC_CLIENTE and enviado["CveRetenc"] == "01"
    assert enviado["Receptor"]["RFCRecep"] == RFC_PF
    assert [i["montoRet"] for i in enviado["Totales"]["ImpRetenidos"]] == [1000.0, 1066.67]
    acuse = fa.cancelar(t.uuid, RFC_CLIENTE, "02", tipo="retenciones")
    assert acuse.estatus == "cancelado"
    assert g.peticiones[-1].method == "DELETE"


def test_pac_respuesta_sin_timbre_es_502(credenciales_pac):
    with pytest.raises(ErrorServicioExterno):
        pac_mod.leer_timbre(b"<a/>")


def test_registro_pac_tiene_falso_y_tres_reales():
    estado = {s["servicio"]: s for s in registro.verificar_configuracion()}["pac"]
    assert set(estado["disponibles"]) == {"falso", "finkok", "sw_sapien", "facturama"}


# ── de la bóveda al CFDI timbrado, por la API ──


@pytest.fixture
def cartera(sesionador, tmp_path, monkeypatch):
    monkeypatch.setenv("FISCALITO_ALMACEN_DIR", str(tmp_path / "almacen"))
    monkeypatch.delenv("FISCALITO_ALMACENAMIENTO", raising=False)
    monkeypatch.delenv("FISCALITO_PAC", raising=False)
    monkeypatch.setattr(settings, "LLAVE_MAESTRA", Fernet.generate_key().decode())
    monkeypatch.setattr(settings, "ENTORNO", "desarrollo")
    db = sesionador()
    asegurar_usuario(db, "uid-a")
    asegurar_usuario(db, "uid-b")
    taller = Cliente(despacho_id="uid-a", clave="taller", nombre="Taller Sintetico",
                     rfc=RFC_CLIENTE, datos={"regimen": "601", "codigo_postal": "91000"})
    db.add_all([taller, Cliente(despacho_id="uid-b", clave="otro", nombre="Otro",
                                rfc=RFC_CLIENTE)])
    db.flush()
    par = certs_sat.generar(rfc=RFC_CLIENTE, tipo="csd")
    cred_servicio.guardar(db, taller, "csd", par.cer, par.key, par.password, "uid-a")
    db.commit()
    db.close()


def _subir(a, archivos):
    r = a.post("/api/v1/boveda/clientes/taller/cfdi",
               files=[("archivos", (f"{i}.xml", x, "text/xml")) for i, x in enumerate(archivos)])
    assert r.status_code == 200 and not r.json()["rechazados"], r.text


def test_emite_descarga_y_cancela_por_api(api, cartera):
    a = api("uid-a")
    _subir(a, [
        # honorarios de una persona física: ISR 10 % y 2/3 del IVA retenidos
        cfdi_tasas(uuid_n(1), emisor=RFC_PF, receptor=RFC_CLIENTE, fecha="2026-03-10T10:00:00",
                   conceptos=[("10000.00", "0.160000")], isr_ret="1000.00",
                   iva_ret="1066.67", regimen_emisor="612", lugar="06700"),
        # proveedor sin retenciones: no aparece
        cfdi_tasas(uuid_n(2), emisor=RFC_PROVEEDOR, receptor=RFC_CLIENTE,
                   fecha="2026-03-11T10:00:00", conceptos=[("500.00", "0.160000")]),
    ])
    r = a.get("/api/v1/clientes/taller/retenciones-cfdi/terceros",
              params={"ejercicio": 2026, "mes_ini": 3, "mes_fin": 3})
    assert r.status_code == 200, r.text
    (t,) = r.json()["terceros"]
    assert t["rfc"] == RFC_PF and t["isr_retenido"] == "1000.00"
    assert t["iva_retenido"] == "1066.67" and t["cve_retenc_sugerida"] == "01"
    assert t["domicilio_fiscal"] == "06700"

    r = a.post("/api/v1/clientes/taller/retenciones-cfdi", json={
        "rfc_tercero": RFC_PF, "ejercicio": 2026, "mes_ini": 3, "mes_fin": 3})
    assert r.status_code == 200, r.text
    emitido = r.json()["cfdi"]
    assert emitido["estado"] == "timbrado" and emitido["es_prueba"] and emitido["pac"] == "falso"

    xml = a.get(f"/api/v1/clientes/taller/retenciones-cfdi/{emitido['uuid']}/xml")
    assert xml.status_code == 200
    assert _esquema_tests().validate(_sin_tfd(xml.content)), _esquema_tests().error_log
    assert esquemas.validar(etree.fromstring(xml.content)) == []
    datos = generador.leer(xml.content)
    assert datos["totales"]["MontoTotRet"] == "2066.67"
    assert datos["timbre"]["UUID"] == emitido["uuid"]

    pdf = a.get(f"/api/v1/clientes/taller/retenciones-cfdi/{emitido['uuid']}/pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    texto = PdfReader(io.BytesIO(pdf.content)).pages[0].extract_text()
    assert emitido["uuid"] in texto and "NO FISCAL" in texto

    # despacho B no ve el comprobante de A
    b = api("uid-b")
    assert b.get(f"/api/v1/clientes/taller/retenciones-cfdi/{emitido['uuid']}/xml") \
        .status_code == 404

    r = a.post(f"/api/v1/clientes/taller/retenciones-cfdi/{emitido['uuid']}/cancelar",
               json={"motivo": "02"})
    assert r.status_code == 200 and r.json()["cfdi"]["estado"] == "cancelado"
    assert a.post(f"/api/v1/clientes/taller/retenciones-cfdi/{emitido['uuid']}/cancelar",
                  json={"motivo": "02"}).status_code == 409
    lista = a.get("/api/v1/clientes/taller/retenciones-cfdi", params={"ejercicio": 2026})
    assert [c["estado"] for c in lista.json()["cfdi"]] == ["cancelado"]


def test_no_manda_al_pac_lo_que_no_valida(api, cartera, sesionador):
    db = sesionador()
    c = db.query(Cliente).filter_by(clave="taller").one()
    c.datos = {"regimen": "999", "codigo_postal": "91000"}  # régimen fuera de c_RegimenFiscal
    db.commit()
    db.close()
    a = api("uid-a")
    _subir(a, [cfdi_tasas(uuid_n(1), emisor=RFC_PF, receptor=RFC_CLIENTE,
                          fecha="2026-03-10T10:00:00", conceptos=[("1000.00", "0.160000")],
                          isr_ret="100.00", regimen_emisor="612")])
    llamado = []
    registro.limpiar_cache()
    falso = registro.obtener("pac")
    original = falso.timbrar
    falso.timbrar = lambda *a, **k: llamado.append(1) or original(*a, **k)  # type: ignore
    try:
        r = a.post("/api/v1/clientes/taller/retenciones-cfdi", json={
            "rfc_tercero": RFC_PF, "ejercicio": 2026, "mes_ini": 3, "mes_fin": 3})
    finally:
        falso.timbrar = original  # type: ignore
    assert r.status_code == 422 and "XSD" in r.json()["error"]
    assert llamado == []


def test_sin_csd_no_emite(api, cartera, sesionador):
    db = sesionador()
    for cred in cred_servicio.activas(db, db.query(Cliente).filter_by(clave="taller").one()):
        cred.activo = False
    db.commit()
    db.close()
    a = api("uid-a")
    _subir(a, [cfdi_tasas(uuid_n(1), emisor=RFC_PF, receptor=RFC_CLIENTE,
                          fecha="2026-03-10T10:00:00", conceptos=[("1000.00", "0.160000")],
                          isr_ret="100.00", regimen_emisor="612")])
    r = a.post("/api/v1/clientes/taller/retenciones-cfdi", json={
        "rfc_tercero": RFC_PF, "ejercicio": 2026, "mes_ini": 3, "mes_fin": 3})
    assert r.status_code == 404 and "CSD" in r.json()["error"]
