"""
P5-05 · Envío de documentos al cliente por correo y WhatsApp con los adaptadores FALSOS.

"Listo cuando": desde la ficha del cliente se envía cualquier documento por los dos canales.
Se prueba con una factura (P5-04), una opinión de cumplimiento (P1-05) y un acuse subido al
expediente: contactos con consentimiento, envío en segundo plano, enlace firmado para WhatsApp,
reintentos sin duplicar, bitácora y multi-tenant.
"""

from __future__ import annotations

import io
from datetime import timedelta
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas
from sqlalchemy import select

from app.db.base import ahora
from app.integraciones import registro
from app.main import app
from app.modelos.auditoria import EventoAuditoria
from app.trabajos.cola import procesar_siguiente
from tests.plan_p.test_facturacion import URL, B, _factura, preparar_entorno

BASE = "/api/v1/clientes/taller"


@pytest.fixture
def entorno(api, sesionador, tmp_path, monkeypatch):
    yield from preparar_entorno(api, sesionador, tmp_path, monkeypatch)


def _pdf(texto: str) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(40, 700, texto)
    c.save()
    return buf.getvalue()


def _preparar(http):
    f = http.post(URL, json=_factura()).json()["factura"]
    r = http.post(f"{BASE}/expediente", data={"tipo": "acuse", "descripcion": "Acuse ISR sep",
                                              "periodo": "2026-09"},
                  files={"archivo": ("acuse.pdf", _pdf("ACUSE DE RECIBO"), "application/pdf")})
    assert r.status_code == 200, r.text
    r = http.post(f"{BASE}/opinion/pdf".replace("/clientes/", "/sat/clientes/"),
                  data={"tipo": "opinion", "resultado": "positiva"},
                  files={"archivo": ("opinion.pdf", _pdf("OPINION POSITIVA"), "application/pdf")})
    assert r.status_code == 200, r.text
    contactos = []
    for cuerpo in ({"nombre": "Ana Ruiz", "correo": "ana@taller.mx",
                    "telefono": "+52 1 55 1234 5678", "consentimiento_whatsapp": True},
                   {"nombre": "Luis Paz", "correo": "luis@taller.mx",
                    "telefono": "5215598765432"}):
        r = http.post(f"{BASE}/contactos", json=cuerpo)
        assert r.status_code == 200, r.text
        contactos.append(r.json()["contacto"])
    return f, contactos


def _docs(http):
    return {d["tipo"]: d for d in http.get(f"{BASE}/documentos-enviables").json()["documentos"]}


def test_envia_factura_opinion_y_acuse_por_correo_y_whatsapp(entorno, sesionador):
    http = entorno
    f, (ana, luis) = _preparar(http)
    assert ana["consentimiento_whatsapp"] and ana["consentimiento_en"] and ana["telefono"] == \
        "5215512345678"
    docs = _docs(http)
    # la factura ya está en la bóveda del receptor: no se repite como "cfdi"
    assert set(docs) == {"factura", "acuse", "opinion"}
    elegidos = [{"tipo": t, "ref": docs[t]["ref"]} for t in ("factura", "acuse", "opinion")]
    r = http.post(f"{BASE}/envios", json={"documentos": elegidos,
                                          "canales": ["correo", "whatsapp"],
                                          "contactos": [ana["id"], luis["id"]],
                                          "mensaje": "Saludos"})
    assert r.status_code == 200, r.text
    j = r.json()
    # Luis no dio consentimiento de WhatsApp: se omite ese canal para él, con motivo.
    assert [(o["contacto"], o["canal"]) for o in j["omitidos"]] == [("Luis Paz", "whatsapp")]
    n = len(elegidos)
    assert j["resumen"] == {"pendiente": 3 * n} and j["trabajo"]["estado"] == "pendiente"
    assert procesar_siguiente(sesionador).estado == "hecho"
    correo, wa = registro.obtener("correo"), registro.obtener("whatsapp")
    assert sorted(m.destinatarios[0] for m in correo.enviados) == sorted(
        ["ana@taller.mx"] * n + ["luis@taller.mx"] * n)
    factura_mail = next(m for m in correo.enviados if f["uuid"] in m.asunto)
    nombres = {a.nombre.rsplit(".", 1)[-1] for a in factura_mail.adjuntos}
    assert nombres == {"pdf", "xml"} and "Saludos" in factura_mail.html
    assert len(wa.enviados) == n and {m["telefono"] for m in wa.enviados} == {"5215512345678"}
    m = next(m for m in wa.enviados if "Factura" in m["parametros"][1])
    assert m["plantilla"] == "documento_cliente" and m["parametros"][0] == "Ana Ruiz"
    # el enlace firmado baja el PDF sin sesión; alterado o del otro ámbito → 404
    url = urlparse(m["documento"].url)
    q = {k: v[0] for k, v in parse_qs(url.query).items()}
    publico = TestClient(app)
    r = publico.get(url.path, params=q)
    assert r.status_code == 200 and r.content.startswith(b"%PDF")
    assert publico.get(url.path, params={**q, "firma": "0" * 64}).status_code == 404
    assert publico.get(url.path.replace("/documentos/", "/recibos/").replace(
        "documento.pdf", "recibo.pdf"), params=q).status_code == 404
    estado = http.get(f"{BASE}/envios").json()
    assert estado["resumen"] == {"enviado": 3 * n}
    with sesionador() as db:
        acciones = set(db.scalars(select(EventoAuditoria.accion)))
    assert {"documentos.enviar", "documentos.enviados", "documentos.contacto"} <= acciones


