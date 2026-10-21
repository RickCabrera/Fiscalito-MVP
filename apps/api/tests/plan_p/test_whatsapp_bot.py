"""
P5-06 · Bot de WhatsApp con IA.

"Listo cuando": con el adaptador falso, una conversación de prueba entrega el PDF correcto al
cliente correcto y rechaza números no registrados; prueba multi-tenant. Además: firma del
webhook, idempotencia ante reintentos de Meta, límite por número, bitácora, y que el texto con
cifras sale del motor, nunca del modelo.
"""

from __future__ import annotations

import hashlib
import hmac
import io
import json
import zipfile
from datetime import datetime
from urllib.parse import urlparse

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.acceso.llm import ZONA
from app.asistente import consultas
from app.boveda_cfdi import servicio as boveda
from app.integraciones import registro
from app.integraciones.llm import LlamadaHerramienta, RespuestaLLM
from app.main import app
from app.modelos.nucleo import Cliente
from app.modelos.trabajos import Trabajo
from app.modelos.whatsapp import MensajeWhatsApp
from app.sat_verificacion import cumplimiento, pdf
from app.tenancy import asegurar_usuario
from app.trabajos.cola import procesar_siguiente
from app.whatsapp_bot import servicio
from tests.plan_p.cfdi_sintetico import RFC_CLIENTE, RFC_PROVEEDOR, cfdi, uuid_n

RFC_B = "XBXX020202BC2"
TEL_A, TEL_B, TEL_AMBOS = "+525511111111", "+525522222222", "+525533333333"
WEBHOOK = "/api/v1/whatsapp/webhook"


@pytest.fixture(autouse=True)
def _limpio(tmp_path, monkeypatch):
    monkeypatch.setenv("FISCALITO_ALMACEN_DIR", str(tmp_path / "almacen"))
    for var in ("FISCALITO_LLM", "FISCALITO_WHATSAPP", "FISCALITO_ALMACENAMIENTO",
                "FISCALITO_URL_PUBLICA_API"):
        monkeypatch.delenv(var, raising=False)
    registro.limpiar_cache()
    yield
    registro.limpiar_cache()


def _wa():
    return registro.obtener("whatsapp")


def _llm():
    return registro.obtener("llm")


def _opinion(rfc: str, sentido: str) -> bytes:
    return pdf.pdf_texto(["OPINION DEL CUMPLIMIENTO DE OBLIGACIONES FISCALES",
                          "Folio: 26NA1234567890", f"RFC: {rfc}",
                          "Revision practicada el dia 3 de octubre de 2026",
                          f"se emite opinion del cumplimiento de obligaciones fiscales en "
                          f"sentido {sentido}"])


@pytest.fixture
def escenario(api, sesionador):
    """Despacho A (cliente taller) y despacho B (cliente ferre), cada uno con su opinión."""
    pdfs = {}
    with sesionador() as db:
        for uid, clave, rfc, sentido in (("uid-a", "taller", RFC_CLIENTE, "POSITIVO"),
                                         ("uid-b", "ferre", RFC_B, "NEGATIVO")):
            asegurar_usuario(db, uid)
            c = Cliente(despacho_id=uid, clave=clave, nombre=clave.title(), rfc=rfc,
                        datos={"regimen": "612"})
            db.add(c)
            db.flush()
            pdfs[clave] = _opinion(rfc, sentido)
            cumplimiento.guardar_pdf(db, c, "opinion", pdfs[clave], uid)
        taller = db.scalar(select(Cliente).where(Cliente.clave == "taller"))
        boveda.importar(db, taller, [
            ("a.xml", io.BytesIO(cfdi(uuid_n(1), fecha="2026-03-05T10:00:00"))),
            ("b.xml", io.BytesIO(cfdi(uuid_n(2), emisor=RFC_PROVEEDOR, receptor=RFC_CLIENTE,
                                      fecha="2026-03-11T10:00:00"))),
        ])
        db.commit()
    a, b = api("uid-a"), api("uid-b")
    for http, clave, tel in ((a, "taller", TEL_A), (b, "ferre", TEL_B),
                             (a, "taller", TEL_AMBOS), (b, "ferre", TEL_AMBOS[3:])):
        r = http.post(f"/api/v1/whatsapp/clientes/{clave}/contactos",
                      json={"telefono": tel, "nombre": "Dueño", "consentimiento": True})
        assert r.status_code == 200, r.text
    return {"a": a, "b": b, "pdfs": pdfs, "sesionador": sesionador}


