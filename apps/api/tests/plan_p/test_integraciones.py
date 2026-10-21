"""
P0-06: adaptadores genéricos (correo, WhatsApp, pagos, monitoreo, LLM).

Cada real se prueba contra `httpx.MockTransport` con respuestas grabadas en
`tests/fixtures/<servicio>/`. Ningún test toca la red: el transporte falla si la petición
no es la esperada.
"""

import base64
import hashlib
import hmac
import json
import time
from pathlib import Path
from urllib.parse import parse_qsl, urlencode

import httpx
import pytest

from app.exceptions import FiscalAgentError
from app.integraciones import correo, llm, monitoreo, pagos, registro, whatsapp

FIX = Path(__file__).resolve().parents[1] / "fixtures"


def grabada(ruta: str) -> dict:
    return json.loads((FIX / ruta).read_text(encoding="utf-8"))


class Grabadora:
    """MockTransport que guarda cada petición y responde lo que le toque por URL."""

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


# ── Registro: la variable elige la implementación ──


@pytest.mark.parametrize("servicio,reales", [
    ("correo", {"smtp", "resend", "sendgrid"}),
    ("whatsapp", {"meta", "twilio"}),
    ("pagos", {"stripe", "mercadopago"}),
    ("monitoreo", {"log", "sentry"}),
    ("llm", {"openai", "anthropic"}),
])
def test_cada_servicio_tiene_falso_y_reales(servicio, reales):
    estado = {s["servicio"]: s for s in registro.verificar_configuracion()}[servicio]
    assert {"falso"} | reales <= set(estado["disponibles"])


def test_la_variable_cambia_de_implementacion(monkeypatch):
    registro.limpiar_cache()
    monkeypatch.delenv("FISCALITO_CORREO", raising=False)
    assert isinstance(registro.obtener("correo"), correo.CorreoFalso)
    monkeypatch.setenv("FISCALITO_CORREO", "resend")
    monkeypatch.setenv("FISCALITO_RESEND_API_KEY", "re_prueba")
    monkeypatch.setenv("FISCALITO_CORREO_REMITENTE", "avisos@despacho.mx")
    assert isinstance(registro.obtener("correo"), correo.CorreoResend)
    monkeypatch.setenv("FISCALITO_MONITOREO", "log")
    assert isinstance(registro.obtener("monitoreo"), monitoreo.MonitoreoLog)
    registro.limpiar_cache()


def test_real_sin_credenciales_dice_que_variable_falta(monkeypatch):
    registro.limpiar_cache()
    monkeypatch.setenv("FISCALITO_PAGOS", "stripe")
    monkeypatch.delenv("FISCALITO_STRIPE_API_KEY", raising=False)
    with pytest.raises(FiscalAgentError) as e:
        registro.obtener("pagos")
    assert e.value.status_code == 503 and "FISCALITO_STRIPE_API_KEY" in e.value.message
    registro.limpiar_cache()


# ── Correo ──


def test_correo_falso_guarda():
    c = correo.CorreoFalso()
    c.enviar(["a@b.mx"], "Hola", "<p>x</p>", [correo.Adjunto("r.pdf", b"%PDF", "application/pdf")])
    assert c.enviados[0].asunto == "Hola" and c.enviados[0].adjuntos[0].nombre == "r.pdf"


def test_correo_resend():
    g = Grabadora({"api.resend.com": httpx.Response(200, json=grabada("correo/resend_ok.json"))})
    c = correo.CorreoResend("re_123", "avisos@despacho.mx", http=g.cliente())
    mid = c.enviar(["a@b.mx"], "Asunto", "<b>hola</b>", [correo.Adjunto("x.xml", b"<x/>")])
    assert mid == "49a3999c-0ce1-4ea6-ab68-afcd6dc2e794"
    p = g.peticiones[0]
    assert p.headers["Authorization"] == "Bearer re_123"
    cuerpo = json.loads(p.content)
    assert cuerpo["to"] == ["a@b.mx"] and cuerpo["attachments"][0]["content"] == "PHgvPg=="


def test_correo_sendgrid_y_error():
    g = Grabadora({"sendgrid": httpx.Response(202, headers={"X-Message-Id": "sg-1"})})
    c = correo.CorreoSendGrid("SG.x", "avisos@despacho.mx", http=g.cliente())
    assert c.enviar(["a@b.mx"], "A", "<p/>") == "sg-1"
    assert json.loads(g.peticiones[0].content)["personalizations"][0]["to"][0]["email"] == "a@b.mx"
    malo = Grabadora({"sendgrid": httpx.Response(401, json={"errors": [{"message": "bad key"}]})})
    with pytest.raises(FiscalAgentError) as e:
        correo.CorreoSendGrid("SG.x", "a@b.mx", http=malo.cliente()).enviar(["a@b.mx"], "A", "x")
    assert e.value.status_code == 502


