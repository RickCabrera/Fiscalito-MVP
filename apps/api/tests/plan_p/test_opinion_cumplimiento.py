"""
P1-05: opinión de cumplimiento 32-D y constancia de situación fiscal.

"Listo cuando": con el adaptador falso se obtiene y guarda la opinión de un cliente y se ve su
semáforo en la cartera; las tres vías (portal_sat, proveedor, manual) están implementadas.
El portal del SAT se prueba con páginas simuladas: el flujo real queda POR CONFIRMAR con una
e.firma real.
"""

import base64
import json
from datetime import date, timedelta

import httpx
import pytest
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.x509 import load_der_x509_certificate
from sqlalchemy import select

from app.config import settings
from app.credenciales import servicio as cred_servicio
from app.exceptions import FiscalAgentError
from app.integraciones import registro
from app.integraciones.almacenamiento import AlmacenamientoMemoria
from app.integraciones.comun import ErrorServicioExterno
from app.integraciones.opinion_cumplimiento import (
    URL_OPINION_PDF,
    OpinionFalsa,
    OpinionManual,
    OpinionPortalSat,
    OpinionProveedor,
    SolicitudCumplimiento,
    formulario,
    token_fiel,
)
from app.modelos.nucleo import Cliente
from app.modelos.sat_verificacion import ConfigCumplimiento, DocumentoCumplimiento
from app.sat_verificacion import cumplimiento, pdf
from app.tenancy import asegurar_usuario
from app.trabajos.cola import procesar_siguiente
from tests.plan_p import certs_sat

RFC = "XAXX010101AB1"


def opinion_pdf(sentido: str, fecha: str = "3 de octubre de 2026", rfc: str = RFC) -> bytes:
    return pdf.pdf_texto([
        "OPINION DEL CUMPLIMIENTO DE OBLIGACIONES FISCALES",
        "Folio: 26NA1234567890",
        f"RFC: {rfc}",
        f"Revision practicada el dia {fecha}",
        f"se emite opinion del cumplimiento de obligaciones fiscales en sentido {sentido}",
    ])


# ── lector de PDF ──


@pytest.mark.parametrize("sentido,esperado", [
    ("POSITIVO", "positiva"), ("NEGATIVO", "negativa"),
])
def test_lee_sentido_folio_y_fecha(sentido, esperado):
    leido = pdf.leer_opinion(opinion_pdf(sentido))
    assert (leido.resultado, leido.folio, leido.fecha, leido.rfc) == (
        esperado, "26NA1234567890", date(2026, 10, 3), RFC)


def test_sin_obligaciones_y_pdf_ilegible():
    sin = pdf.pdf_texto(["Opinion: el contribuyente esta INSCRITO SIN OBLIGACIONES",
                         "en sentido POSITIVO"])
    assert pdf.leer_opinion(sin).resultado == "sin_obligaciones"
    assert pdf.leer_opinion(b"%PDF-1.4 basura").resultado == "desconocido"
    with pytest.raises(FiscalAgentError, match="no es un PDF"):
        pdf.validar_pdf(b"hola")


# ── dominio ──


@pytest.fixture
def cliente(db_sesion):
    asegurar_usuario(db_sesion, "uid-a")
    c = Cliente(despacho_id="uid-a", clave="taller", nombre="Taller", rfc=RFC)
    db_sesion.add(c)
    db_sesion.flush()
    return c


def test_falso_obtiene_guarda_y_lee(db_sesion, cliente):
    almacen = AlmacenamientoMemoria()
    falso = OpinionFalsa(fecha_fija=date.today())
    doc = cumplimiento.obtener_y_guardar(db_sesion, cliente, "opinion", falso, "uid-a", almacen)
    assert doc.resultado == "positiva" and doc.lectura == "pdf" and doc.origen == "falso"
    assert doc.folio.startswith("26NA") and doc.fecha == date.today()
    assert cumplimiento.leer_pdf(doc, almacen).startswith(b"%PDF-")
    assert cumplimiento.semaforo(doc) == "verde"
    # Mismo PDF otra vez = mismo renglón.
    otra = cumplimiento.obtener_y_guardar(db_sesion, cliente, "opinion", falso, "uid-a", almacen)
    assert otra.id == doc.id
    constancia = cumplimiento.obtener_y_guardar(db_sesion, cliente, "constancia", falso,
                                                "uid-a", almacen)
    assert constancia.folio == "12345678901" and constancia.resultado == "desconocido"


