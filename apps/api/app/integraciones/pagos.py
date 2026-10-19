"""
Pagos de suscripción del despacho (P0-06). `FISCALITO_PAGOS` = falso | stripe | mercadopago.

Interfaz: `crear_cliente(email, nombre, referencia)` → id; `crear_suscripcion(cliente_id,
plan)` → `Suscripcion`; `cancelar(suscripcion_id)`; `portal_url(cliente_id, regreso)` → URL;
`parsear_webhook(cuerpo, encabezados)` → `EventoPago` (verifica la firma; 400 si no cuadra).
"""

import hashlib
import hmac
import json
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

from app.exceptions import FiscalAgentError
from app.integraciones import registro
from app.integraciones.comun import cliente_http, env, revisar


@dataclass(frozen=True)
class Suscripcion:
    id: str
    estado: str
    url_pago: str = ""


@dataclass(frozen=True)
class EventoPago:
    tipo: str
    id_objeto: str
    datos: dict[str, Any]


class FirmaInvalida(FiscalAgentError):
    def __init__(self, servicio: str) -> None:
        super().__init__(f"La firma del webhook de {servicio} no es válida.", status_code=400)


def _encabezado(encabezados: Mapping[str, str], nombre: str) -> str:
    for k, v in encabezados.items():
        if k.lower() == nombre.lower():
            return v
    return ""


class Pagos(Protocol):
    def crear_cliente(self, email: str, nombre: str, referencia: str) -> str: ...
    def crear_suscripcion(self, cliente_id: str, plan: str) -> Suscripcion: ...
    def cancelar(self, suscripcion_id: str) -> None: ...
    def portal_url(self, cliente_id: str, regreso: str) -> str: ...
    def parsear_webhook(self, cuerpo: bytes, encabezados: Mapping[str, str]) -> EventoPago: ...


@dataclass
class PagosFalso:
    """Todo en memoria. El webhook falso es JSON `{tipo, id, datos}` sin firma."""

    clientes: dict[str, dict[str, str]] = field(default_factory=dict)
    suscripciones: dict[str, dict[str, str]] = field(default_factory=dict)

    def crear_cliente(self, email, nombre, referencia):
        cid = f"cli_falso_{len(self.clientes) + 1}"
        self.clientes[cid] = {"email": email, "nombre": nombre, "referencia": referencia}
        return cid

    def crear_suscripcion(self, cliente_id, plan):
        sid = f"sub_falso_{len(self.suscripciones) + 1}"
        self.suscripciones[sid] = {"cliente": cliente_id, "plan": plan, "estado": "active"}
        return Suscripcion(id=sid, estado="active")

    def cancelar(self, suscripcion_id):
        if suscripcion_id not in self.suscripciones:
            raise FiscalAgentError("No existe esa suscripción.", status_code=404)
        self.suscripciones[suscripcion_id]["estado"] = "canceled"

    def portal_url(self, cliente_id, regreso):
        return f"{regreso}?portal_falso={cliente_id}"

    def parsear_webhook(self, cuerpo, encabezados):
        d = json.loads(cuerpo)
        return EventoPago(tipo=d["tipo"], id_objeto=d.get("id", ""), datos=d.get("datos", {}))


