"""
Representación impresa (PDF) del CFDI de retenciones, con QR (P3-04).

El QR lleva la URL de verificación de retenciones del SAT con id (UUID), re (RFC emisor),
rr (RFC receptor), tt (monto total de la operación) y fe (últimos 8 caracteres del sello).
# POR CONFIRMAR: la URL y el formato de `tt` se tomaron de la guía de la representación
impresa del CFDI 4.0 (Anexo 20) por analogía; no se encontró la guía específica de
retenciones 2.0 publicada en el portal del SAT desde este entorno.

Si el PAC es el `falso`, la constancia lo dice en grande: NO tiene validez fiscal.
"""

from __future__ import annotations

import io
from decimal import Decimal
from typing import Any

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas

from app.retenciones_cfdi import generador

URL_VERIFICACION = "https://prodretencionverificacion.clouda.sat.gob.mx/"
MESES = ("", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre")


def contenido_qr(d: dict[str, Any]) -> str:
    total = Decimal(d["totales"].get("MontoTotOperacion", "0"))
    return (f"{URL_VERIFICACION}?id={d['timbre'].get('UUID', '')}"
            f"&re={d['emisor'].get('RfcE', '')}&rr={d['receptor'].get('RfcR', '')}"
            f"&tt={total:025.6f}&fe={d['raiz'].get('Sello', '')[-8:]}")


def _partir(texto: str, ancho: int) -> list[str]:
    return [texto[i:i + ancho] for i in range(0, len(texto), ancho)] or [""]


def constancia(xml: bytes, es_prueba: bool = False) -> bytes:
    """PDF de una página con los datos del comprobante, el timbre y el QR."""
    d = generador.leer(xml)
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=LETTER)
    c.setTitle("Constancia de retenciones")
    ancho, alto = LETTER
    y = alto - 50
    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, y, "CFDI de Retenciones e información de pagos 2.0")
    if es_prueba:
        c.setFillColorRGB(0.75, 0.1, 0.1)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(40, y - 18, "DOCUMENTO DE PRUEBA - NO FISCAL - timbre sintético sin "
                                 "validez ante el SAT")
        c.setFillColorRGB(0, 0, 0)
    y -= 44
    p, t, raiz, rec = d["periodo"], d["totales"], d["raiz"], d["receptor"]
    clave = raiz.get("CveRetenc", "")
    renglones = [
        ("Emisor", f"{d['emisor'].get('NomDenRazSocE', '')}  RFC {d['emisor'].get('RfcE', '')}"
                   f"  Régimen {d['emisor'].get('RegimenFiscalE', '')}"),
        ("Receptor", f"{rec.get('NomDenRazSocR', '')}  RFC {rec.get('RfcR', '')}  CP "
                     f"{rec.get('DomicilioFiscalR', '')}"),
        ("Periodo", f"{MESES[int(p.get('MesIni', 1))]} a {MESES[int(p.get('MesFin', 1))]} "
                    f"{p.get('Ejercicio', '')}"),
        ("Clave de retención", f"{clave} {generador.CVE_RETENC.get(clave, '')}"),
        ("Fecha de expedición", f"{raiz.get('FechaExp', '')}  Lugar "
                                f"{raiz.get('LugarExpRetenc', '')}"),
        ("Monto de la operación", f"${Decimal(t.get('MontoTotOperacion', '0')):,.2f}"),
        ("Gravado / exento", f"${Decimal(t.get('MontoTotGrav', '0')):,.2f} / "
                             f"${Decimal(t.get('MontoTotExent', '0')):,.2f}"),
        ("Total retenido", f"${Decimal(t.get('MontoTotRet', '0')):,.2f}"),
    ]
    for etiqueta, valor in renglones:
        c.setFont("Helvetica-Bold", 9)
        c.drawString(40, y, etiqueta)
        c.setFont("Helvetica", 9)
        c.drawString(170, y, valor[:95])
        y -= 15
    y -= 6
    c.setFont("Helvetica-Bold", 9)
    c.drawString(40, y, "Impuestos retenidos")
    y -= 14
    c.setFont("Helvetica", 9)
    for i in d["impuestos"]:
        nombre = {"001": "ISR", "002": "IVA", "003": "IEPS"}.get(i.get("ImpuestoRet", ""), "")
        tipo = generador.TIPO_PAGO_RET.get(i.get("TipoPagoRet", ""), "")
        c.drawString(50, y, f"{nombre}: base ${Decimal(i.get('BaseRet', '0')):,.2f}  retenido "
                            f"${Decimal(i.get('MontoRet', '0')):,.2f}  ({tipo})")
        y -= 13
    timbre = d["timbre"]
    y -= 10
    for etiqueta, valor in (("Folio fiscal (UUID)", timbre.get("UUID", "")),
                            ("Fecha de certificación", timbre.get("FechaTimbrado", "")),
                            ("RFC del PAC", timbre.get("RfcProvCertif", "")),
                            ("No. de certificado del emisor", raiz.get("NoCertificado", "")),
                            ("No. de certificado SAT", timbre.get("NoCertificadoSAT", ""))):
        c.setFont("Helvetica-Bold", 8)
        c.drawString(40, y, etiqueta)
        c.setFont("Helvetica", 8)
        c.drawString(190, y, valor)
        y -= 12
    if timbre:
        qr = QrCodeWidget(contenido_qr(d))
        x0, y0, x1, y1 = qr.getBounds()
        lado = 110
        dibujo = Drawing(lado, lado, transform=[lado / (x1 - x0), 0, 0, lado / (y1 - y0), 0, 0])
        dibujo.add(qr)
        renderPDF.draw(dibujo, c, ancho - 40 - lado, y + 10)
    for etiqueta, valor in (("Sello digital del emisor", raiz.get("Sello", "")),
                            ("Sello del SAT", timbre.get("SelloSAT", "")),
                            ("Cadena original del complemento de certificación",
                             d["cadena_tfd"])):
        y -= 8
        c.setFont("Helvetica-Bold", 7)
        c.drawString(40, y, etiqueta)
        c.setFont("Courier", 6)
        for linea in _partir(valor, 120)[:6]:
            y -= 8
            c.drawString(40, y, linea)
    c.setFont("Helvetica", 7)
    c.drawString(40, 30, "Este documento es una representación impresa de un CFDI de "
                         "retenciones e información de pagos.")
    c.showPage()
    c.save()
    return buf.getvalue()