def test_semaforo():
    def doc(resultado, dias):
        return DocumentoCumplimiento(resultado=resultado,
                                     fecha=date.today() - timedelta(days=dias))
    assert cumplimiento.semaforo(None) == "gris"
    assert cumplimiento.semaforo(doc("positiva", 5)) == "verde"
    assert cumplimiento.semaforo(doc("sin_obligaciones", 5)) == "verde"
    assert cumplimiento.semaforo(doc("positiva", 45)) == "amarillo"
    assert cumplimiento.semaforo(doc("desconocido", 1)) == "amarillo"
    assert cumplimiento.semaforo(doc("negativa", 1)) == "rojo"


def test_pdf_manual_con_resultado_y_aviso_de_rfc(db_sesion, cliente):
    almacen = AlmacenamientoMemoria()
    doc = cumplimiento.guardar_pdf(db_sesion, cliente, "opinion",
                                   opinion_pdf("NEGATIVO", rfc="OTR010101AA1"), "uid-a",
                                   almacen=almacen)
    assert doc.resultado == "negativa" and doc.origen == "manual"
    assert "OTR010101AA1" in doc.datos["aviso"]
    ilegible = pdf.pdf_texto(["escaneado"])
    doc2 = cumplimiento.guardar_pdf(db_sesion, cliente, "opinion", ilegible, "uid-a",
                                    "positiva", almacen)
    assert doc2.resultado == "positiva" and doc2.lectura == "manual"
    with pytest.raises(FiscalAgentError):
        cumplimiento.guardar_pdf(db_sesion, cliente, "opinion", b"no pdf", "uid-a",
                                 almacen=almacen)


def test_manual_no_consulta():
    with pytest.raises(FiscalAgentError) as e:
        OpinionManual().obtener(SolicitudCumplimiento(rfc=RFC, tipo="opinion"))
    assert e.value.status_code == 409


def test_programacion_mensual_por_cliente():
    config = ConfigCumplimiento(automatico=True, dia_del_mes=5, constancia=True)
    ultima = DocumentoCumplimiento(fecha=date(2026, 9, 5))
    assert not cumplimiento.toca_hoy(config, ultima, date(2026, 10, 4))  # aún no es el día
    assert cumplimiento.toca_hoy(config, ultima, date(2026, 10, 5))
    assert cumplimiento.toca_hoy(config, None, date(2026, 10, 20))
    assert not cumplimiento.toca_hoy(config, DocumentoCumplimiento(fecha=date(2026, 10, 1)),
                                     date(2026, 10, 20))  # ya hay una de este mes
    config.automatico = False
    assert not cumplimiento.toca_hoy(config, None, date(2026, 10, 20))


# ── proveedor externo ──


def test_proveedor_generico_con_mapeo(monkeypatch):
    monkeypatch.setenv("FISCALITO_OPINION_PROVEEDOR_URL", "https://prov.example/v1/{tipo}/{rfc}")
    monkeypatch.setenv("FISCALITO_OPINION_PROVEEDOR_API_KEY", "llave-secreta")
    monkeypatch.setenv("FISCALITO_OPINION_PROVEEDOR_ENCABEZADO", "X-Api-Key")
    monkeypatch.setenv("FISCALITO_OPINION_PROVEEDOR_CAMPOS", json.dumps(
        {"pdf_base64": "data.documento", "resultado": "data.sentido", "folio": "data.folio",
         "fecha": "data.emitida"}))
    monkeypatch.setenv("FISCALITO_OPINION_PROVEEDOR_RESULTADOS",
                       json.dumps({"POSITIVO": "positiva", "NEGATIVO": "negativa"}))
    peticiones = []

    def transporte(p):
        peticiones.append(p)
        return httpx.Response(200, json={"data": {
            "documento": base64.b64encode(opinion_pdf("POSITIVO")).decode(),
            "sentido": "NEGATIVO", "folio": "F-1", "emitida": "2026-10-02T10:00:00"}})

    prov = OpinionProveedor(http=httpx.Client(transport=httpx.MockTransport(transporte)))
    r = prov.obtener(SolicitudCumplimiento(rfc=RFC, tipo="opinion"))
    assert str(peticiones[0].url) == f"https://prov.example/v1/opinion/{RFC}"
    assert peticiones[0].headers["X-Api-Key"] == "llave-secreta"
    # Lo que dice el proveedor manda sobre el texto del PDF.
    assert (r.resultado, r.folio, r.fecha) == ("negativa", "F-1", date(2026, 10, 2))


