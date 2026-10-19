"""
Lectura de los PDF del SAT (P1-05): sentido de la opinión 32-D y datos de la constancia.

Se extrae el texto con `pypdf` y se buscan frases. Nada se adivina: si el texto no trae una
frase reconocible, el resultado es `desconocido` y la pantalla lo dice.

# POR CONFIRMAR CON PDF REAL: las frases salen de la forma pública de la opinión 32-D
# ("...se emite opinión del cumplimiento de obligaciones fiscales en sentido POSITIVO/
# NEGATIVO", "INSCRITO SIN OBLIGACIONES", "Folio") y de la Cédula de Identificación Fiscal
# ("idCIF", "Lugar y Fecha de Emisión"). Se probaron con PDF sintéticos que imitan ese texto;
# un PDF real puede partir las líneas distinto. Si una opinión real sale `desconocido`,
# agrega su frase a `_SENTIDOS`.
"""

from __future__ import annotations

import io
import re
import unicodedata
from dataclasses import dataclass
from datetime import date

from app.exceptions import FiscalAgentError

FIRMA_PDF = b"%PDF-"
MAX_BYTES_PDF = 10 * 1024 * 1024

MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7,
    "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11,
    "diciembre": 12,
}

# Orden importa: "sin obligaciones" antes que "positivo" (esa opinión dice las dos).
_SENTIDOS: list[tuple[str, str]] = [
    (r"sin\s+obligaciones", "sin_obligaciones"),
    (r"sentido\s+negativo", "negativa"),
    (r"sentido\s+positivo", "positiva"),
    (r"opini[oó]n\s+negativa", "negativa"),
    (r"opini[oó]n\s+positiva", "positiva"),
]


@dataclass(frozen=True)
class LecturaPdf:
    resultado: str = "desconocido"
    folio: str = ""
    fecha: date | None = None
    rfc: str = ""
    texto_leido: bool = False


def _sin_acentos(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto)
                   if unicodedata.category(c) != "Mn")


def validar_pdf(datos: bytes) -> None:
    """422 si no parece PDF o pesa demasiado."""
    if len(datos) > MAX_BYTES_PDF:
        raise FiscalAgentError("El PDF pasa de 10 MB.", status_code=422)
    if not datos.lstrip()[:5].startswith(FIRMA_PDF):
        raise FiscalAgentError("El archivo no es un PDF.", status_code=422)


def texto_de(datos: bytes) -> str:
    """Texto plano del PDF ("" si no se puede leer: escaneado, cifrado o dañado)."""
    try:
        from pypdf import PdfReader

        lector = PdfReader(io.BytesIO(datos))
        return "\n".join((p.extract_text() or "") for p in lector.pages[:5])
    except Exception:  # noqa: BLE001 — un PDF raro no tumba la carga: queda desconocido
        return ""


def _fecha(texto: str) -> date | None:
    plano = _sin_acentos(texto).lower()
    m = re.search(r"(\d{1,2})\s+de\s+([a-z]+)\s+de\s+(\d{4})", plano)
    if m and m.group(2) in MESES:
        try:
            return date(int(m.group(3)), MESES[m.group(2)], int(m.group(1)))
        except ValueError:
            pass
    m = re.search(r"(\d{2})/(\d{2})/(\d{4})", plano)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            return None
    return None


def leer_opinion(datos: bytes) -> LecturaPdf:
    """Sentido, folio, fecha de revisión y RFC de una opinión 32-D."""
    texto = texto_de(datos)
    if not texto.strip():
        return LecturaPdf()
    plano = _sin_acentos(texto).lower()
    resultado = next((r for patron, r in _SENTIDOS if re.search(patron, plano)), "desconocido")
    folio = re.search(r"folio[:\s]+([a-z0-9\-]{6,40})", plano)
    revision = re.search(r"revision\s+practicada\s+el\s+dia\s+(.{0,40}\d{4})", plano)
    rfc = re.search(r"\b([a-z&n]{3,4}\d{6}[a-z0-9]{3})\b", plano)
    return LecturaPdf(
        resultado=resultado,
        folio=folio.group(1).upper() if folio else "",
        fecha=_fecha(revision.group(1)) if revision else _fecha(texto),
        rfc=rfc.group(1).upper() if rfc else "",
        texto_leido=True,
    )


def leer_constancia(datos: bytes) -> LecturaPdf:
    """idCIF (como folio), fecha de emisión y RFC de una constancia de situación fiscal."""
    texto = texto_de(datos)
    if not texto.strip():
        return LecturaPdf()
    plano = _sin_acentos(texto).lower()
    cif = re.search(r"idcif[:\s]+(\d{6,20})", plano)
    emision = re.search(r"fecha\s+de\s+emision[^\n]*?(\d{1,2}\s+de\s+[a-z]+\s+de\s+\d{4})", plano)
    rfc = re.search(r"rfc[:\s]+([a-z&n]{3,4}\d{6}[a-z0-9]{3})", plano)
    return LecturaPdf(
        resultado="desconocido",
        folio=cif.group(1) if cif else "",
        fecha=_fecha(emision.group(1)) if emision else _fecha(texto),
        rfc=rfc.group(1).upper() if rfc else "",
        texto_leido=True,
    )


def pdf_texto(lineas: list[str]) -> bytes:
    """
    Un PDF mínimo de una página con `lineas` en Helvetica. Lo usa el adaptador falso y los
    tests: así el PDF falso pasa por el MISMO lector que uno real.
    """

    def esc(s: str) -> str:
        return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    flujo = "BT /F1 11 Tf 50 780 Td 14 TL\n" + "".join(
        f"({esc(linea)}) Tj T*\n" for linea in lineas
    ) + "ET"
    contenido = flujo.encode("latin-1", errors="replace")
    objetos = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(contenido)).encode() + b" >>\nstream\n" + contenido
        + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
        b"/Encoding /WinAnsiEncoding >>",
    ]
    salida = bytearray(b"%PDF-1.4\n")
    posiciones = []
    for n, obj in enumerate(objetos, start=1):
        posiciones.append(len(salida))
        salida += f"{n} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(salida)
    salida += f"xref\n0 {len(objetos) + 1}\n0000000000 65535 f \n".encode()
    for p in posiciones:
        salida += f"{p:010d} 00000 n \n".encode()
    salida += (
        f"trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n"
    ).encode()
    return bytes(salida)