def test_correo_smtp_con_servidor_falso():
    enviados = []

    class SMTPFalso:
        def __init__(self, host, puerto, timeout):
            self.host = host

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def starttls(self):
            enviados.append("tls")

        def login(self, u, p):
            enviados.append(("login", u))

        def send_message(self, msg):
            enviados.append(msg)

    c = correo.CorreoSMTP("smtp.x", 587, "u", "p", "avisos@despacho.mx", fabrica_smtp=SMTPFalso)
    adjunto = correo.Adjunto("r.pdf", b"%PDF", "application/pdf")
    c.enviar(["a@b.mx"], "Recibo", "<p>hola</p>", [adjunto])
    msg = enviados[-1]
    assert enviados[0] == "tls" and msg["Subject"] == "Recibo"
    assert [p.get_filename() for p in msg.iter_attachments()] == ["r.pdf"]


# ── WhatsApp ──


def test_whatsapp_falso_y_firma():
    w = whatsapp.WhatsAppFalso(secreto="s")
    w.enviar_plantilla("521", "recordatorio", parametros=["Taller"])
    assert w.enviados[0]["parametros"] == ["Taller"]
    cuerpo = (FIX / "whatsapp/meta_webhook.json").read_bytes()
    firma = "sha256=" + hmac.new(b"s", cuerpo, hashlib.sha256).hexdigest()
    assert w.verificar_firma_webhook(cuerpo, {"X-Hub-Signature-256": firma})
    assert not w.verificar_firma_webhook(cuerpo, {"X-Hub-Signature-256": "sha256=00"})


def test_whatsapp_meta():
    g = Grabadora({"graph.facebook.com": httpx.Response(
        200, json=grabada("whatsapp/meta_enviado.json"))})
    w = whatsapp.WhatsAppMeta("tok", "106540352242922", "secreto", http=g.cliente())
    assert w.enviar_texto("5215512345678", "hola").startswith("wamid.")
    w.enviar_documento("5215512345678", "https://x/r.pdf", "r.pdf", "Tu recibo")
    w.enviar_plantilla("5215512345678", "aviso_vencimiento", parametros=["Taller", "17"])
    cuerpos = [json.loads(p.content) for p in g.peticiones]
    assert g.peticiones[0].url.path == "/v20.0/106540352242922/messages"
    assert cuerpos[0]["text"]["body"] == "hola"
    assert cuerpos[1]["document"] == {"link": "https://x/r.pdf", "filename": "r.pdf",
                                      "caption": "Tu recibo"}
    assert cuerpos[2]["template"]["components"][0]["parameters"][1]["text"] == "17"

    cuerpo = (FIX / "whatsapp/meta_webhook.json").read_bytes()
    firma = "sha256=" + hmac.new(b"secreto", cuerpo, hashlib.sha256).hexdigest()
    assert w.verificar_firma_webhook(cuerpo, {"x-hub-signature-256": firma})
    [m] = w.parsear_webhook(cuerpo)
    assert m.telefono == "5215512345678" and "declaración" in m.texto


def test_whatsapp_twilio():
    g = Grabadora({"api.twilio.com": httpx.Response(
        201, json=grabada("whatsapp/twilio_enviado.json"))})
    w = whatsapp.WhatsAppTwilio("AC1", "token", "+14155238886", http=g.cliente())
    assert w.enviar_texto("+5215512345678", "hola").startswith("SM")
    w.enviar_plantilla("+5215512345678", "HXabc", parametros=["Taller"])
    p = g.peticiones[0]
    datos = dict(parse_qsl(p.content.decode()))
    assert datos["To"] == "whatsapp:+5215512345678" and datos["From"] == "whatsapp:+14155238886"
    assert p.headers["Authorization"].startswith("Basic ")
    assert json.loads(dict(parse_qsl(g.peticiones[1].content.decode()))["ContentVariables"]) == {
        "1": "Taller"}

    url = "https://api.fiscalito.mx/api/v1/whatsapp/webhook"
    cuerpo = urlencode({"MessageSid": "SMx", "From": "whatsapp:+5215512345678",
                        "Body": "hola", "NumMedia": "0"}).encode()
    base = url + "".join(k + v for k, v in sorted(parse_qsl(cuerpo.decode())))
    firma = base64.b64encode(hmac.new(b"token", base.encode(), hashlib.sha1).digest()).decode()
    assert w.verificar_firma_webhook(cuerpo, {"X-Twilio-Signature": firma}, url)
    assert not w.verificar_firma_webhook(cuerpo, {"X-Twilio-Signature": firma}, url + "x")
    [m] = w.parsear_webhook(cuerpo)
    assert m.telefono == "+5215512345678" and m.texto == "hola"