def test_proveedor_pdf_directo_y_errores(monkeypatch):
    monkeypatch.setenv("FISCALITO_OPINION_PROVEEDOR_URL", "https://prov.example/{rfc}")
    monkeypatch.setenv("FISCALITO_OPINION_PROVEEDOR_API_KEY", "k")
    monkeypatch.setenv("FISCALITO_OPINION_PROVEEDOR_METODO", "POST")
    respuestas = [
        httpx.Response(200, content=opinion_pdf("POSITIVO"),
                       headers={"content-type": "application/pdf"}),
        httpx.Response(200, json={"otro": 1}),
        httpx.Response(401, json={"error": "llave"}),
    ]
    vistos = []

    def transporte(p):
        vistos.append(p)
        return respuestas.pop(0)

    prov = OpinionProveedor(http=httpx.Client(transport=httpx.MockTransport(transporte)))
    sol = SolicitudCumplimiento(rfc=RFC, tipo="opinion")
    assert prov.obtener(sol).pdf.startswith(b"%PDF-")
    assert vistos[0].headers["Authorization"] == "Bearer k"
    assert json.loads(vistos[0].content) == {"rfc": RFC, "tipo": "opinion"}
    with pytest.raises(ErrorServicioExterno, match="no trae el PDF"):
        prov.obtener(sol)
    with pytest.raises(ErrorServicioExterno, match="401"):
        prov.obtener(sol)


def test_proveedor_sin_variables_da_503(monkeypatch):
    monkeypatch.delenv("FISCALITO_OPINION_PROVEEDOR_URL", raising=False)
    with pytest.raises(FiscalAgentError) as e:
        OpinionProveedor()
    assert e.value.status_code == 503


# ── portal del SAT (páginas simuladas) ──


@pytest.fixture
def firmante(db_sesion, cliente, monkeypatch):
    monkeypatch.setattr(settings, "LLAVE_MAESTRA", Fernet.generate_key().decode())
    par = certs_sat.generar(rfc=RFC)
    cred_servicio.guardar(db_sesion, cliente, "efirma", par.cer, par.key, par.password, "u")
    return cred_servicio.obtener_firmante(db_sesion, cliente, "efirma"), par


def test_token_fiel_verificable_con_el_certificado(firmante):
    f, par = firmante
    token = base64.b64decode(token_fiel(f, "GUID-123"))
    cadena_b64, firma_b64 = token.split(b"#")
    cadena = base64.b64decode(cadena_b64)
    assert cadena == f"GUID-123|{RFC}|{par.numero}".encode()
    firma = base64.b64decode(base64.b64decode(firma_b64))
    load_der_x509_certificate(par.cer).public_key().verify(
        firma, cadena, padding.PKCS1v15(), hashes.SHA1())


def test_formulario_lee_action_relativa_e_inputs():
    html = ('<html><form id="certform" method="post" action="/nidp/app/login?sid=1">'
            '<input name="guid" value="G1"/><input name="token"/><input type="submit"/>'
            "</form></html>")
    accion, datos = formulario(html, "https://loginda.siat.sat.gob.mx/nidp/x", "certform")
    assert accion == "https://loginda.siat.sat.gob.mx/nidp/app/login?sid=1"
    assert datos == {"guid": "G1", "token": ""}
    assert formulario("", "https://x/") == (None, {})


