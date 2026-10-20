"""
Enlaces firmados para que WhatsApp descargue lo que el bot entrega (P5-06).

Como los recibos de P4-13: Meta y Twilio no reciben el archivo, reciben una URL pública de
la que lo bajan. `GET /api/v1/whatsapp/documentos/{mensaje_id}/{archivo}?vence=…&firma=…`,
sin sesión, con HMAC-SHA256 de `wa-bot:mensaje_id:archivo:vence` (prefijo propio: una firma
de recibo no abre un documento del bot ni al revés) y vigencia de 7 días. Firma inválida o
vencida → 404, igual que si no existiera.

Mismo secreto y misma URL pública que P4-13: `FISCALITO_ENLACES_SECRETO` y
`FISCALITO_URL_PUBLICA_API`.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import time

from app.nomina_envio.enlaces import VIGENCIA_SEGUNDOS, secreto

ARCHIVOS = ("opinion.pdf", "constancia.pdf", "facturas.zip")


def firma(mensaje_id: int, archivo: str, vence: int) -> str:
    return hmac.new(secreto(), f"wa-bot:{mensaje_id}:{archivo}:{vence}".encode(),
                    hashlib.sha256).hexdigest()


def url_firmada(mensaje_id: int, archivo: str, ahora: float | None = None) -> str:
    vence = int((ahora or time.time()) + VIGENCIA_SEGUNDOS)
    base = os.environ.get("FISCALITO_URL_PUBLICA_API", "http://localhost:8000").rstrip("/")
    return (f"{base}/api/v1/whatsapp/documentos/{mensaje_id}/{archivo}"
            f"?vence={vence}&firma={firma(mensaje_id, archivo, vence)}")


def verificar(mensaje_id: int, archivo: str, vence: int, recibida: str,
              ahora: float | None = None) -> bool:
    if archivo not in ARCHIVOS or vence < (ahora or time.time()):
        return False
    return hmac.compare_digest(firma(mensaje_id, archivo, vence), recibida or "")
