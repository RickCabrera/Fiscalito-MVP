"""
Envío de la contabilidad electrónica al SAT (P2-07). `FISCALITO_BUZON_SAT` = falso | portal_sat.

EL SAT NO TIENE API PARA ESTO
-----------------------------
La contabilidad electrónica se sube en el portal (sat.gob.mx → Contabilidad electrónica →
Envío de archivos) con la e.firma del contribuyente; el portal valida el XML y emite acuses.
Hoy el producto genera, valida y empaqueta el ZIP y muestra las instrucciones
(`app/contabilidad/anexo24/generador.INSTRUCCIONES_PORTAL`); el despacho lo sube a mano.

Este adaptador deja preparada la costura para automatizarlo después:

- `falso`: sin red. Acepta el ZIP, verifica que el nombre tenga la forma del SAT y devuelve
  un acuse sintético determinístico (`FALSO-<sha256[:12]>`). Lo usan los tests y el modo
  demostración. NO envía nada a ningún lado y el acuse lo dice.
- `portal_sat`: # POR CONFIRMAR CON E.FIRMA REAL: automatizar el portal con la e.firma del
  cliente (`obtener_firmante`), igual que `opinion_cumplimiento.portal_sat` (login FIEL de
  `satcfdi/portal`). El flujo de carga de contabilidad electrónica no está documentado por el
  SAT ni por `satcfdi`; no se adivina. Hoy responde 501 con un mensaje que dice qué falta.
  Ningún request sale de aquí.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from app.exceptions import FiscalAgentError
from app.integraciones import registro

RE_NOMBRE = re.compile(
    r"^[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}\d{4}(0[1-9]|1[0-3])(CT|BN|BC|PL|XC|XF)\.zip$")


@dataclass(frozen=True)
class EnvioContabilidad:
    rfc: str
    nombre_zip: str
    zip_bytes: bytes
    # Perezoso: sólo `portal_sat` lo llama (así un cliente sin e.firma usa el falso).
    firmante: Callable[[], Any] | None = None


@dataclass(frozen=True)
class Acuse:
    folio: str
    estado: str  # recibido | simulado
    mensaje: str


class BuzonSat(Protocol):
    nombre: str

    def enviar(self, envio: EnvioContabilidad) -> Acuse: ...


def _validar(envio: EnvioContabilidad) -> None:
    if not RE_NOMBRE.match(envio.nombre_zip):
        raise FiscalAgentError(f"Nombre de archivo inválido para el SAT: {envio.nombre_zip}.",
                               422)
    if not envio.nombre_zip.startswith(envio.rfc):
        raise FiscalAgentError("El ZIP no es del RFC del contribuyente.", 422)
    if envio.zip_bytes[:2] != b"PK":
        raise FiscalAgentError("El archivo no es un ZIP.", 422)


class BuzonSatFalso:
    nombre = "falso"

    def enviar(self, envio: EnvioContabilidad) -> Acuse:
        _validar(envio)
        huella = hashlib.sha256(envio.zip_bytes).hexdigest()[:12].upper()
        return Acuse(f"FALSO-{huella}", "simulado",
                     "Simulación: no se envió nada al SAT. Sube el ZIP en el portal.")


class BuzonSatPortal:
    """# POR CONFIRMAR CON E.FIRMA REAL: carga en el portal del SAT. Hoy no implementado."""

    nombre = "portal_sat"

    def enviar(self, envio: EnvioContabilidad) -> Acuse:
        _validar(envio)
        raise FiscalAgentError(
            "El envío automático al portal del SAT aún no está implementado (POR CONFIRMAR "
            "con una e.firma real: el SAT no documenta el flujo de carga). Descarga el ZIP y "
            "súbelo en sat.gob.mx → Contabilidad electrónica.", 501)


registro.registrar("buzon_sat", "falso", BuzonSatFalso,
                   "Envío de contabilidad electrónica al SAT (sin API oficial)")
registro.registrar("buzon_sat", "portal_sat", BuzonSatPortal)