class PortalSimulado:
    """Imita las páginas que python-satcfdi espera ver. No es el SAT."""

    def __init__(self, cambiado: bool = False) -> None:
        self.cambiado = cambiado
        self.peticiones: list[httpx.Request] = []
        self.token = ""

    def __call__(self, p: httpx.Request) -> httpx.Response:
        self.peticiones.append(p)
        url = str(p.url)
        if url.startswith("https://ptsc32d.clouda.sat.gob.mx/?"):
            return httpx.Response(200, text=(
                '<form method="post" action="https://loginda.siat.sat.gob.mx/nidp/app/login'
                '?id=ciec"><input name="x" value="1"/></form>'))
        if "nidp/app/login?id=fiel" in url:
            if self.cambiado:
                return httpx.Response(200, text="<html>nuevo portal</html>")
            return httpx.Response(200, text=(
                '<form id="certform" method="post" action="/nidp/app/login?sid=0">'
                '<input name="guid" value="GUID-XYZ"/><input name="token"/>'
                '<input name="fert"/></form>'))
        if "nidp/app/login?sid=0" in url:
            datos = dict(httpx.QueryParams(p.content.decode()))
            self.token = datos["token"]
            assert datos["guid"] == "GUID-XYZ" and len(datos["fert"]) == 13
            return httpx.Response(200, text="<script>top.location.href='https://ptsc32d."
                                            "clouda.sat.gob.mx/oauth?code=1';</script>")
        if "oauth?code=1" in url:
            return httpx.Response(200, text="<html>listo</html>")
        if url == URL_OPINION_PDF:
            cuerpo = json.loads(p.content)
            assert cuerpo["rfc"] == RFC and cuerpo["tipoReporte"] == "32D"
            return httpx.Response(200, json={
                "ContenidoBase64": base64.b64encode(opinion_pdf("POSITIVO")).decode()})
        raise AssertionError(f"Petición inesperada: {p.method} {url}")


def test_portal_sat_flujo_simulado(firmante):
    f, _par = firmante
    portal = PortalSimulado()
    adaptador = OpinionPortalSat(http=httpx.Client(transport=httpx.MockTransport(portal),
                                                   follow_redirects=True))
    r = adaptador.obtener(SolicitudCumplimiento(rfc=RFC, tipo="opinion", firmante=lambda: f))
    assert pdf.leer_opinion(r.pdf).resultado == "positiva"
    assert portal.token  # se mandó el token firmado
    assert any("id=fiel" in str(p.url) for p in portal.peticiones)


def test_portal_sat_cambiado_falla_con_mensaje_claro(firmante):
    f, _par = firmante
    adaptador = OpinionPortalSat(http=httpx.Client(
        transport=httpx.MockTransport(PortalSimulado(cambiado=True)), follow_redirects=True))
    with pytest.raises(ErrorServicioExterno, match="portal del SAT cambió en el paso 'login"):
        adaptador.obtener(SolicitudCumplimiento(rfc=RFC, tipo="opinion", firmante=lambda: f))


def test_portal_sat_sin_efirma_da_404(db_sesion, cliente):
    with pytest.raises(FiscalAgentError) as e:
        cumplimiento.obtener_y_guardar(db_sesion, cliente, "opinion", OpinionPortalSat(),
                                       "uid-a", AlmacenamientoMemoria())
    assert e.value.status_code == 404


def test_registro_cuatro_vias():
    estado = {s["servicio"]: s for s in registro.verificar_configuracion()}
    assert set(estado["opinion_cumplimiento"]["disponibles"]) == {
        "falso", "portal_sat", "proveedor", "manual"}


# ── rutas ──


@pytest.fixture
def con_clientes(sesionador, tmp_path, monkeypatch):
    monkeypatch.setenv("FISCALITO_ALMACEN_DIR", str(tmp_path / "almacen"))
    monkeypatch.delenv("FISCALITO_ALMACENAMIENTO", raising=False)
    monkeypatch.delenv("FISCALITO_OPINION_CUMPLIMIENTO", raising=False)
    db = sesionador()
    asegurar_usuario(db, "uid-a")
    asegurar_usuario(db, "uid-b")
    db.add_all([Cliente(despacho_id="uid-a", clave="taller", nombre="T", rfc=RFC),
                Cliente(despacho_id="uid-a", clave="sinrfc", nombre="S", rfc=""),
                Cliente(despacho_id="uid-b", clave="otro", nombre="O", rfc=RFC)])
    db.commit()
    db.close()


