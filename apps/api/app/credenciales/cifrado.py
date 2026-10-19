"""
Cifrado simétrico de la bóveda con la llave maestra de entorno.

LA LLAVE
--------
`FISCALITO_LLAVE_MAESTRA` trae una o varias llaves Fernet (base64 urlsafe de 32 bytes)
separadas por comas. **La primera cifra**; todas descifran (MultiFernet). Para rotar:

1. Genera una nueva:
   `python -c "from cryptography.fernet import Fernet as F; print(F.generate_key().decode())"`
2. Ponla PRIMERO: `FISCALITO_LLAVE_MAESTRA=<nueva>,<vieja>` y reinicia.
3. Corre `recifrar_todo(db)` (re-cifra cada credencial con la nueva).
4. Quita la vieja de la variable.

SIN LLAVE
---------
- En **producción** cualquier uso de la bóveda responde 503: nunca se inventa una llave.
- En **desarrollo** se genera una llave efímera por proceso, con aviso fuerte en el log: lo
  que se cifre con ella es ilegible tras reiniciar. Sirve para probar la pantalla, no para
  guardar una e.firma real.
"""

import logging

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from app.config import settings
from app.exceptions import FiscalAgentError

logger = logging.getLogger(__name__)

_EFIMERA: bytes | None = None


class BovedaNoDisponible(FiscalAgentError):
    """La bóveda no puede cifrar o descifrar (llave ausente, inválida o distinta)."""

    def __init__(self, mensaje: str) -> None:
        super().__init__(mensaje, status_code=503)


def _llaves_configuradas() -> list[bytes]:
    crudas = [k.strip() for k in (settings.LLAVE_MAESTRA or "").split(",") if k.strip()]
    return [k.encode("ascii") for k in crudas]


def _llave_efimera() -> bytes:
    global _EFIMERA
    if _EFIMERA is None:
        _EFIMERA = Fernet.generate_key()
        logger.warning(
            "BÓVEDA DE CREDENCIALES SIN LLAVE MAESTRA: se generó una llave EFÍMERA para este "
            "proceso. Todo lo que se guarde será ILEGIBLE al reiniciar. Configura "
            "FISCALITO_LLAVE_MAESTRA antes de subir una e.firma o CSD real."
        )
    return _EFIMERA


def cifrador() -> MultiFernet:
    """El MultiFernet vigente. 503 en producción si falta la llave maestra."""
    llaves = _llaves_configuradas()
    if not llaves:
        if settings.ENTORNO == "produccion":
            raise BovedaNoDisponible(
                "La bóveda de credenciales no está disponible: falta FISCALITO_LLAVE_MAESTRA "
                "en el servidor."
            )
        llaves = [_llave_efimera()]
    try:
        return MultiFernet([Fernet(k) for k in llaves])
    except (ValueError, TypeError) as e:
        raise BovedaNoDisponible(
            "FISCALITO_LLAVE_MAESTRA no es válida: cada llave debe ser base64 urlsafe de 32 "
            "bytes (genera una con Fernet.generate_key())."
        ) from e


def cifrar(datos: bytes) -> bytes:
    """Cifra con la primera llave."""
    return cifrador().encrypt(datos)


def descifrar(token: bytes) -> bytes:
    """Descifra con cualquiera de las llaves; 503 si ninguna corresponde."""
    try:
        return cifrador().decrypt(token)
    except InvalidToken as e:
        raise BovedaNoDisponible(
            "No se pudo leer la credencial guardada: la llave maestra del servidor no es la "
            "que la cifró (¿se cambió FISCALITO_LLAVE_MAESTRA sin conservar la anterior?)."
        ) from e


def recifrar(token: bytes) -> bytes:
    """Re-cifra un token con la llave primaria actual (rotación)."""
    try:
        return cifrador().rotate(token)
    except InvalidToken as e:
        raise BovedaNoDisponible(
            "No se pudo rotar la credencial: ninguna llave maestra configurada la descifra."
        ) from e


def olvidar_llave_efimera() -> None:
    """Para tests: simula un reinicio del proceso."""
    global _EFIMERA
    _EFIMERA = None