def _cuerpo(telefono: str, texto: str, id_: str) -> bytes:
    """Lo que manda la Cloud API de Meta (número sin `+`, como llega de verdad)."""
    return json.dumps({"entry": [{"changes": [{"value": {"messages": [{
        "from": telefono.lstrip("+"), "id": id_, "type": "text", "text": {"body": texto}}]}}]}]
    }).encode()


def _firmar(cuerpo: bytes, secreto: str = "secreto-falso") -> dict[str, str]:
    firma = hmac.new(secreto.encode(), cuerpo, hashlib.sha256).hexdigest()
    return {"X-Hub-Signature-256": f"sha256={firma}", "Content-Type": "application/json"}


def _publico() -> TestClient:
    return TestClient(app)  # sin sesión: así llega Meta


def _escribir(sesionador, telefono: str, texto: str, id_: str,
              intencion: RespuestaLLM | None = None) -> dict:
    if intencion is not None:
        _llm().respuestas.append(intencion)
    cuerpo = _cuerpo(telefono, texto, id_)
    r = _publico().post(WEBHOOK, content=cuerpo, headers=_firmar(cuerpo))
    assert r.status_code == 200, r.text
    while procesar_siguiente(sesionador) is not None:
        pass
    return r.json()


def _pide(nombre: str, args: dict | None = None) -> RespuestaLLM:
    return RespuestaLLM(texto="", llamadas=[LlamadaHerramienta("i1", nombre, args or {})])


def _bajar(url: str) -> bytes:
    p = urlparse(url)
    r = _publico().get(f"{p.path}?{p.query}")
    assert r.status_code == 200, r.text
    return r.content


# ── Listo cuando ──


def test_cada_cliente_recibe_su_propio_pdf(escenario):
    s = escenario["sesionador"]
    _escribir(s, TEL_A, "mándame mi opinión de cumplimiento", "wamid.1",
              _pide("enviar_opinion_cumplimiento"))
    _escribir(s, TEL_B, "opinión porfa", "wamid.2", _pide("enviar_opinion_cumplimiento"))
    a, b = _wa().enviados
    assert (a["tipo"], a["telefono"], a["nombre"]) == ("documento", TEL_A, "opinion.pdf")
    assert (b["tipo"], b["telefono"]) == ("documento", TEL_B)
    assert "positiva" in a["leyenda"] and "negativa" in b["leyenda"]
    assert _bajar(a["url"]) == escenario["pdfs"]["taller"]
    assert _bajar(b["url"]) == escenario["pdfs"]["ferre"]
    # El LLM sólo vio el texto del cliente y las intenciones; no recibió datos fiscales.
    vistos = _llm().llamadas[0]
    assert vistos["mensajes"][-1] == {"role": "user",
                                      "content": "mándame mi opinión de cumplimiento"}
    # Bitácora: cada despacho ve SOLO su conversación.
    conv_a = escenario["a"].get("/api/v1/whatsapp/clientes/taller/conversacion").json()
    assert [(m["direccion"], m["estado"]) for m in conv_a["mensajes"]] == [
        ("entrante", "respondido"), ("saliente", "enviado")]
    assert conv_a["mensajes"][0]["intencion"] == "enviar_opinion_cumplimiento"
    assert conv_a["mensajes"][1]["documento"] == "opinion.pdf"
    assert escenario["b"].get(
        "/api/v1/whatsapp/clientes/taller/conversacion").status_code == 404


