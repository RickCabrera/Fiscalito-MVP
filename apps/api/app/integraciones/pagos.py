"""
Pagos de suscripción del despacho (P0-06). `FISCALITO_PAGOS` = falso | stripe | mercadopago.

Interfaz: `crear_cliente(email, nombre, referencia)` → id; `crear_suscripcion(cliente_id,
plan)` → `Suscripcion`; `cambiar_plan(suscripcion_id, plan)` → `Suscripcion` (P5-08);
`cancelar(suscripcion_id)`; `portal_url(cliente_id, regreso)` → URL;
`parsear_webhook(cuerpo, encabezados)` → `EventoPago` (verifica la firma; 400 si no cuadra).

EVENTOS NORMALIZADOS (P5-08)
----------------------------
Cada implementación traduce su evento a `EventoPago.clase`, lo único que lee el dominio
(`app/suscripciones/servicio.py`): `pago_exitoso`, `pago_fallido`, `suscripcion_actualizada`,
`suscripcion_cancelada`, o `""` (evento que no nos importa: se registra y se ignora).
`id_evento` es la llave de idempotencia (los proveedores reintentan el mismo evento).
"""

import hashlib
import hmac
import json
import os
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
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
    id_evento: str = ""
    clase: str = ""
    suscripcion_externa: str = ""
    # active | past_due | canceled | ... tal como lo dice el proveedor (si lo dice).
    estado_externo: str = ""
    monto: Decimal | None = None
    moneda: str = ""
    fin_periodo: datetime | None = None


CLASES = ("pago_exitoso", "pago_fallido", "suscripcion_actualizada", "suscripcion_cancelada")


class FirmaInvalida(FiscalAgentError):
    def __init__(self, servicio: str) -> None:
        super().__init__(f"La firma del webhook de {servicio} no es válida.", status_code=400)


def _encabezado(encabezados: Mapping[str, str], nombre: str) -> str:
    for k, v in encabezados.items():
        if k.lower() == nombre.lower():
            return v
    return ""


def _decimal(valor: Any, centavos: bool = False) -> Decimal | None:
    if valor is None or valor == "":
        return None
    try:
        d = Decimal(str(valor))
    except InvalidOperation:
        return None
    return (d / 100 if centavos else d).quantize(Decimal("0.01"))


def _epoch(valor: Any) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(valor), UTC) if valor else None
    except (TypeError, ValueError, OverflowError):
        return None


class Pagos(Protocol):
    def crear_cliente(self, email: str, nombre: str, referencia: str) -> str: ...
    def crear_suscripcion(self, cliente_id: str, plan: str) -> Suscripcion: ...
    def cambiar_plan(self, suscripcion_id: str, plan: str) -> Suscripcion: ...
    def cancelar(self, suscripcion_id: str) -> None: ...
    def portal_url(self, cliente_id: str, regreso: str) -> str: ...
    def parsear_webhook(self, cuerpo: bytes, encabezados: Mapping[str, str]) -> EventoPago: ...


SECRETO_FALSO = "secreto-del-webhook-falso"
ENCABEZADO_FIRMA_FALSA = "X-Fiscalito-Firma"


def _secreto_falso() -> str:
    return os.environ.get("FISCALITO_PAGOS_FALSO_SECRETO", "").strip() or SECRETO_FALSO