# ── Pagos ──


def test_pagos_falso():
    p = pagos.PagosFalso()
    cid = p.crear_cliente("a@b.mx", "Despacho", "uid-a")
    s = p.crear_suscripcion(cid, "contador")
    p.cancelar(s.id)
    assert p.suscripciones[s.id]["estado"] == "canceled"
    ev = p.parsear_webhook(b'{"tipo": "pago", "id": "x"}', {})
    assert ev.tipo == "pago"


def test_pagos_stripe():
    g = Grabadora({
        "/customers": httpx.Response(200, json=grabada("pagos/stripe_customer.json")),
        "/subscriptions/sub_": httpx.Response(
            200, json={"id": "sub_PRUEBA456", "status": "canceled"}),
        "/subscriptions": httpx.Response(200, json=grabada("pagos/stripe_subscription.json")),
        "/billing_portal": httpx.Response(200, json=grabada("pagos/stripe_portal.json")),
    })
    s = pagos.PagosStripe("sk_test_x", "whsec_x", http=g.cliente())
    assert s.crear_cliente("a@b.mx", "Despacho", "uid-a") == "cus_PRUEBA123"
    assert s.crear_suscripcion("cus_PRUEBA123", "price_1").estado == "incomplete"
    assert s.portal_url("cus_PRUEBA123", "https://app").startswith("https://billing.stripe.com")
    s.cancelar("sub_PRUEBA456")
    assert dict(parse_qsl(g.peticiones[0].content.decode()))["metadata[referencia]"] == "uid-a"
    assert g.peticiones[3].method == "DELETE"

    cuerpo = (FIX / "pagos/stripe_evento.json").read_bytes()
    t = str(int(time.time()))
    v1 = hmac.new(b"whsec_x", f"{t}.".encode() + cuerpo, hashlib.sha256).hexdigest()
    ev = s.parsear_webhook(cuerpo, {"Stripe-Signature": f"t={t},v1={v1}"})
    assert ev.tipo == "customer.subscription.updated" and ev.id_objeto == "sub_PRUEBA456"
    with pytest.raises(FiscalAgentError):
        s.parsear_webhook(cuerpo, {"Stripe-Signature": f"t={t},v1=00"})
    with pytest.raises(FiscalAgentError):  # firma vieja: ataque de repetición
        s.parsear_webhook(cuerpo, {"Stripe-Signature": f"t={t},v1={v1}"}, ahora=int(t) + 3600)


def test_pagos_mercadopago():
    g = Grabadora({
        "/v1/customers": httpx.Response(201, json={"id": "123-abc"}),
        "/preapproval/": httpx.Response(200, json={"id": "x", "status": "cancelled"}),
        "/preapproval": httpx.Response(201, json=grabada("pagos/mercadopago_preapproval.json")),
    })
    m = pagos.PagosMercadoPago("APP_USR-x", "secreto", http=g.cliente())
    assert m.crear_cliente("a@b.mx", "Despacho", "uid-a") == "123-abc"
    s = m.crear_suscripcion("a@b.mx", "plan-1")
    assert s.url_pago.startswith("https://www.mercadopago.com.mx")
    m.cancelar(s.id)
    assert g.peticiones[2].method == "PUT"

    cuerpo = json.dumps({"type": "subscription_preapproval", "data": {"id": "ABC"}}).encode()
    manifiesto = "id:abc;request-id:req-1;ts:1700000000;"
    v1 = hmac.new(b"secreto", manifiesto.encode(), hashlib.sha256).hexdigest()
    enc = {"x-signature": f"ts=1700000000,v1={v1}", "x-request-id": "req-1"}
    assert m.parsear_webhook(cuerpo, enc).id_objeto == "ABC"
    with pytest.raises(FiscalAgentError):
        m.parsear_webhook(cuerpo, {**enc, "x-request-id": "otro"})


