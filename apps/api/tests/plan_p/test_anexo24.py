"""
P2-07 · Contabilidad electrónica (Anexo 24, versión 1.3).

"Listo cuando": los XML de catálogo, balanza y pólizas de un mes validan contra el XSD
oficial versionado offline. Se valida contra la copia de `tests/xsd/contabilidad/` (no la
del paquete de la app) y se verifica que las dos copias sean idénticas y que sus SHA-256
coincidan con el README.
"""

from __future__ import annotations

import base64
import hashlib
import io
import re
import zipfile
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.x509 import load_der_x509_certificate
from lxml import etree

from app.config import settings
from app.contabilidad import catalogo, polizas
from app.contabilidad.anexo24 import esquemas, generador
from app.contabilidad.anexo24.generador import Solicitud
from app.credenciales import servicio as cred_servicio
from app.exceptions import FiscalAgentError
from app.integraciones.almacenamiento import AlmacenamientoMemoria
from app.integraciones.buzon_sat import BuzonSatFalso, BuzonSatPortal, EnvioContabilidad
from app.modelos.nucleo import Cliente
from app.tenancy import asegurar_usuario
from tests.plan_p import certs_sat
from tests.plan_p.conta_sintetico import factura, uuid_n

RFC = "XAXX010101AB1"  # el de los certificados de prueba (genérico, no es de nadie)
TESTS_XSD = Path(__file__).resolve().parents[1] / "xsd" / "contabilidad"
D = Decimal

SHA256 = {
    "esquemas/ContabilidadE/1_3/CatalogoCuentas/CatalogoCuentas_1_3.xsd":
        "40334af7689237a2faff22eefb595d19fa56dc66712014aa41fa8ef4da061f01",
    "esquemas/ContabilidadE/1_3/BalanzaComprobacion/BalanzaComprobacion_1_3.xsd":
        "02df1d97862eaf57ad92ab4eaddd86ea3b4625c2c04ebce2e89342f61a6977cc",
    "esquemas/ContabilidadE/1_3/PolizasPeriodo/PolizasPeriodo_1_3.xsd":
        "4d83675a54fd04d9db5ec3c750b1bc6c2a1cda3ce9c0f774e2bf5754a32673ec",
    "esquemas/ContabilidadE/1_3/AuxiliarCtas/AuxiliarCtas_1_3.xsd":
        "ec85d5381730dd7f00df14793ef10c370600717ee38f3508964ca9972592382c",
    "esquemas/ContabilidadE/1_3/AuxiliarFolios/AuxiliarFolios_1_3.xsd":
        "ae865b852e93bd669dacd8156070baa57562d42f64997e25bb005d3ac9ef1f1b",
    "esquemas/ContabilidadE/1_3/CatalogosParaEsqContE/CatalogosParaEsqContE.xsd":
        "4641439c4e710e3b7761755214d827bc98d4b50fdf587b6f3672034cf215fa51",
    "esquemas/utilerias.xslt":
        "4df421ef981d48d4a7861777f2bd30299eb0c5c3035ad27880fdb1f91cda0f6b",
}


def validar_offline(clave: str, xml: bytes) -> list[str]:
    t = esquemas.TIPOS[clave]
    xsd = etree.XMLSchema(etree.parse(str(
        TESTS_XSD / "esquemas" / "ContabilidadE" / "1_3" / t.carpeta / t.xsd)))
    ok = xsd.validate(etree.fromstring(xml))
    return [] if ok else [str(e) for e in xsd.error_log]


@pytest.fixture
def cliente(db_sesion):
    asegurar_usuario(db_sesion, "uid-ce")
    c = Cliente(despacho_id="uid-ce", clave="taller", nombre="Taller", rfc=RFC)
    db_sesion.add(c)
    db_sesion.flush()
    catalogo.sembrar_base(db_sesion, c)
    return c


@pytest.fixture
def mes(db_sesion, cliente):
    """Un mes con una factura emitida en la bóveda y su póliza (con UUID), y una manual."""
    from app.boveda_cfdi import servicio as boveda
    from app.contabilidad import generador as gen_polizas

    rep = boveda.importar(db_sesion, cliente, [("f.xml", io.BytesIO(
        factura(uuid_n(1), emisor=RFC, fecha="2026-03-10T10:00:00")))],
        almacen=AlmacenamientoMemoria())
    assert not rep.rechazados, rep.rechazados
    gen_polizas.generar(db_sesion, cliente, date(2026, 3, 1), date(2026, 3, 31), "u")
    n = catalogo.por_numero(db_sesion, cliente)
    polizas.crear_manual(db_sesion, cliente, tipo="diario", fecha=date(2026, 3, 20),
                         concepto="Comisión bancaria", movimientos=[
                             polizas.MovimientoEntrada(n["701.10"].id, D("100.00")),
                             polizas.MovimientoEntrada(n["102.01.01"].id, D(0), D("100.00"))],
                         uid="u")
    return cliente


# ── XSD versionados ──


