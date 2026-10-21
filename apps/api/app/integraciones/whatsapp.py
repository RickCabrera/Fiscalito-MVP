"""
WhatsApp (P0-06). `FISCALITO_WHATSAPP` = falso | meta | twilio.

Interfaz: `enviar_texto`, `enviar_documento`, `enviar_plantilla` (devuelven el id del
mensaje), `verificar_firma_webhook(cuerpo, encabezados, url)` y `parsear_webhook(cuerpo,
encabezados)` → lista de `MensajeEntrante`.
"""

import base64
import hashlib
import hmac
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol
from urllib.parse import parse_qsl

import httpx

from app.integraciones import registro
from app.integraciones.comun import cliente_http, env, revisar


@dataclass(frozen=True)
class DocumentoPlantilla:
    """Documento del encabezado de una plantilla aprobada (P4-13): URL pública y nombre."""

    url: str
    nombre: str


@dataclass(frozen=True)
class MensajeEntrante:
    telefono: str
    texto: str
    id_mensaje: str
    tipo: str = "texto"


def _encabezado(encabezados: Mapping[str, str], nombre: str) -> str:
    for k, v in encabezados.items():
        if k.lower() == nombre.lower():
            return v
    return ""


class WhatsApp(Protocol):
    def enviar_texto(self, telefono: str, texto: str) -> str: ...
    def enviar_documento(
        self, telefono: str, url_documento: str, nombre: str, leyenda: str = ""
    ) -> str: ...
    def enviar_plantilla(
        self, telefono: str, plantilla: str, idioma: str = "es_MX",
        parametros: Sequence[str] = (), documento: DocumentoPlantilla | None = None,
    ) -> str: ...
    def verificar_firma_webhook(
        self, cuerpo: bytes, encabezados: Mapping[str, str], url: str = ""
    ) -> bool: ...
    def parsear_webhook(
        self, cuerpo: bytes, encabezados: Mapping[str, str] | None = None
    ) -> list[MensajeEntrante]: ...


@dataclass
class WhatsAppFalso:
    """Guarda lo enviado en `enviados`. Firma: HMAC-SHA256 con `secreto` (como Meta)."""

    secreto: str = "secreto-falso"
    enviados: list[dict[str, Any]] = field(default_factory=list)

    def _guardar(self, **datos: Any) -> str:
        self.enviados.append(datos)
        return f"wa-falso-{len(self.enviados)}"

    def enviar_texto(self, telefono, texto):
        return self._guardar(tipo="texto", telefono=telefono, texto=texto)

    def enviar_documento(self, telefono, url_documento, nombre, leyenda=""):
        return self._guardar(tipo="documento", telefono=telefono, url=url_documento,
                             nombre=nombre, leyenda=leyenda)

    def enviar_plantilla(self, telefono, plantilla, idioma="es_MX", parametros=(),
                         documento=None):
        return self._guardar(tipo="plantilla", telefono=telefono, plantilla=plantilla,
                             idioma=idioma, parametros=list(parametros), documento=documento)

    def verificar_firma_webhook(self, cuerpo, encabezados, url=""):
        return _firma_meta_valida(self.secreto, cuerpo, encabezados)

    def parsear_webhook(self, cuerpo, encabezados=None):
        return _parsear_meta(cuerpo)


def _firma_meta_valida(secreto: str, cuerpo: bytes, encabezados: Mapping[str, str]) -> bool:
    recibida = _encabezado(encabezados, "X-Hub-Signature-256")
    esperada = "sha256=" + hmac.new(secreto.encode(), cuerpo, hashlib.sha256).hexdigest()
    return bool(recibida) and hmac.compare_digest(recibida, esperada)


def _parsear_meta(cuerpo: bytes) -> list[MensajeEntrante]:
    datos = json.loads(cuerpo or b"{}")
    salida: list[MensajeEntrante] = []
    for entrada in datos.get("entry", []):
        for cambio in entrada.get("changes", []):
            for m in cambio.get("value", {}).get("messages", []) or []:
                tipo = m.get("type", "")
                texto = m.get("text", {}).get("body", "") if tipo == "text" else ""
                salida.append(MensajeEntrante(
                    telefono=m.get("from", ""), texto=texto, id_mensaje=m.get("id", ""),
                    tipo="texto" if tipo == "text" else tipo,
                ))
    return salida


