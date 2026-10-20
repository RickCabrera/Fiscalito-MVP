"""
Enlaces firmados para que WhatsApp descargue un documento (P4-13; P5-05 lo reusa).

La Cloud API de Meta (y Twilio) no reciben el archivo: reciben una URL pública de la que lo
bajan. Se publica `GET /api/v1/<ruta>/descarga/{envio_id}/{archivo}?vence=…&firma=…`, sin
sesión, con firma HMAC-SHA256 y vigencia de 7 días. Sin firma válida o vencida → 404 (no se
distingue, para no confirmar que el envío existe).

Dos ÁMBITOS con el mismo secreto y mensajes que no se confunden:
- `recibos` (P4-13): `/recibos/descarga/…`, firma de `envio_id:archivo:vence` (el formato
  original; los enlaces ya mandados siguen valiendo).
- `documentos` (P5-05): `/documentos/descarga/…`, firma de `documentos:envio_id:archivo:vence`
  — un enlace de un ámbito no abre el otro aunque el número de envío coincida.

Variables: `FISCALITO_ENLACES_SECRETO` (obligatoria en producción) y
`FISCALITO_URL_PUBLICA_API` (la URL con la que Meta llega a esta API).
"""

from __future__ import annotations

import hashlib
import hmac
import os
import time

from app.config import settings
from app.exceptions import FiscalAgentError

VIGENCIA_SEGUNDOS = 7 * 24 * 3600
ARCHIVOS = ("recibo.pdf", "recibo.xml")
ARCHIVOS_POR_AMBITO = {"recibos": ARCHIVOS, "documentos": ("documento.pdf", "documento.xml")}


def _secreto() -> bytes:
    valor = os.environ.get("FISCALITO_ENLACES_SECRETO", "").strip()
    if valor:
        return valor.encode()
    if settings.ENTORNO == "produccion":
        raise FiscalAgentError(
            "Falta FISCALITO_ENLACES_SECRETO (ver docs/servicios-externos.md).", 503)
    return b"secreto-de-desarrollo-no-usar-en-produccion"


def firma(envio_id: int, archivo: str, vence: int, ambito: str = "recibos") -> str:
    prefijo = "" if ambito == "recibos" else f"{ambito}:"
    return hmac.new(_secreto(), f"{prefijo}{envio_id}:{archivo}:{vence}".encode(),
                    hashlib.sha256).hexdigest()


def url_firmada(envio_id: int, archivo: str, ahora: float | None = None,
                ambito: str = "recibos") -> str:
    vence = int((ahora or time.time()) + VIGENCIA_SEGUNDOS)
    base = os.environ.get("FISCALITO_URL_PUBLICA_API", "http://localhost:8000").rstrip("/")
    return (f"{base}/api/v1/{ambito}/descarga/{envio_id}/{archivo}"
            f"?vence={vence}&firma={firma(envio_id, archivo, vence, ambito)}")


def verificar(envio_id: int, archivo: str, vence: int, recibida: str,
              ahora: float | None = None, ambito: str = "recibos") -> bool:
    if archivo not in ARCHIVOS_POR_AMBITO[ambito] or vence < (ahora or time.time()):
        return False
    return hmac.compare_digest(firma(envio_id, archivo, vence, ambito), recibida or "")