def test_xsd_versionados_con_hash_y_copias_identicas():
    readme = (TESTS_XSD / "README.md").read_text(encoding="utf-8")
    for rel, sha in SHA256.items():
        datos = (TESTS_XSD / rel).read_bytes()
        assert hashlib.sha256(datos).hexdigest() == sha, rel
        assert sha in readme, rel
    for archivo in TESTS_XSD.rglob("*"):
        if archivo.is_file() and archivo.suffix in (".xsd", ".xslt"):
            rel = archivo.relative_to(TESTS_XSD)
            assert (esquemas.RAIZ.parents[2] / rel).read_bytes() == archivo.read_bytes(), rel


# ── LISTO CUANDO: los tres XML de un mes validan ──


def test_catalogo_balanza_y_polizas_del_mes_validan(db_sesion, mes):
    docs = {
        "catalogo": Solicitud("catalogo", 2026, 3),
        "balanza": Solicitud("balanza", 2026, 3),
        "polizas": Solicitud("polizas", 2026, 3, tipo_solicitud="AF",
                             num_orden="ABC1234567/26"),
        "auxiliar_cuentas": Solicitud("auxiliar_cuentas", 2026, 3, tipo_solicitud="DE",
                                      num_tramite="AB123456789012"),
        "auxiliar_folios": Solicitud("auxiliar_folios", 2026, 3, tipo_solicitud="CO",
                                     num_tramite="AB123456789012"),
    }
    for clave, s in docs.items():
        doc = generador.generar(db_sesion, mes, s)
        assert doc.errores == [], (clave, doc.errores)
        assert validar_offline(clave, doc.xml) == [], clave
    pol = etree.fromstring(generador.generar(db_sesion, mes, docs["polizas"]).xml)
    ns = {"p": esquemas.TIPOS["polizas"].ns}
    comp = pol.find(".//p:CompNal", ns)
    assert comp is not None and comp.get("UUID_CFDI") == uuid_n(1)
    assert pol.get("TipoSolicitud") == "AF" and pol.get("NumOrden") == "ABC1234567/26"
    bal = etree.fromstring(generador.generar(db_sesion, mes, docs["balanza"]).xml)
    ctas = bal.findall(f"{{{esquemas.TIPOS['balanza'].ns}}}Ctas")
    debe = sum(D(c.get("Debe")) for c in ctas if "." not in c.get("NumCta"))
    haber = sum(D(c.get("Haber")) for c in ctas if "." not in c.get("NumCta"))
    assert debe == haber > 0


def test_balanza_complementaria_y_saldos_por_naturaleza(db_sesion, mes):
    with pytest.raises(FiscalAgentError, match="FechaModBal"):
        generador.generar(db_sesion, mes, Solicitud("balanza", 2026, 3, tipo_envio="C"))
    doc = generador.generar(db_sesion, mes, Solicitud("balanza", 2026, 3, tipo_envio="C",
                                                      fecha_mod_bal=date(2026, 5, 2)))
    assert doc.valido and doc.nombre == f"{RFC}202603BC"
    ns = esquemas.TIPOS["balanza"].ns
    ingresos = etree.fromstring(doc.xml).find(f"{{{ns}}}Ctas[@NumCta='401.01']")
    assert D(ingresos.get("SaldoFin")) > 0  # acreedora: positiva en su naturaleza


def test_solicitud_exige_orden_o_tramite(db_sesion, mes):
    with pytest.raises(FiscalAgentError, match="a solicitud"):
        generador.generar(db_sesion, mes, Solicitud("polizas", 2026, 3))
    with pytest.raises(FiscalAgentError, match="NumOrden"):
        generador.generar(db_sesion, mes, Solicitud("polizas", 2026, 3, tipo_solicitud="FC"))
    with pytest.raises(FiscalAgentError, match="NumTramite"):
        generador.generar(db_sesion, mes, Solicitud("polizas", 2026, 3, tipo_solicitud="DE",
                                                    num_tramite="X"))


def test_nombres_de_archivo_y_zip(db_sesion, mes):
    casos = [
        (Solicitud("catalogo", 2026, 3), f"{RFC}202603CT"),
        (Solicitud("balanza", 2026, 3), f"{RFC}202603BN"),
        (Solicitud("polizas", 2026, 3, tipo_solicitud="AF", num_orden="ABC1234567/26"),
         f"{RFC}202603PL"),
        (Solicitud("auxiliar_cuentas", 2026, 3, tipo_solicitud="AF",
                   num_orden="ABC1234567/26"), f"{RFC}202603XC"),
        (Solicitud("auxiliar_folios", 2026, 3, tipo_solicitud="AF",
                   num_orden="ABC1234567/26"), f"{RFC}202603XF"),
    ]
    for s, nombre in casos:
        doc = generador.generar(db_sesion, mes, s)
        assert doc.nombre == nombre
        z = zipfile.ZipFile(io.BytesIO(generador.empaquetar(doc)))
        assert z.namelist() == [f"{nombre}.xml"]
        assert z.read(f"{nombre}.xml") == doc.xml