class WhatsAppMeta:
    """WhatsApp Cloud API de Meta (Graph API)."""

    def __init__(
        self, token: str, phone_number_id: str, app_secret: str,
        version: str = "v20.0", http: httpx.Client | None = None,
    ) -> None:
        self._token, self._secreto = token, app_secret
        self.url = f"https://graph.facebook.com/{version}/{phone_number_id}/messages"
        self._http = cliente_http(http)

    def _mandar(self, telefono: str, **contenido: Any) -> str:
        cuerpo = {"messaging_product": "whatsapp", "to": telefono, **contenido}
        r = self._http.post(
            self.url, json=cuerpo, headers={"Authorization": f"Bearer {self._token}"}
        )
        return str(revisar(r, "WhatsApp (Meta)").json()["messages"][0]["id"])

    def enviar_texto(self, telefono, texto):
        return self._mandar(telefono, type="text", text={"body": texto})

    def enviar_documento(self, telefono, url_documento, nombre, leyenda=""):
        doc = {"link": url_documento, "filename": nombre}
        if leyenda:
            doc["caption"] = leyenda
        return self._mandar(telefono, type="document", document=doc)

    def enviar_plantilla(self, telefono, plantilla, idioma="es_MX", parametros=(),
                         documento=None):
        plantilla_cuerpo: dict[str, Any] = {"name": plantilla, "language": {"code": idioma}}
        componentes: list[dict[str, Any]] = []
        if documento is not None:
            # Plantilla con encabezado de tipo DOCUMENT (Cloud API, "template" → "header").
            componentes.append({"type": "header", "parameters": [{
                "type": "document",
                "document": {"link": documento.url, "filename": documento.nombre},
            }]})
        if parametros:
            componentes.append({
                "type": "body",
                "parameters": [{"type": "text", "text": p} for p in parametros],
            })
        if componentes:
            plantilla_cuerpo["components"] = componentes
        return self._mandar(telefono, type="template", template=plantilla_cuerpo)

    def verificar_firma_webhook(self, cuerpo, encabezados, url=""):
        return _firma_meta_valida(self._secreto, cuerpo, encabezados)

    def parsear_webhook(self, cuerpo, encabezados=None):
        return _parsear_meta(cuerpo)


class WhatsAppTwilio:
    """Twilio Messaging API con remitente `whatsapp:+...`."""

    def __init__(
        self, account_sid: str, auth_token: str, remitente: str,
        http: httpx.Client | None = None,
    ) -> None:
        self._sid, self._token = account_sid, auth_token
        self.remitente = remitente if remitente.startswith("whatsapp:") else f"whatsapp:{remitente}"
        self.url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
        self._http = cliente_http(http)

    def _mandar(self, telefono: str, **datos: str) -> str:
        para = telefono if telefono.startswith("whatsapp:") else f"whatsapp:{telefono}"
        r = self._http.post(
            self.url, data={"From": self.remitente, "To": para, **datos},
            auth=(self._sid, self._token),
        )
        return str(revisar(r, "WhatsApp (Twilio)").json()["sid"])

    def enviar_texto(self, telefono, texto):
        return self._mandar(telefono, Body=texto)

    def enviar_documento(self, telefono, url_documento, nombre, leyenda=""):
        return self._mandar(telefono, Body=leyenda or nombre, MediaUrl=url_documento)

    def enviar_plantilla(self, telefono, plantilla, idioma="es_MX", parametros=(),
                         documento=None):
        # En Twilio la plantilla es un Content SID (HX...) y las variables van numeradas. El
        # documento va como la variable siguiente: la plantilla de Content API debe declarar
        # su media con esa variable (POR CONFIRMAR contra la plantilla aprobada).
        valores = [*parametros, *([documento.url] if documento is not None else [])]
        variables = json.dumps({str(i + 1): p for i, p in enumerate(valores)})
        return self._mandar(telefono, ContentSid=plantilla, ContentVariables=variables)

    def verificar_firma_webhook(self, cuerpo, encabezados, url=""):
        """X-Twilio-Signature = base64(HMAC-SHA1(token, url + params ordenados))."""
        recibida = _encabezado(encabezados, "X-Twilio-Signature")
        params = sorted(parse_qsl(cuerpo.decode("utf-8"), keep_blank_values=True))
        base = url + "".join(k + v for k, v in params)
        esperada = base64.b64encode(
            hmac.new(self._token.encode(), base.encode(), hashlib.sha1).digest()
        ).decode()
        return bool(recibida) and hmac.compare_digest(recibida, esperada)

    def parsear_webhook(self, cuerpo, encabezados=None):
        p = dict(parse_qsl(cuerpo.decode("utf-8"), keep_blank_values=True))
        if not p.get("MessageSid"):
            return []
        media = int(p.get("NumMedia", "0") or 0)
        return [MensajeEntrante(
            telefono=p.get("From", "").removeprefix("whatsapp:"),
            texto=p.get("Body", ""), id_mensaje=p["MessageSid"],
            tipo="documento" if media else "texto",
        )]


DESCRIPCION = "WhatsApp Business (envío de documentos y avisos, bot con IA)"
registro.registrar("whatsapp", "falso", WhatsAppFalso, DESCRIPCION)
registro.registrar("whatsapp", "meta", lambda: WhatsAppMeta(
    env("FISCALITO_WHATSAPP_TOKEN"), env("FISCALITO_WHATSAPP_PHONE_ID"),
    env("FISCALITO_WHATSAPP_APP_SECRET"), env("FISCALITO_WHATSAPP_VERSION", "v20.0"),
), DESCRIPCION)
registro.registrar("whatsapp", "twilio", lambda: WhatsAppTwilio(
    env("FISCALITO_TWILIO_ACCOUNT_SID"), env("FISCALITO_TWILIO_AUTH_TOKEN"),
    env("FISCALITO_TWILIO_WHATSAPP_FROM"),
), DESCRIPCION)