def test_fallo_se_reintenta_sin_duplicar_y_reenvio(entorno, sesionador, monkeypatch):
    http = entorno
    _, (ana, _luis) = _preparar(http)
    docs = _docs(http)
    correo = registro.obtener("correo")
    original = correo.enviar
    caido = {"si": True}

    def enviar(destinatarios, asunto, html, adjuntos=()):
        if caido["si"] and "Acuse" in asunto:
            raise RuntimeError("SMTP caído")
        return original(destinatarios, asunto, html, adjuntos)

    monkeypatch.setattr(correo, "enviar", enviar)
    http.post(f"{BASE}/envios", json={
        "documentos": [{"tipo": "factura", "ref": docs["factura"]["ref"]},
                       {"tipo": "acuse", "ref": docs["acuse"]["ref"]}],
        "canales": ["correo"], "contactos": [ana["id"]]})
    procesar_siguiente(sesionador)
    estado = {e["tipo_documento"]: e for e in http.get(f"{BASE}/envios").json()["envios"]}
    assert estado["acuse"]["estado"] == "fallido" and "SMTP" in estado["acuse"]["error"]
    assert len(correo.enviados) == 1
    caido["si"] = False
    procesar_siguiente(sesionador, ahora=ahora() + timedelta(hours=2))
    estado = {e["tipo_documento"]: e for e in http.get(f"{BASE}/envios").json()["envios"]}
    assert estado["acuse"]["estado"] == "enviado" and len(correo.enviados) == 2
    # reenvío explícito de uno
    r = http.post(f"{BASE}/envios/{estado['factura']['id']}/reenviar")
    assert r.status_code == 200
    procesar_siguiente(sesionador)
    assert len(correo.enviados) == 3


def test_validaciones_y_multi_tenant(entorno, api):
    http = entorno
    f, (ana, _) = _preparar(http)
    assert http.post(f"{BASE}/contactos", json={"nombre": "Sin datos"}).status_code == 422
    assert http.post(f"{BASE}/contactos", json={
        "nombre": "X", "correo": "x@y.mx", "consentimiento_whatsapp": True}).status_code == 422
    assert http.post(f"{BASE}/expediente", data={"tipo": "acuse"}, files={
        "archivo": ("a.exe", b"MZ....", "application/octet-stream")}).status_code == 422
    # un documento de otro cliente no se envía desde éste
    assert http.post("/api/v1/clientes/despacho/envios", json={
        "documentos": [{"tipo": "acuse", "ref": _docs(http)["acuse"]["ref"]}],
        "canales": ["correo"], "contactos": [ana["id"]]}).status_code == 404
    # la factura emitida por el despacho sí aparece en la ficha del receptor y se descarga
    r = http.get(f"{BASE}/documentos/factura/{f['id']}/0")
    assert r.status_code == 200 and r.content.startswith(b"%PDF")
    b = api(B)
    assert b.get(f"{BASE}/contactos").status_code == 404
    assert b.get(f"{BASE}/documentos-enviables").status_code == 404
    assert b.post(f"{BASE}/envios", json={
        "documentos": [{"tipo": "factura", "ref": str(f["id"])}], "canales": ["correo"],
        "contactos": [ana["id"]]}).status_code == 404
    assert b.put(f"{BASE}/contactos/{ana['id']}", json={"nombre": "x"}).status_code == 404