def test_numero_no_registrado_se_rechaza_sin_llm_ni_datos(escenario):
    s = escenario["sesionador"]
    _escribir(s, "+525599999999", "mándame la opinión de XEXX010101AB1", "wamid.x1")
    _escribir(s, "+525599999999", "¿y mis facturas?", "wamid.x2")
    assert _llm().llamadas == []
    assert [e["tipo"] for e in _wa().enviados] == ["texto"]  # un solo aviso por día
    assert "no está registrado" in _wa().enviados[0]["texto"]
    with s() as db:
        entrantes = list(db.scalars(select(MensajeWhatsApp).where(
            MensajeWhatsApp.direccion == "entrante")))
    assert {m.estado for m in entrantes} == {"rechazado"}
    assert all(m.texto == "" and "texto_pendiente" not in m.detalle and m.cliente_id is None
               for m in entrantes)


def test_numero_de_dos_despachos_pide_el_rfc_y_luego_entrega_el_correcto(escenario):
    s = escenario["sesionador"]
    _escribir(s, TEL_AMBOS, "mi opinión", "wamid.m1")
    assert _llm().llamadas == [] and "RFC" in _wa().enviados[-1]["texto"]
    _escribir(s, TEL_AMBOS, f"mi opinión {RFC_B.lower()}", "wamid.m2",
              _pide("enviar_opinion_cumplimiento"))
    assert _bajar(_wa().enviados[-1]["url"]) == escenario["pdfs"]["ferre"]
    _escribir(s, TEL_AMBOS, f"opinión {RFC_CLIENTE}", "wamid.m3",
              _pide("enviar_opinion_cumplimiento"))
    assert _bajar(_wa().enviados[-1]["url"]) == escenario["pdfs"]["taller"]


# ── Las otras intenciones ──


def test_facturas_del_mes_van_en_zip_con_resumen_de_la_boveda(escenario):
    s = escenario["sesionador"]
    _escribir(s, TEL_A, "mis facturas de marzo", "wamid.f1",
              _pide("enviar_facturas_del_mes", {"anio": 2026, "mes": 3}))
    e = _wa().enviados[-1]
    assert e["nombre"] == "facturas.zip"
    assert "1 emitidas tipo I por $1,160.00" in e["leyenda"]
    with zipfile.ZipFile(io.BytesIO(_bajar(e["url"]))) as z:
        assert sorted(z.namelist()) == [f"{uuid_n(1)}.xml", f"{uuid_n(2)}.xml"]


def test_cuanto_pago_este_mes_lo_dice_el_motor(escenario):
    s = escenario["sesionador"]
    _escribir(s, TEL_A, "¿cuánto pago este mes?", "wamid.p1", _pide("consultar_pago_del_mes"))
    texto = _wa().enviados[-1]["texto"]
    hoy = datetime.now(ZONA).date()
    with s() as db:
        taller = db.scalar(select(Cliente).where(Cliente.clave == "taller"))
        esperado = consultas.impuestos_mes(db, taller, *consultas.periodo_que_vence(hoy), hoy)
    assert f"${float(esperado['total_a_pagar']):,.2f}" in texto
    assert "tu contador la confirma" in texto


def test_texto_libre_del_modelo_con_cifras_no_sale(escenario):
    s = escenario["sesionador"]
    _escribir(s, TEL_A, "hola", "wamid.t1", RespuestaLLM(texto="¡Hola! Pagas $5,000."))
    assert _wa().enviados[-1]["texto"] == servicio.MENU
    _escribir(s, TEL_A, "gracias", "wamid.t2", RespuestaLLM(texto="¡Con gusto!"))
    assert _wa().enviados[-1]["texto"] == "¡Con gusto!"


def test_sin_opinion_guardada_lo_dice(escenario):
    s = escenario["sesionador"]
    _escribir(s, TEL_A, "mi constancia", "wamid.c1", _pide("enviar_constancia"))
    assert "Aún no tenemos tu constancia" in _wa().enviados[-1]["texto"]


# ── Webhook: firma, reintentos, límite ──


def test_firma_invalida_es_401_y_no_se_anota_nada(escenario):
    cuerpo = _cuerpo(TEL_A, "opinión", "wamid.f")
    r = _publico().post(WEBHOOK, content=cuerpo, headers=_firmar(cuerpo, "otro-secreto"))
    assert r.status_code == 401
    r = _publico().post(WEBHOOK, content=cuerpo, headers={"Content-Type": "application/json"})
    assert r.status_code == 401
    with escenario["sesionador"]() as db:
        assert db.scalar(select(MensajeWhatsApp.id)) is None


