"""
Voz del asistente (P5-07, absorbe S-00). `FISCALITO_VOZ` = falso | openai.

Interfaz: `transcribir(audio, mime) -> str` (voz a texto, español) y
`sintetizar(texto) -> bytes` (texto a voz, MP3).

ANTES ESTO VIVÍA EN EL NAVEGADOR CON LA LLAVE EN EL BUNDLE
---------------------------------------------------------
`apps/store/src/services/voiceChatService.ts` llamaba a Whisper y a `tts-1` con
`VITE_OPENAI_API_KEY`: cualquier variable `VITE_*` se incrusta en el JavaScript que se
descarga, así que la llave viajaba a cada visitante. Ahora la llave vive sólo en el
servidor (`OPENAI_API_KEY`, la misma del adaptador `llm`) y el front habla con
`/api/v1/asistente/transcribir` y `/asistente/hablar` con su sesión de Firebase.

La real habla REST con httpx (como `llm.py`): se prueba con `httpx.MockTransport`.
"""

from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

from app.config import settings
from app.integraciones import registro
from app.integraciones.comun import ServicioNoConfigurado, cliente_http, revisar

# Tipos de audio que acepta la transcripción (tipo base, sin `;codecs=...`), con la extensión
# que se le pone al archivo: Whisper decide el formato por la extensión del nombre, así que
# el nombre se deriva del tipo YA validado, nunca del que mande el cliente.
EXTENSIONES = {
    "audio/webm": "webm", "audio/ogg": "ogg", "audio/mp4": "mp4", "audio/mpeg": "mp3",
    "audio/wav": "wav", "audio/x-wav": "wav",
}


class Voz(Protocol):
    def transcribir(self, audio: bytes, mime: str) -> str: ...
    def sintetizar(self, texto: str) -> bytes: ...


# Un MP3 mínimo (encabezado ID3 vacío): lo que devuelve el falso para que el front reciba
# un `audio/mpeg` con forma de archivo, sin red.
MP3_FALSO = b"ID3\x04\x00\x00\x00\x00\x00\x00"


@dataclass
class VozFalso:
    """Determinística y sin red. Guarda lo recibido en `transcritos` y `sintetizados`."""

    transcripcion: str = ""
    transcritos: list[dict[str, Any]] = field(default_factory=list)
    sintetizados: list[str] = field(default_factory=list)

    def transcribir(self, audio, mime):
        self.transcritos.append({"bytes": len(audio), "mime": mime})
        return self.transcripcion or f"[falso] audio de {len(audio)} bytes"

    def sintetizar(self, texto):
        self.sintetizados.append(texto)
        return MP3_FALSO


class VozOpenAI:
    """Whisper (`whisper-1`) para transcribir y `tts-1` (voz `nova`) para hablar."""

    URL_STT = "https://api.openai.com/v1/audio/transcriptions"
    URL_TTS = "https://api.openai.com/v1/audio/speech"

    def __init__(self, api_key: str, voz: str = "nova", http: httpx.Client | None = None):
        self._key, self.voz = api_key, voz
        self._http = cliente_http(http, timeout=httpx.Timeout(60.0, connect=10.0))

    def _auth(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._key}"}

    def transcribir(self, audio, mime):
        ext = EXTENSIONES[mime]
        r = self._http.post(
            self.URL_STT, headers=self._auth(),
            data={"model": "whisper-1", "language": "es"},
            files={"file": (f"audio.{ext}", audio, mime)},
        )
        return str(revisar(r, "OpenAI (voz a texto)").json().get("text", ""))

    def sintetizar(self, texto):
        r = self._http.post(self.URL_TTS, headers=self._auth(), json={
            "model": "tts-1", "input": texto, "voice": self.voz, "response_format": "mp3",
        })
        return revisar(r, "OpenAI (texto a voz)").content


def _llave() -> str:
    if not settings.OPENAI_API_KEY:
        raise ServicioNoConfigurado("Falta OPENAI_API_KEY para la voz del asistente.")
    return settings.OPENAI_API_KEY


DESCRIPCION = "Voz del asistente (voz a texto y texto a voz). La llave vive sólo en el servidor."
registro.registrar("voz", "falso", VozFalso, DESCRIPCION)
registro.registrar("voz", "openai", lambda: VozOpenAI(_llave()), DESCRIPCION)
