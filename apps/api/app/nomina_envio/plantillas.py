"""
Plantillas del envío de recibos (P4-13), editables por despacho.

Variables: `{nombre}`, `{periodo}`, `{neto}`. Cualquier otra llave se deja tal cual (no
levanta: una plantilla con una errata no debe tumbar el envío de toda la nómina). En correo
los valores se escapan para HTML antes de sustituir.

WhatsApp no manda texto libre fuera de la ventana de 24 h: se usa una PLANTILLA APROBADA por
Meta (`plantilla_whatsapp`), cuyo cuerpo recibe los tres valores como parámetros en el orden
{{1}} nombre, {{2}} periodo, {{3}} neto, y cuyo encabezado es el documento (el PDF).
"""

from __future__ import annotations

import html
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modelos.nomina_envio import CANALES, PlantillaRecibo

VARIABLES = ("nombre", "periodo", "neto")
DEFAULTS: dict[str, dict[str, str]] = {
    "correo": {
        "asunto": "Tu recibo de nómina del periodo {periodo}",
        "cuerpo": "<p>Hola {nombre}:</p><p>Te compartimos tu recibo de nómina del periodo "
                  "{periodo}. Neto pagado: <strong>{neto}</strong>.</p>"
                  "<p>Si algo no cuadra, avísale a tu área de nómina.</p>",
        "plantilla_whatsapp": "",
        "idioma": "es_MX",
    },
    "whatsapp": {
        "asunto": "",
        "cuerpo": "Hola {nombre}, tu recibo de nómina del periodo {periodo} (neto {neto}).",
        "plantilla_whatsapp": "recibo_nomina",
        "idioma": "es_MX",
    },
}
_LLAVE = re.compile(r"\{(\w+)\}")


def renderizar(texto: str, valores: dict[str, str], *, escapar: bool = False) -> str:
    """Sustituye sólo las variables conocidas; lo demás queda igual."""
    def cambio(m: re.Match[str]) -> str:
        clave = m.group(1)
        if clave not in VARIABLES or clave not in valores:
            return m.group(0)
        return html.escape(valores[clave]) if escapar else valores[clave]

    return _LLAVE.sub(cambio, texto or "")


def de_despacho(db: Session, despacho_id: str, canal: str) -> dict[str, str]:
    """La plantilla del despacho para el canal, o el default si no ha editado ninguna."""
    fila = db.scalar(select(PlantillaRecibo).where(
        PlantillaRecibo.despacho_id == despacho_id, PlantillaRecibo.canal == canal))
    if fila is None:
        return {**DEFAULTS[canal], "canal": canal, "personalizada": ""}
    return {"canal": canal, "asunto": fila.asunto, "cuerpo": fila.cuerpo,
            "plantilla_whatsapp": fila.plantilla_whatsapp, "idioma": fila.idioma,
            "personalizada": "1"}


def guardar(db: Session, despacho_id: str, canal: str, datos: dict[str, str]) -> PlantillaRecibo:
    if canal not in CANALES:
        raise ValueError(canal)
    fila = db.scalar(select(PlantillaRecibo).where(
        PlantillaRecibo.despacho_id == despacho_id, PlantillaRecibo.canal == canal))
    if fila is None:
        fila = PlantillaRecibo(despacho_id=despacho_id, canal=canal)
        db.add(fila)
    fila.asunto = datos.get("asunto", "")
    fila.cuerpo = datos.get("cuerpo", "")
    fila.plantilla_whatsapp = datos.get("plantilla_whatsapp", "")
    fila.idioma = datos.get("idioma") or "es_MX"
    db.flush()
    return fila