def test_reintento_de_meta_no_contesta_dos_veces(escenario):
    s = escenario["sesionador"]
    _escribir(s, TEL_A, "opinión", "wamid.r", _pide("enviar_opinion_cumplimiento"))
    j = _escribir(s, TEL_A, "opinión", "wamid.r")
    assert j["repetidos"] == 1 and len(_wa().enviados) == 1


def test_limite_por_numero(escenario, monkeypatch):
    monkeypatch.setenv("FISCALITO_WHATSAPP_BOT_POR_MINUTO", "2")
    s = escenario["sesionador"]
    _llm().respuestas += [RespuestaLLM(texto="hola"), RespuestaLLM(texto="hola")]
    for n in range(3):
        _escribir(s, TEL_A, "hola", f"wamid.l{n}")
    with s() as db:
        estados = [m.estado for m in db.scalars(select(MensajeWhatsApp).where(
            MensajeWhatsApp.direccion == "entrante").order_by(MensajeWhatsApp.id))]
        trabajos = db.scalars(select(Trabajo).where(Trabajo.tipo == servicio.TIPO_TRABAJO))
        assert estados == ["respondido", "respondido", "limitado"] and len(list(trabajos)) == 2
    assert len(_wa().enviados) == 2


def test_tope_diario_del_despacho_corta_el_llm(escenario, monkeypatch):
    monkeypatch.setenv("FISCALITO_TOPE_LLM_DIARIO_LLAMADAS", "1")
    s = escenario["sesionador"]
    _escribir(s, TEL_A, "hola", "wamid.d1", RespuestaLLM(texto="hola"))
    _escribir(s, TEL_A, "hola otra vez", "wamid.d2")
    assert len(_llm().llamadas) == 1 and _wa().enviados[-1]["texto"] == servicio.TOPE


def test_verificacion_de_suscripcion(monkeypatch):
    q = {"hub.mode": "subscribe", "hub.verify_token": "mi-token", "hub.challenge": "123"}
    assert _publico().get(WEBHOOK, params=q).status_code == 403  # sin variable: cerrado
    monkeypatch.setenv("FISCALITO_WHATSAPP_VERIFY_TOKEN", "mi-token")
    r = _publico().get(WEBHOOK, params=q)
    assert r.status_code == 200 and r.text == "123"
    assert _publico().get(WEBHOOK, params={**q, "hub.verify_token": "x"}).status_code == 403


def test_enlace_alterado_o_de_otro_archivo_es_404(escenario):
    s = escenario["sesionador"]
    _escribir(s, TEL_A, "opinión", "wamid.e", _pide("enviar_opinion_cumplimiento"))
    p = urlparse(_wa().enviados[-1]["url"])
    assert _publico().get(f"{p.path}?{p.query[:-1]}0").status_code == 404
    otro = p.path.replace("opinion.pdf", "constancia.pdf")
    assert _publico().get(f"{otro}?{p.query}").status_code == 404


# ── Contactos ──


def test_contactos_exigen_consentimiento_y_respetan_tenencia(escenario):
    a, b = escenario["a"], escenario["b"]
    url = "/api/v1/whatsapp/clientes/taller/contactos"
    assert a.post(url, json={"telefono": TEL_B, "consentimiento": False}).status_code == 422
    assert a.post(url, json={"telefono": "+15551234567", "consentimiento": True}
                  ).status_code == 422
    assert b.get(url).status_code == 404
    lista = a.get(url).json()["contactos"]
    assert {c["telefono"] for c in lista} == {TEL_A, TEL_AMBOS}
    ida = next(c["id"] for c in lista if c["telefono"] == TEL_A)
    assert b.delete(f"/api/v1/whatsapp/clientes/ferre/contactos/{ida}").status_code == 404
    assert a.delete(f"{url}/{ida}").status_code == 200
    # Dado de baja, el número ya no se atiende.
    _escribir(escenario["sesionador"], TEL_A, "opinión", "wamid.baja")
    assert "no está registrado" in _wa().enviados[-1]["texto"]
