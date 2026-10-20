"""
Representación impresa del CFDI de nómina (recibo PDF con QR), P4-11.

QR: URL de verificación del CFDI 4.0 del SAT con `id` (UUID), `re` (RFC emisor), `rr` (RFC
receptor), `tt` (total) y `fe` (últimos 8 caracteres del sello), Anexo 20.
# POR CONFIRMAR: el formato de `tt` (aquí 25 posiciones: 18 enteros, punto y 6 decimales, como
la constancia de retenciones de P3-04) contra la guía de la representación impresa vigente.

Con el PAC falso el recibo lo dice en grande: NO tiene validez fiscal.
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

from app.nomina_cfdi import esquemas

URL_VERIFICACION = "https://verificacfdi.facturaelectronica.sat.gob.mx/default.aspx"
N = {"c": esquemas.NS_CFDI, "n": esquemas.NS_NOMINA, "t": esquemas.NS_TFD}


def _todos(raiz: Any, ruta: str) -> list[dict[str, str]]:
    return [dict(p.attrib) for p in raiz.findall(ruta, N)]


def leer(xml: bytes) -> dict[str, Any]:
    raiz = esquemas.parsear(xml)

    def at(ruta: str) -> dict[str, str]:
        n = raiz.find(ruta, N)
        return dict(n.attrib) if n is not None else {}

    tfd = raiz.find("c:Complemento/t:TimbreFiscalDigital", N)
    nomina = "c:Complemento/n:Nomina"
    return {
        "raiz": dict(raiz.attrib), "emisor": at("c:Emisor"), "receptor": at("c:Receptor"),
        "nomina": at(nomina), "nomina_receptor": at(f"{nomina}/n:Receptor"),
        "nomina_emisor": at(f"{nomina}/n:Emisor"),
        "percepciones": _todos(raiz, f"{nomina}/n:Percepciones/n:Percepcion"),
        "deducciones": _todos(raiz, f"{nomina}/n:Deducciones/n:Deduccion"),
        "otros_pagos": _todos(raiz, f"{nomina}/n:OtrosPagos/n:OtroPago"),
        "timbre": dict(tfd.attrib) if tfd is not None else {},
        "cadena_tfd": esquemas.cadena_original_tfd(tfd) if tfd is not None else "",
    }


def contenido_qr(d: dict[str, Any]) -> str:
    total = Decimal(d["raiz"].get("Total", "0"))
    return (f"{URL_VERIFICACION}?id={d['timbre'].get('UUID', '')}"
            f"&re={d['emisor'].get('Rfc', '')}&rr={d['receptor'].get('Rfc', '')}"
            f"&tt={total:025.6f}&fe={d['raiz'].get('Sello', '')[-8:]}")


def _m(v: str | None) -> str:
    return f"${Decimal(v or '0'):,.2f}"


def recibo(xml: bytes, es_prueba: bool = False) -> bytes:
    """PDF de una página: datos del patrón y del trabajador, partidas, timbre y QR."""
    d = leer(xml)
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=LETTER)
    c.setTitle("Recibo de nómina")
    ancho, alto = LETTER
    y = alto - 46
    c.setFont("Helvetica-Bold", 13)
    c.drawString(40, y, "Recibo de nómina — CFDI 4.0 con complemento de nómina 1.2")
    if es_prueba:
        c.setFillColorRGB(0.75, 0.1, 0.1)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(40, y - 16, "DOCUMENTO DE PRUEBA - NO FISCAL - timbre sintético sin validez "
                                 "ante el SAT")
        c.setFillColorRGB(0, 0, 0)
    y -= 40
    e, r, n, nr = d["emisor"], d["receptor"], d["nomina"], d["nomina_receptor"]
    renglones = [
        ("Patrón", f"{e.get('Nombre', '')}  RFC {e.get('Rfc', '')}  Régimen "
                   f"{e.get('RegimenFiscal', '')}  Reg. patronal "
                   f"{d['nomina_emisor'].get('RegistroPatronal', '—')}"),
        ("Trabajador", f"{r.get('Nombre', '')}  RFC {r.get('Rfc', '')}  CP "
                       f"{r.get('DomicilioFiscalReceptor', '')}"),
        ("CURP / NSS", f"{nr.get('Curp', '')} / {nr.get('NumSeguridadSocial', '—')}  "
                       f"No. empleado {nr.get('NumEmpleado', '')}"),
        ("Periodo", f"{n.get('FechaInicialPago', '')} a {n.get('FechaFinalPago', '')}  pago "
                    f"{n.get('FechaPago', '')}  días {n.get('NumDiasPagados', '')}  tipo "
                    f"{n.get('TipoNomina', '')}  régimen {nr.get('TipoRegimen', '')}"),
        ("SBC / SDI", f"{nr.get('SalarioBaseCotApor', '—')} / "
                      f"{nr.get('SalarioDiarioIntegrado', '—')}"),
    ]
    for etiqueta, valor in renglones:
        c.setFont("Helvetica-Bold", 8.5)
        c.drawString(40, y, etiqueta)
        c.setFont("Helvetica", 8.5)
        c.drawString(120, y, valor[:110])
        y -= 13
    y -= 6

    def bloque(titulo: str, filas: list[tuple[str, str]], y: float) -> float:
        c.setFont("Helvetica-Bold", 9)
        c.drawString(40, y, titulo)
        y -= 12
        c.setFont("Helvetica", 8.5)
        for izq, der in filas:
            c.drawString(50, y, izq[:80])
            c.drawRightString(ancho - 180, y, der)
            y -= 11
        return y - 4

    y = bloque("Percepciones", [(f"{p.get('TipoPercepcion')} {p.get('Concepto', '')}",
                                 _m(str(Decimal(p.get('ImporteGravado', '0'))
                                        + Decimal(p.get('ImporteExento', '0')))))
                                for p in d["percepciones"]], y)
    y = bloque("Deducciones", [(f"{x.get('TipoDeduccion')} {x.get('Concepto', '')}",
                                _m(x.get("Importe"))) for x in d["deducciones"]], y)
    if d["otros_pagos"]:
        y = bloque("Otros pagos", [(f"{x.get('TipoOtroPago')} {x.get('Concepto', '')}",
                                    _m(x.get("Importe"))) for x in d["otros_pagos"]], y)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, y, "Neto a pagar")
    c.drawRightString(ancho - 180, y, _m(d["raiz"].get("Total")))
    y -= 22
    t, raiz = d["timbre"], d["raiz"]
    for etiqueta, valor in (("Folio fiscal (UUID)", t.get("UUID", "")),
                            ("Fecha de certificación", t.get("FechaTimbrado", "")),
                            ("RFC del PAC", t.get("RfcProvCertif", "")),
                            ("No. de certificado del emisor", raiz.get("NoCertificado", "")),
                            ("No. de certificado SAT", t.get("NoCertificadoSAT", ""))):
        c.setFont("Helvetica-Bold", 8)
        c.drawString(40, y, etiqueta)
        c.setFont("Helvetica", 8)
        c.drawString(190, y, valor)
        y -= 11
    if t:
        qr = QrCodeWidget(contenido_qr(d))
        x0, y0, x1, y1 = qr.getBounds()
        lado = 110
        dibujo = Drawing(lado, lado, transform=[lado / (x1 - x0), 0, 0, lado / (y1 - y0), 0, 0])
        dibujo.add(qr)
        renderPDF.draw(dibujo, c, ancho - 40 - lado, y + 4)
    for etiqueta, valor in (("Sello digital del emisor", raiz.get("Sello", "")),
                            ("Sello del SAT", t.get("SelloSAT", "")),
                            ("Cadena original del complemento de certificación",
                             d["cadena_tfd"])):
        y -= 8
        c.setFont("Helvetica-Bold", 7)
        c.drawString(40, y, etiqueta)
        c.setFont("Courier", 6)
        for i in range(0, min(len(valor), 600), 120):
            y -= 8
            c.drawString(40, y, valor[i:i + 120])
    c.setFont("Helvetica", 7)
    c.drawString(40, 30, "Este documento es una representación impresa de un CFDI de nómina.")
    c.showPage()
    c.save()
    return buf.getvalue()