# ── Monitoreo ──


def test_monitoreo_falso_y_log(caplog):
    f = monitoreo.MonitoreoFalso()
    f.capturar_error(ValueError("x"), {"cliente": "taller"})
    assert f.eventos[0]["contexto"] == {"cliente": "taller"}
    with caplog.at_level("WARNING", logger="fiscalito.monitoreo"):
        monitoreo.MonitoreoLog().capturar_mensaje("cuidado", "warning")
    assert "cuidado" in caplog.text


def test_monitoreo_sentry_con_sdk_inyectado():
    llamadas = []

    class Scope:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def set_extra(self, k, v):
            llamadas.append(("extra", k, v))

    class SDK:
        def init(self, **kw):
            llamadas.append(("init", kw["dsn"], kw["send_default_pii"]))

        def new_scope(self):
            return Scope()

        def capture_exception(self, e):
            llamadas.append(("exc", str(e)))

        def capture_message(self, m, level):
            llamadas.append(("msg", m, level))

    s = monitoreo.MonitoreoSentry("https://k@o.ingest.sentry.io/1", "produccion", sdk=SDK())
    s.capturar_error(RuntimeError("boom"), {"cliente": "taller"})
    s.capturar_mensaje("hola", "warning")
    assert llamadas[0] == ("init", "https://k@o.ingest.sentry.io/1", False)
    assert ("exc", "boom") in llamadas and ("msg", "hola", "warning") in llamadas


def test_monitoreo_sentry_sin_paquete_explica(monkeypatch):
    import builtins

    original = builtins.__import__

    def sin_sentry(nombre, *a, **kw):
        if nombre == "sentry_sdk":
            raise ImportError("no instalado")
        return original(nombre, *a, **kw)

    monkeypatch.setattr(builtins, "__import__", sin_sentry)
    with pytest.raises(FiscalAgentError, match="pip install sentry-sdk"):
        monitoreo.MonitoreoSentry("dsn", "produccion")


# ── LLM ──


def test_llm_falso_determinista():
    f = llm.LLMFalso()
    assert f.completar([{"role": "user", "content": "hola"}]).texto == "[falso] hola"
    r = f.completar([{"role": "user", "content": "x"}],
                    [{"nombre": "buscar_cliente", "parametros": {}}])
    assert r.llamadas[0].nombre == "buscar_cliente"


def test_llm_openai_con_respuesta_grabada():
    g = Grabadora({"api.openai.com": httpx.Response(
        200, json=grabada("llm/openai_tool_call.json"))})
    o = llm.LLMOpenAI("sk-x", "gpt-4o-mini", http=g.cliente())
    r = o.completar(
        [{"role": "system", "content": "Eres..."}, {"role": "user", "content": "busca"}],
        [{"nombre": "buscar_cliente", "descripcion": "d",
          "parametros": {"type": "object", "properties": {"rfc": {"type": "string"}}}}],
    )
    assert r.llamadas[0].argumentos == {"rfc": "XAXX010101AB1"} and r.tokens_entrada == 50
    enviado = json.loads(g.peticiones[0].content)
    assert enviado["tools"][0]["function"]["name"] == "buscar_cliente"


def test_llm_anthropic_con_respuesta_grabada():
    g = Grabadora({"api.anthropic.com": httpx.Response(
        200, json=grabada("llm/anthropic_texto.json"))})
    a = llm.LLMAnthropic("sk-ant-x", "claude-haiku-4-5-20251001", http=g.cliente())
    r = a.completar(
        [{"role": "system", "content": "Eres..."}, {"role": "user", "content": "hola"}],
        [{"nombre": "buscar_cliente", "parametros": {"type": "object", "properties": {}}}],
    )
    assert r.texto == "Tu declaración ya quedó." and r.llamadas[0].nombre == "buscar_cliente"
    enviado = json.loads(g.peticiones[0].content)
    assert enviado["system"] == "Eres..." and enviado["messages"] == [
        {"role": "user", "content": "hola"}]
    assert enviado["tools"][0]["input_schema"] == {"type": "object", "properties": {}}


def test_llm_real_sin_llave_503(monkeypatch):
    from app.config import settings

    registro.limpiar_cache()
    monkeypatch.setenv("FISCALITO_LLM", "anthropic")
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "")
    with pytest.raises(FiscalAgentError) as e:
        registro.obtener("llm")
    assert e.value.status_code == 503
    registro.limpiar_cache()