class PagosStripe:
    """Stripe por su API REST (form-encoded) y webhooks firmados (`Stripe-Signature`)."""

    URL = "https://api.stripe.com/v1"
    TOLERANCIA_S = 300

    def __init__(self, api_key: str, webhook_secret: str, http: httpx.Client | None = None):
        self._key, self._secreto = api_key, webhook_secret
        self._http = cliente_http(http)

    def _post(self, ruta: str, datos: dict[str, str] | None = None) -> dict:
        r = self._http.post(f"{self.URL}{ruta}", data=datos or {}, auth=(self._key, ""))
        return revisar(r, "Stripe").json()

    def crear_cliente(self, email, nombre, referencia):
        return self._post("/customers", {
            "email": email, "name": nombre, "metadata[referencia]": referencia,
        })["id"]

    def crear_suscripcion(self, cliente_id, plan):
        d = self._post("/subscriptions", {
            "customer": cliente_id, "items[0][price]": plan,
            "payment_behavior": "default_incomplete",
        })
        return Suscripcion(id=d["id"], estado=d["status"])

    def cancelar(self, suscripcion_id):
        r = self._http.delete(f"{self.URL}/subscriptions/{suscripcion_id}", auth=(self._key, ""))
        revisar(r, "Stripe")

    def portal_url(self, cliente_id, regreso):
        return self._post("/billing_portal/sessions", {
            "customer": cliente_id, "return_url": regreso,
        })["url"]

    def parsear_webhook(self, cuerpo, encabezados, ahora: float | None = None):
        partes = dict(
            p.split("=", 1) for p in _encabezado(encabezados, "Stripe-Signature").split(",")
            if "=" in p
        )
        t, v1 = partes.get("t", ""), partes.get("v1", "")
        esperada = hmac.new(
            self._secreto.encode(), f"{t}.".encode() + cuerpo, hashlib.sha256
        ).hexdigest()
        momento = time.time() if ahora is None else ahora
        if not (t.isdigit() and v1 and hmac.compare_digest(v1, esperada)
                and abs(momento - int(t)) <= self.TOLERANCIA_S):
            raise FirmaInvalida("Stripe")
        d = json.loads(cuerpo)
        objeto = d.get("data", {}).get("object", {})
        return EventoPago(tipo=d["type"], id_objeto=objeto.get("id", ""), datos=objeto)


class PagosMercadoPago:
    """Mercado Pago: suscripciones con `preapproval` y webhooks con `x-signature`."""

    URL = "https://api.mercadopago.com"

    def __init__(self, access_token: str, webhook_secret: str, http: httpx.Client | None = None):
        self._token, self._secreto = access_token, webhook_secret
        self._http = cliente_http(http)
        self._h = {"Authorization": f"Bearer {access_token}"}

    def crear_cliente(self, email, nombre, referencia):
        r = self._http.post(f"{self.URL}/v1/customers", headers=self._h, json={
            "email": email, "first_name": nombre, "description": referencia,
        })
        return str(revisar(r, "Mercado Pago").json()["id"])

    def crear_suscripcion(self, cliente_id, plan):
        # `cliente_id` es el correo del pagador: así lo pide `preapproval`.
        r = self._http.post(f"{self.URL}/preapproval", headers=self._h, json={
            "preapproval_plan_id": plan, "payer_email": cliente_id,
        })
        d = revisar(r, "Mercado Pago").json()
        return Suscripcion(id=d["id"], estado=d.get("status", ""), url_pago=d.get("init_point", ""))

    def cancelar(self, suscripcion_id):
        r = self._http.put(f"{self.URL}/preapproval/{suscripcion_id}", headers=self._h,
                           json={"status": "cancelled"})
        revisar(r, "Mercado Pago")

    def portal_url(self, cliente_id, regreso):
        # Mercado Pago no tiene portal de cliente: el pagador administra en su cuenta.
        return "https://www.mercadopago.com.mx/subscriptions"

    def parsear_webhook(self, cuerpo, encabezados):
        d = json.loads(cuerpo)
        id_dato = str(d.get("data", {}).get("id", ""))
        partes = dict(
            p.strip().split("=", 1) for p in _encabezado(encabezados, "x-signature").split(",")
            if "=" in p
        )
        manifiesto = (f"id:{id_dato.lower()};request-id:"
                      f"{_encabezado(encabezados, 'x-request-id')};ts:{partes.get('ts', '')};")
        esperada = hmac.new(self._secreto.encode(), manifiesto.encode(), hashlib.sha256).hexdigest()
        if not partes.get("v1") or not hmac.compare_digest(partes["v1"], esperada):
            raise FirmaInvalida("Mercado Pago")
        return EventoPago(tipo=d.get("type", d.get("action", "")), id_objeto=id_dato, datos=d)


DESCRIPCION = "Cobro de la suscripción del despacho"
registro.registrar("pagos", "falso", PagosFalso, DESCRIPCION)
registro.registrar("pagos", "stripe", lambda: PagosStripe(
    env("FISCALITO_STRIPE_API_KEY"), env("FISCALITO_STRIPE_WEBHOOK_SECRET")), DESCRIPCION)
registro.registrar("pagos", "mercadopago", lambda: PagosMercadoPago(
    env("FISCALITO_MERCADOPAGO_ACCESS_TOKEN"), env("FISCALITO_MERCADOPAGO_WEBHOOK_SECRET")),
    DESCRIPCION)
