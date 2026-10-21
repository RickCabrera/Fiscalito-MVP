"""
P4-13 · Envío de recibos con los adaptadores FALSOS de correo y WhatsApp: cada trabajador
recibe lo suyo, reintentar no duplica, fallos se reintentan, plantillas por despacho,
enlace firmado, auditoría y multi-tenant.
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.integraciones import registro
from app.main import app
from app.modelos.auditoria import EventoAuditoria
from app.nomina_envio import plantillas
from app.trabajos.cola import procesar_siguiente
from tests.plan_p.nomina_cerrada import nomina_cerrada

ENVIOS = "/api/v1/nomina/clientes/{c}/periodos/{p}/envios"


@pytest.fixture(autouse=True)
def _adaptadores_limpios():
    registro.limpiar_cache()
    yield
    registro.limpiar_cache()


def _correr(sesionador, veces=1):
    for _ in range(veces):
        procesar_siguiente(sesionador)


def _correo():
    return registro.obtener("correo")


def _wa():
    return registro.obtener("whatsapp")


def test_correo_entrega_a_cada_trabajador_su_recibo_y_no_duplica(api, sesionador):
    n = nomina_cerrada(api, sesionador, uid="uid-env")
    url = ENVIOS.format(c=n["clave"], p=n["pid"])
    r = n["http"].post(url, json={"canal": "correo"})
    assert r.status_code == 200, r.text
    j = r.json()
    # E4 y E5 no tienen correo; E3 sí (aunque cobre en efectivo, el recibo se le manda).
    assert {o["empleado_no"] for o in j["omitidos"]} == {"E4", "E5"}
    assert j["resumen"]["pendiente"] == 3 and j["trabajo"]["estado"] == "pendiente"
    _correr(sesionador)
    enviados = _correo().enviados
    assert sorted(m.destinatarios[0] for m in enviados) == [
        "ana@ejemplo.mx", "e3@ejemplo.mx", "luis@ejemplo.mx"]
    por_correo = {m.destinatarios[0]: m for m in enviados}
    ana = por_correo["ana@ejemplo.mx"]
    assert "PERSONA E1" in ana.html and n["netos"]["E1"] in ana.html.replace(",", "")
    assert [a.nombre for a in ana.adjuntos] == ["recibo_20260816_E1_SIN_TIMBRAR.pdf"]
    assert ana.adjuntos[0].contenido.startswith(b"%PDF")
    assert "16/08/2026 al 31/08/2026" in ana.asunto
    # Pedirlo otra vez y volver a correr el trabajo NO duplica.
    j2 = n["http"].post(url, json={"canal": "correo"}).json()
    assert j2["resumen"]["enviado"] == 3
    _correr(sesionador, 2)
    assert len(_correo().enviados) == 3
    estado = n["http"].get(url, params={"canal": "correo"}).json()
    assert all(e["estado"] == "enviado" and e["intentos"] == 1 for e in estado["envios"])


def test_whatsapp_usa_plantilla_aprobada_con_documento_firmado(api, sesionador):
    n = nomina_cerrada(api, sesionador, uid="uid-wa")
    url = ENVIOS.format(c=n["clave"], p=n["pid"])
    j = n["http"].post(url, json={"canal": "whatsapp"}).json()
    motivos = {o["empleado_no"]: o["motivo"] for o in j["omitidos"]}
    assert "consentimiento" in motivos["E2"] and "celular" in motivos["E4"]
    _correr(sesionador)
    enviados = {m["telefono"]: m for m in _wa().enviados}
    assert set(enviados) == {"+525512345678", "+525599998888"}
    m = enviados["+525512345678"]
    assert m["tipo"] == "plantilla" and m["plantilla"] == "recibo_nomina"
    assert m["parametros"][0] == "PERSONA E1" and m["parametros"][1] == "16/08/2026 al 31/08/2026"
    doc = m["documento"]
    assert doc.nombre.endswith("_E1_SIN_TIMBRAR.pdf")
    # El enlace firmado baja el PDF sin sesión; alterado o ajeno, 404.
    u = urlparse(doc.url)
    publico = TestClient(app)
    ok = publico.get(u.path, params={k: v[0] for k, v in parse_qs(u.query).items()})
    assert ok.status_code == 200 and ok.content.startswith(b"%PDF")
    q = parse_qs(u.query)
    malo = publico.get(u.path, params={"vence": q["vence"][0], "firma": "0" * 64})
    assert malo.status_code == 404
    otro = publico.get(u.path.replace("recibo.pdf", "recibo.xml"),
                       params={"vence": q["vence"][0], "firma": q["firma"][0]})
    assert otro.status_code == 404


def test_fallo_se_reintenta_sin_duplicar_y_reenvio_individual(api, sesionador, monkeypatch):
    n = nomina_cerrada(api, sesionador, uid="uid-falla")
    url = ENVIOS.format(c=n["clave"], p=n["pid"])
    correo = _correo()
    original = correo.enviar
    fallar = {"luis@ejemplo.mx"}

    def enviar(destinatarios, asunto, html, adjuntos=()):
        if destinatarios[0] in fallar:
            raise RuntimeError("SMTP caído")
        return original(destinatarios, asunto, html, adjuntos)

    monkeypatch.setattr(correo, "enviar", enviar)
    n["http"].post(url, json={"canal": "correo"})
    from datetime import timedelta

    from app.db.base import ahora

    procesar_siguiente(sesionador)
    estado = {e["empleado_no"]: e for e in
              n["http"].get(url, params={"canal": "correo"}).json()["envios"]}
    assert estado["E2"]["estado"] == "fallido" and "SMTP" in estado["E2"]["error"]
    assert len(correo.enviados) == 2
    fallar.clear()
    procesar_siguiente(sesionador, ahora=ahora() + timedelta(hours=2))  # tras el backoff
    estado = {e["empleado_no"]: e for e in
              n["http"].get(url, params={"canal": "correo"}).json()["envios"]}
    assert estado["E2"]["estado"] == "enviado" and estado["E2"]["intentos"] == 2
    assert sorted(m.destinatarios[0] for m in correo.enviados) == [
        "ana@ejemplo.mx", "e3@ejemplo.mx", "luis@ejemplo.mx"]
    # Reenviar a uno a propósito manda exactamente uno más.
    r = n["http"].post(f"{url}/{estado['E1']['id']}/reenviar")
    assert r.status_code == 200
    procesar_siguiente(sesionador, ahora=ahora() + timedelta(hours=3))
    assert [m.destinatarios[0] for m in correo.enviados].count("ana@ejemplo.mx") == 2
    assert len(correo.enviados) == 4


def test_plantillas_editables_por_despacho_y_rebote(api, sesionador):
    n = nomina_cerrada(api, sesionador, uid="uid-pl")
    http = n["http"]
    r = http.put("/api/v1/nomina/recibos/plantillas/correo", json={
        "asunto": "Recibo {periodo} de {nombre}", "cuerpo": "<p>{nombre}: {neto} {otra}</p>"})
    assert r.status_code == 200 and r.json()["personalizada"] is True
    otro = api("uid-otro").get("/api/v1/nomina/recibos/plantillas").json()["plantillas"]
    assert otro[0]["asunto"] == plantillas.DEFAULTS["correo"]["asunto"]
    url = ENVIOS.format(c=n["clave"], p=n["pid"])
    http.post(url, json={"canal": "correo"})
    _correr(sesionador)
    m = next(x for x in _correo().enviados if x.destinatarios[0] == "ana@ejemplo.mx")
    assert m.asunto == "Recibo 16/08/2026 al 31/08/2026 de PERSONA E1"
    assert "{otra}" in m.html  # una llave desconocida no tumba el envío
    estado = http.get(url, params={"canal": "correo"}).json()["envios"]
    id_msg = None
    s = sesionador()
    from app.modelos.nomina_envio import EnvioRecibo

    id_msg = s.get(EnvioRecibo, estado[0]["id"]).id_mensaje
    s.close()
    rb = http.post("/api/v1/nomina/recibos/envios/rebote",
                   json={"canal": "correo", "id_mensaje": id_msg})
    assert rb.status_code == 200 and rb.json()["estado"] == "rebotado"
    assert api("uid-otro").post("/api/v1/nomina/recibos/envios/rebote",
                                json={"canal": "correo", "id_mensaje": id_msg}).status_code == 404
    s = sesionador()
    acciones = {e.accion for e in s.scalars(select(EventoAuditoria).where(
        EventoAuditoria.despacho_id == "uid-pl"))}
    s.close()
    assert {"nomina.recibos.enviar", "nomina.recibos.enviados", "nomina.recibos.plantilla",
            "nomina.recibos.rebote"} <= acciones


def test_renderizar_escapa_html():
    assert plantillas.renderizar("{nombre}", {"nombre": "<b>"}, escapar=True) == "&lt;b&gt;"


def test_multitenant_y_nomina_abierta(api, sesionador):
    n = nomina_cerrada(api, sesionador, uid="uid-mt2")
    url = ENVIOS.format(c=n["clave"], p=n["pid"])
    ajeno = api("uid-ajeno2")
    assert ajeno.post(url, json={"canal": "correo"}).status_code == 404
    assert ajeno.get(url).status_code == 404
    n["http"].post(url, json={"canal": "correo"})
    eid = n["http"].get(url).json()["envios"][0]["id"]
    assert ajeno.post(f"{url}/{eid}/reenviar").status_code == 404
    r = n["http"].post("/api/v1/nomina/calcular-periodo", json={
        "cliente": n["clave"], "periodo": {"inicio": "2026-09-01", "fin": "2026-09-15"},
        "incidencias": [{"empleado_no": "E1", "dias_periodo": 15, "faltas": 0,
                         "dias_ausentismo": 0}]})
    abierto = ENVIOS.format(c=n["clave"], p=r.json()["periodo_id"])
    assert n["http"].post(abierto, json={"canal": "correo"}).status_code == 409


def test_recibo_timbrado_adjunta_su_xml_y_no_el_pdf_sin_timbrar(api, sesionador, monkeypatch,
                                                                 tmp_path):
    from datetime import datetime

    from app.modelos.cfdi import Comprobante
    from app.modelos.nomina import NominaPeriodo, ReciboNomina

    monkeypatch.setenv("FISCALITO_ALMACEN_DIR", str(tmp_path))
    registro.limpiar_cache()
    n = nomina_cerrada(api, sesionador, uid="uid-timb")
    s = sesionador()
    rec = s.scalar(select(ReciboNomina).where(ReciboNomina.periodo_id == n["pid"],
                                              ReciboNomina.empleado_no == "E1"))
    uuid = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"
    rec.uuid_cfdi = uuid
    registro.obtener("almacenamiento").guardar(b"<cfdi:Comprobante/>", "cfdi/x/E1.xml")
    s.add(Comprobante(cliente_id=s.get(NominaPeriodo, n["pid"]).cliente_id, uuid=uuid,
                      version="4.0", tipo="N", fecha=datetime(2026, 8, 31),
                      rfc_emisor="EKU9003173C9", rfc_receptor="XAXX010101000",
                      direccion="emitido", ruta_xml="cfdi/x/E1.xml", sha256="0" * 64))
    s.commit()
    s.close()
    n["http"].post(ENVIOS.format(c=n["clave"], p=n["pid"]), json={"canal": "correo"})
    _correr(sesionador)
    ana = next(m for m in _correo().enviados if m.destinatarios[0] == "ana@ejemplo.mx")
    assert [a.nombre for a in ana.adjuntos] == ["recibo_20260816_E1.xml"]
    assert ana.adjuntos[0].contenido == b"<cfdi:Comprobante/>"


def test_whatsapp_meta_manda_el_documento_en_el_encabezado_de_la_plantilla():
    import json

    import httpx

    from app.integraciones.whatsapp import DocumentoPlantilla, WhatsAppMeta

    vistos = []

    def responder(req):
        vistos.append(json.loads(req.content))
        return httpx.Response(200, json={"messages": [{"id": "wamid.1"}]})

    wa = WhatsAppMeta("t", "123", "s", http=httpx.Client(transport=httpx.MockTransport(responder)))
    doc = DocumentoPlantilla("https://x/r.pdf", "r.pdf")
    assert wa.enviar_plantilla("+525512345678", "recibo_nomina", "es_MX", ["A", "B", "C"],
                               documento=doc) == "wamid.1"
    comp = vistos[0]["template"]["components"]
    assert comp[0] == {"type": "header", "parameters": [
        {"type": "document", "document": {"link": "https://x/r.pdf", "filename": "r.pdf"}}]}
    assert [p["text"] for p in comp[1]["parameters"]] == ["A", "B", "C"]