@dataclass
class PagosFalso:
    """
    Todo en memoria. El webhook falso es JSON `{id_evento, tipo, id, datos}` donde `tipo` ya
    es la clase normalizada e `id` la suscripción; `datos` puede traer `monto`, `moneda`,
    `fin_periodo` (ISO) y `estado`. Va FIRMADO como los reales: `X-Fiscalito-Firma` =
    HMAC-SHA256 hex del cuerpo con `FISCALITO_PAGOS_FALSO_SECRETO` (o el fijo de pruebas).
    """

    clientes: dict[str, dict[str, str]] = field(default_factory=dict)
    suscripciones: dict[str, dict[str, str]] = field(default_factory=dict)
    secreto: str = field(default_factory=_secreto_falso)

    def firmar(self, cuerpo: bytes) -> dict[str, str]:
        """Encabezados con la firma, para los tests y el simulador."""
        firma = hmac.new(self.secreto.encode(), cuerpo, hashlib.sha256).hexdigest()
        return {ENCABEZADO_FIRMA_FALSA: firma}

    def crear_cliente(self, email, nombre, referencia):
        cid = f"cli_falso_{len(self.clientes) + 1}"
        self.clientes[cid] = {"email": email, "nombre": nombre, "referencia": referencia}
        return cid

    def crear_suscripcion(self, cliente_id, plan):
        sid = f"sub_falso_{len(self.suscripciones) + 1}"
        self.suscripciones[sid] = {"cliente": cliente_id, "plan": plan, "estado": "active"}
        return Suscripcion(id=sid, estado="active")

    def cambiar_plan(self, suscripcion_id, plan):
        if suscripcion_id not in self.suscripciones:
            raise FiscalAgentError("No existe esa suscripción.", status_code=404)
        self.suscripciones[suscripcion_id]["plan"] = plan
        return Suscripcion(id=suscripcion_id, estado=self.suscripciones[suscripcion_id]["estado"])

    def cancelar(self, suscripcion_id):
        if suscripcion_id not in self.suscripciones:
            raise FiscalAgentError("No existe esa suscripción.", status_code=404)
        self.suscripciones[suscripcion_id]["estado"] = "canceled"

    def portal_url(self, cliente_id, regreso):
        return f"{regreso}?portal_falso={cliente_id}"

    def parsear_webhook(self, cuerpo, encabezados):
        esperada = self.firmar(cuerpo)[ENCABEZADO_FIRMA_FALSA]
        if not hmac.compare_digest(_encabezado(encabezados, ENCABEZADO_FIRMA_FALSA), esperada):
            raise FirmaInvalida("pagos (falso)")
        d = json.loads(cuerpo)
        datos = d.get("datos", {}) or {}
        fin = datos.get("fin_periodo")
        tipo = d["tipo"]
        return EventoPago(
            tipo=tipo, id_objeto=d.get("id", ""), datos=datos,
            id_evento=str(d.get("id_evento", "")), clase=tipo if tipo in CLASES else "",
            suscripcion_externa=d.get("id", ""), estado_externo=str(datos.get("estado", "")),
            monto=_decimal(datos.get("monto")), moneda=str(datos.get("moneda", "")).upper(),
            fin_periodo=datetime.fromisoformat(fin) if fin else None,
        )


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

    def cambiar_plan(self, suscripcion_id, plan):
        # Stripe cambia el Price del renglón existente (con prorrateo), no la suscripción.
        r = self._http.get(f"{self.URL}/subscriptions/{suscripcion_id}", auth=(self._key, ""))
        actual = revisar(r, "Stripe").json()
        renglon = actual["items"]["data"][0]["id"]
        d = self._post(f"/subscriptions/{suscripcion_id}", {
            "items[0][id]": renglon, "items[0][price]": plan,
            "proration_behavior": "create_prorations",
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
        return self._normalizar(d, objeto)

    @staticmethod
    def _normalizar(d: dict[str, Any], objeto: dict[str, Any]) -> EventoPago:
        tipo = d["type"]
        base: dict[str, Any] = {"tipo": tipo, "id_objeto": objeto.get("id", ""),
                                "datos": objeto, "id_evento": d.get("id", "")}
        if tipo in ("invoice.paid", "invoice.payment_succeeded", "invoice.payment_failed"):
            pagado = tipo != "invoice.payment_failed"
            lineas = (objeto.get("lines") or {}).get("data") or [{}]
            fin = _epoch((lineas[0].get("period") or {}).get("end")) or _epoch(
                objeto.get("period_end"))
            return EventoPago(
                **base, clase="pago_exitoso" if pagado else "pago_fallido",
                suscripcion_externa=objeto.get("subscription") or "",
                monto=_decimal(objeto.get("amount_paid" if pagado else "amount_due"), True),
                moneda=str(objeto.get("currency", "")).upper(), fin_periodo=fin)
        if tipo in ("customer.subscription.created", "customer.subscription.updated",
                    "customer.subscription.deleted"):
            return EventoPago(
                **base, clase="suscripcion_cancelada" if tipo.endswith("deleted")
                else "suscripcion_actualizada",
                suscripcion_externa=objeto.get("id", ""),
                estado_externo=objeto.get("status", ""),
                fin_periodo=_epoch(objeto.get("current_period_end")))
        return EventoPago(**base)


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
        # PENDIENTE: los avisos de Mercado Pago sólo traen el id y falta consultar
        # `/preapproval` para saber el estado; sin eso un despacho que pagó caería en solo
        # lectura al terminar la prueba. Hasta que esté, no se acepta el alta (revisor P5).
        raise FiscalAgentError(
            "Las suscripciones con Mercado Pago aún no están disponibles; usa Stripe.",
            status_code=503)

    def _crear_suscripcion_preapproval(self, cliente_id, plan):
        # `cliente_id` es el correo del pagador: así lo pide `preapproval`.
        r = self._http.post(f"{self.URL}/preapproval", headers=self._h, json={
            "preapproval_plan_id": plan, "payer_email": cliente_id,
        })
        d = revisar(r, "Mercado Pago").json()
        return Suscripcion(id=d["id"], estado=d.get("status", ""), url_pago=d.get("init_point", ""))

    def cambiar_plan(self, suscripcion_id, plan):
        # Un `preapproval` queda atado a su `preapproval_plan_id`: Mercado Pago no lo cambia.
        raise FiscalAgentError(
            "Mercado Pago no permite cambiar el plan de una suscripción: cancélala y "
            "suscríbete al plan nuevo.", status_code=409)

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
        # El aviso de Mercado Pago sólo trae el id: el estado real hay que consultarlo
        # (`GET /preapproval/{id}` o `/authorized_payments/{id}`). Hasta tener esa consulta
        # con respuestas grabadas, la clase queda vacía y el dominio sólo lo registra.
        # PENDIENTE (P5-08): normalizar los eventos de Mercado Pago.
        return EventoPago(tipo=d.get("type", d.get("action", "")), id_objeto=id_dato, datos=d,
                          id_evento=str(d.get("id", "")))


DESCRIPCION = "Cobro de la suscripción del despacho"
registro.registrar("pagos", "falso", PagosFalso, DESCRIPCION)
registro.registrar("pagos", "stripe", lambda: PagosStripe(
    env("FISCALITO_STRIPE_API_KEY"), env("FISCALITO_STRIPE_WEBHOOK_SECRET")), DESCRIPCION)
registro.registrar("pagos", "mercadopago", lambda: PagosMercadoPago(
    env("FISCALITO_MERCADOPAGO_ACCESS_TOKEN"), env("FISCALITO_MERCADOPAGO_WEBHOOK_SECRET")),
    DESCRIPCION)