def test_api_obtener_ahora_y_semaforo_en_cartera(api, con_clientes, sesionador):
    """El "Listo cuando" de P1-05."""
    a = api("uid-a")
    r = a.post("/api/v1/sat/clientes/taller/opinion/obtener")
    assert r.status_code == 200, r.text
    assert r.json()["trabajo"]["tipo"] == "sat.cumplimiento_obtener"
    assert procesar_siguiente(sesionador).estado == "hecho"

    h = a.get("/api/v1/sat/clientes/taller/opinion").json()
    assert h["semaforo"] == "verde" and h["ultimo"]["resultado"] == "positiva"
    assert h["via"] == "falso" and len(h["historial"]) == 1
    assert h["config"] == {"automatico": True, "dia_del_mes": 1, "constancia": True}

    cartera = {c["clave"]: c for c in a.get("/api/v1/sat/cartera/semaforo").json()["clientes"]}
    assert cartera["taller"]["opinion"]["semaforo"] == "verde"
    assert cartera["sinrfc"]["opinion"]["semaforo"] == "gris"

    doc_id = h["ultimo"]["id"]
    d = a.get(f"/api/v1/sat/clientes/taller/opinion/{doc_id}/pdf")
    assert d.status_code == 200 and d.content.startswith(b"%PDF-")
    assert d.headers["content-type"] == "application/pdf"

    assert a.post("/api/v1/sat/clientes/taller/opinion/obtener",
                  params={"tipo": "constancia"}).status_code == 200
    assert procesar_siguiente(sesionador).estado == "hecho"
    c = a.get("/api/v1/sat/clientes/taller/constancia").json()
    assert c["ultimo"]["folio"] == "12345678901"

    assert a.post("/api/v1/sat/clientes/sinrfc/opinion/obtener").status_code == 422


def test_api_subir_pdf_config_y_multitenant(api, con_clientes, monkeypatch):
    a = api("uid-a")
    r = a.post("/api/v1/sat/clientes/taller/opinion/pdf",
               files={"archivo": ("op.pdf", opinion_pdf("NEGATIVO"), "application/pdf")},
               data={"tipo": "opinion"})
    assert r.status_code == 200, r.text
    assert r.json()["semaforo"] == "rojo" and r.json()["documento"]["origen"] == "manual"
    assert a.post("/api/v1/sat/clientes/taller/opinion/pdf",
                  files={"archivo": ("x.pdf", b"nada", "application/pdf")}).status_code == 422

    assert a.put("/api/v1/sat/clientes/taller/opinion/config",
                 json={"automatico": False, "dia_del_mes": 10, "constancia": False}
                 ).status_code == 200
    assert a.get("/api/v1/sat/clientes/taller/opinion").json()["config"]["dia_del_mes"] == 10
    assert a.put("/api/v1/sat/clientes/taller/opinion/config",
                 json={"dia_del_mes": 31}).status_code == 422

    doc_id = a.get("/api/v1/sat/clientes/taller/opinion").json()["ultimo"]["id"]
    b = api("uid-b")
    assert b.get("/api/v1/sat/clientes/taller/opinion").status_code == 404
    assert b.get(f"/api/v1/sat/clientes/taller/opinion/{doc_id}/pdf").status_code == 404
    assert b.get(f"/api/v1/sat/clientes/otro/opinion/{doc_id}/pdf").status_code == 404
    assert b.post("/api/v1/sat/clientes/taller/opinion/obtener").status_code == 404
    assert [c["clave"] for c in b.get("/api/v1/sat/cartera/semaforo").json()["clientes"]] == [
        "otro"]

    monkeypatch.setenv("FISCALITO_OPINION_CUMPLIMIENTO", "manual")
    registro.limpiar_cache()
    assert a.post("/api/v1/sat/clientes/taller/opinion/obtener").status_code == 409
    assert a.get("/api/v1/sat/clientes/taller/opinion").json()["via"] == "manual"


def test_programado_encola_a_quien_le_toca(sesionador):
    import app.trabajos.manejadores as m
    from app.trabajos.cola import encolar

    m.cargar_manejadores()
    with sesionador() as db:
        asegurar_usuario(db, "uid-a")
        a = Cliente(despacho_id="uid-a", clave="a", nombre="A", rfc=RFC)
        b = Cliente(despacho_id="uid-a", clave="b", nombre="B", rfc="OTR010101AA1")
        db.add_all([a, b])
        db.flush()
        db.add(ConfigCumplimiento(cliente_id=b.id, automatico=False))
        encolar(db, "sat.cumplimiento_programado", {})
        db.commit()
    t = procesar_siguiente(sesionador)
    assert t.resultado == {"encolados": 2}  # opinión + constancia de A; B está apagado
    from app.modelos.trabajos import Trabajo

    with sesionador() as db:
        tipos = sorted(x.carga["tipo"] for x in db.scalars(
            select(Trabajo).where(Trabajo.tipo == "sat.cumplimiento_obtener")))
    assert tipos == ["constancia", "opinion"]