def test_xml_invalido_no_se_empaqueta(db_sesion, cliente):
    # Sin movimientos, el auxiliar de cuentas queda sin <Cuenta> y el XSD lo rechaza.
    doc = generador.generar(db_sesion, cliente, Solicitud(
        "auxiliar_cuentas", 2026, 3, tipo_solicitud="AF", num_orden="ABC1234567/26"))
    assert not doc.valido and doc.errores
    with pytest.raises(FiscalAgentError, match="no valida"):
        generador.empaquetar(doc)


def test_rfc_invalido_y_mes(db_sesion, cliente):
    cliente.rfc = ""
    with pytest.raises(FiscalAgentError, match="RFC"):
        generador.generar(db_sesion, cliente, Solicitud("catalogo", 2026, 3))
    cliente.rfc = RFC
    with pytest.raises(FiscalAgentError):
        generador.generar(db_sesion, cliente, Solicitud("catalogo", 2026, 13))


# ── sello con la e.firma ──


@pytest.fixture
def efirma(db_sesion, mes, monkeypatch):
    monkeypatch.setattr(settings, "LLAVE_MAESTRA", Fernet.generate_key().decode())
    par = certs_sat.generar(rfc=RFC)
    cred_servicio.guardar(db_sesion, mes, "efirma", par.cer, par.key, par.password, "u")
    return cred_servicio.obtener_firmante(db_sesion, mes, "efirma")


def test_sello_con_cadena_original_oficial(db_sesion, mes, efirma):
    doc = generador.generar(db_sesion, mes, Solicitud("catalogo", 2026, 3), firmante=efirma)
    assert doc.sellado and doc.valido and validar_offline("catalogo", doc.xml) == []
    raiz = etree.fromstring(doc.xml)
    assert raiz.get("noCertificado") == efirma.numero_certificado
    cadena = esquemas.cadena_original("catalogo", raiz)
    assert cadena.startswith(f"||1.3|{RFC}|03|2026|") and cadena.endswith("||")
    assert "Sello" not in cadena  # el sello no entra en la cadena original
    cert = load_der_x509_certificate(base64.b64decode(raiz.get("Certificado")))
    cert.public_key().verify(base64.b64decode(raiz.get("Sello")), cadena.encode(),
                             padding.PKCS1v15(), hashes.SHA256())


# ── adaptador buzon_sat ──


def test_buzon_falso_y_portal_por_confirmar(db_sesion, mes):
    doc = generador.generar(db_sesion, mes, Solicitud("catalogo", 2026, 3))
    envio = EnvioContabilidad(RFC, f"{doc.nombre}.zip", generador.empaquetar(doc))
    acuse = BuzonSatFalso().enviar(envio)
    assert acuse.estado == "simulado" and re.fullmatch(r"FALSO-[0-9A-F]{12}", acuse.folio)
    assert BuzonSatFalso().enviar(envio).folio == acuse.folio  # determinístico
    with pytest.raises(FiscalAgentError, match="Nombre de archivo"):
        BuzonSatFalso().enviar(EnvioContabilidad(RFC, "otro.zip", envio.zip_bytes))
    with pytest.raises(FiscalAgentError) as e:
        BuzonSatPortal().enviar(envio)
    assert e.value.status_code == 501


# ── API y multi-tenant ──


def test_api_genera_valida_descarga_y_multitenant(api, sesionador):
    s = sesionador()
    asegurar_usuario(s, "uid-a")
    c = Cliente(despacho_id="uid-a", clave="taller", nombre="Taller", rfc=RFC)
    s.add(c)
    s.flush()
    catalogo.sembrar_base(s, c)
    s.commit()
    s.close()
    a = api("uid-a")
    base = "/api/v1/contabilidad-electronica/clientes/taller"
    r = a.post(f"{base}/validar", json={"documento": "catalogo", "anio": 2026, "mes": 3})
    assert r.status_code == 200 and r.json()["valido"] is True
    r = a.post(f"{base}/zip", json={"documento": "catalogo", "anio": 2026, "mes": 3})
    assert r.status_code == 200
    assert f"{RFC}202603CT.zip" in r.headers["content-disposition"]
    r = a.post(f"{base}/enviar", json={"documento": "catalogo", "anio": 2026, "mes": 3})
    assert r.json()["acuse"]["estado"] == "simulado"
    r = a.post(f"{base}/validar", json={"documento": "polizas", "anio": 2026, "mes": 3})
    assert r.status_code == 422
    docs = a.get("/api/v1/contabilidad-electronica/documentos").json()
    assert len(docs["documentos"]) == 5 and docs["instrucciones_portal"]
    b = api("uid-b")
    assert b.post(f"{base}/validar", json={"documento": "catalogo", "anio": 2026,
                                           "mes": 3}).status_code == 404
    assert b.post(f"{base}/zip", json={"documento": "catalogo", "anio": 2026,
                                       "mes": 3}).status_code == 404
