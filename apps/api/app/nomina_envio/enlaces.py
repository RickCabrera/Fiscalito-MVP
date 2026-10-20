"""
Enlaces firmados para que WhatsApp descargue el recibo (P4-13).

La Cloud API de Meta (y Twilio) no reciben el archivo: reciben una URL pública de la que lo
bajan. Se publica `GET /api/v1/recibos/descarga/{envio_id}/{archivo}?vence=…&firma=…`, sin
sesión, con firma HMAC-SHA256 de `envio_id:archivo:vence` y vigencia de 7 días. Sin firma
válida o vencida → 404 (no se distingue, para no confirmar que el envío existe).

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


def _secreto() -> bytes:
    valor = os.environ.get("FISCALITO_ENLACES_SECRETO", "").strip()
    if valor:
        return valor.encode()
    if settings.ENTORNO == "produccion":
        raise FiscalAgentError(
            "Falta FISCALITO_ENLACES_SECRETO (ver docs/servicios-externos.md).", 503)
    return b"secreto-de-desarrollo-no-usar-en-produccion"


def firma(envio_id: int, archivo: str, vence: int) -> str:
    return hmac.new(_secreto(), f"{envio_id}:{archivo}:{vence}".encode(),
                    hashlib.sha256).hexdigest()


def url_firmada(envio_id: int, archivo: str, ahora: float | None = None) -> str:
    vence = int((ahora or time.time()) + VIGENCIA_SEGUNDOS)
    base = os.environ.get("FISCALITO_URL_PUBLICA_API", "http://localhost:8000").rstrip("/")
    return (f"{base}/api/v1/recibos/descarga/{envio_id}/{archivo}"
            f"?vence={vence}&firma={firma(envio_id, archivo, vence)}")


def verificar(envio_id: int, archivo: str, vence: int, recibida: str,
              ahora: float | None = None) -> bool:
    if archivo not in ARCHIVOS or vence < (ahora or time.time()):
        return False
    return hmac.compare_digest(firma(envio_id, archivo, vence), recibida or "")
