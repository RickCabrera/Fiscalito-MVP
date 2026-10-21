"""
Correo transaccional (P0-06). `FISCALITO_CORREO` = falso | smtp | resend | sendgrid.

`enviar(destinatarios, asunto, html, adjuntos)` devuelve el id del mensaje que da el
proveedor (o uno local). Los adjuntos son `Adjunto(nombre, contenido, tipo_mime)`.
"""

import base64
import smtplib
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from email.message import EmailMessage
from email.utils import make_msgid
from typing import Protocol

import httpx

from app.integraciones import registro
from app.integraciones.comun import cliente_http, env, revisar


@dataclass(frozen=True)
class Adjunto:
    nombre: str
    contenido: bytes
    tipo_mime: str = "application/octet-stream"


class Correo(Protocol):
    def enviar(
        self,
        destinatarios: Sequence[str],
        asunto: str,
        html: str,
        adjuntos: Sequence[Adjunto] = (),
    ) -> str: ...


@dataclass
class MensajeEnviado:
    destinatarios: list[str]
    asunto: str
    html: str
    adjuntos: list[Adjunto] = field(default_factory=list)


class CorreoFalso:
    """No envía nada: guarda en `enviados` para que los tests lo consulten."""

    def __init__(self) -> None:
        self.enviados: list[MensajeEnviado] = []

    def enviar(self, destinatarios, asunto, html, adjuntos=()) -> str:
        self.enviados.append(MensajeEnviado(list(destinatarios), asunto, html, list(adjuntos)))
        return f"falso-{len(self.enviados)}"


def _validar(destinatarios: Sequence[str]) -> list[str]:
    limpios = [d.strip() for d in destinatarios if d and d.strip()]
    if not limpios:
        raise ValueError("El correo necesita al menos un destinatario.")
    return limpios


class CorreoSMTP:
    """SMTP con STARTTLS (o SSL en el puerto 465)."""

    def __init__(
        self,
        host: str,
        puerto: int,
        usuario: str,
        password: str,
        remitente: str,
        fabrica_smtp: Callable[..., smtplib.SMTP] | None = None,
    ) -> None:
        self.host, self.puerto = host, puerto
        self.usuario, self._password, self.remitente = usuario, password, remitente
        self._fabrica = fabrica_smtp or (smtplib.SMTP_SSL if puerto == 465 else smtplib.SMTP)

    def enviar(self, destinatarios, asunto, html, adjuntos=()) -> str:
        msg = EmailMessage()
        msg["From"], msg["To"], msg["Subject"] = self.remitente, ", ".join(
            _validar(destinatarios)
        ), asunto
        msg["Message-ID"] = make_msgid(domain=self.remitente.rsplit("@", 1)[-1].strip(">"))
        msg.set_content("Este mensaje requiere un cliente de correo con HTML.")
        msg.add_alternative(html, subtype="html")
        for a in adjuntos:
            principal, _, sub = a.tipo_mime.partition("/")
            msg.add_attachment(a.contenido, maintype=principal, subtype=sub or "octet-stream",
                               filename=a.nombre)
        with self._fabrica(self.host, self.puerto, timeout=20) as smtp:
            if self.puerto != 465:
                smtp.starttls()
            if self.usuario:
                smtp.login(self.usuario, self._password)
            smtp.send_message(msg)
        return str(msg["Message-ID"])


class CorreoResend:
    """Resend (https://resend.com) por su API HTTP."""

    URL = "https://api.resend.com/emails"

    def __init__(self, api_key: str, remitente: str, http: httpx.Client | None = None) -> None:
        self._api_key, self.remitente = api_key, remitente
        self._http = cliente_http(http)

    def enviar(self, destinatarios, asunto, html, adjuntos=()) -> str:
        cuerpo = {
            "from": self.remitente,
            "to": _validar(destinatarios),
            "subject": asunto,
            "html": html,
            "attachments": [
                {"filename": a.nombre, "content": base64.b64encode(a.contenido).decode()}
                for a in adjuntos
            ],
        }
        r = self._http.post(
            self.URL, json=cuerpo, headers={"Authorization": f"Bearer {self._api_key}"}
        )
        return str(revisar(r, "Resend").json()["id"])


class CorreoSendGrid:
    """SendGrid v3 `mail/send`. El id viene en el encabezado `X-Message-Id`."""

    URL = "https://api.sendgrid.com/v3/mail/send"

    def __init__(self, api_key: str, remitente: str, http: httpx.Client | None = None) -> None:
        self._api_key, self.remitente = api_key, remitente
        self._http = cliente_http(http)

    def enviar(self, destinatarios, asunto, html, adjuntos=()) -> str:
        cuerpo: dict = {
            "personalizations": [{"to": [{"email": d} for d in _validar(destinatarios)]}],
            "from": {"email": self.remitente},
            "subject": asunto,
            "content": [{"type": "text/html", "value": html}],
        }
        if adjuntos:
            cuerpo["attachments"] = [
                {"filename": a.nombre, "type": a.tipo_mime,
                 "content": base64.b64encode(a.contenido).decode()}
                for a in adjuntos
            ]
        r = self._http.post(
            self.URL, json=cuerpo, headers={"Authorization": f"Bearer {self._api_key}"}
        )
        return revisar(r, "SendGrid").headers.get("X-Message-Id", "")


def _smtp() -> CorreoSMTP:
    return CorreoSMTP(
        host=env("FISCALITO_SMTP_HOST"),
        puerto=int(env("FISCALITO_SMTP_PUERTO", "587")),
        usuario=env("FISCALITO_SMTP_USUARIO", ""),
        password=env("FISCALITO_SMTP_PASSWORD", ""),
        remitente=env("FISCALITO_CORREO_REMITENTE"),
    )


registrar = registro.registrar
DESCRIPCION = "Correo transaccional (avisos, recibos, papeles de trabajo)"
registrar("correo", "falso", CorreoFalso, DESCRIPCION)
registrar("correo", "smtp", _smtp, DESCRIPCION)
registrar("correo", "resend", lambda: CorreoResend(
    env("FISCALITO_RESEND_API_KEY"), env("FISCALITO_CORREO_REMITENTE")), DESCRIPCION)
registrar("correo", "sendgrid", lambda: CorreoSendGrid(
    env("FISCALITO_SENDGRID_API_KEY"), env("FISCALITO_CORREO_REMITENTE")), DESCRIPCION)
