"""
Representación impresa de la factura (CFDI 4.0 I/E/P) en PDF con QR — P5-04.

El QR y su contenido son los del recibo de nómina (`app.nomina_cfdi.pdf.contenido_qr`: URL de
verificación del SAT con id, re, rr, tt y fe, Anexo 20), con la misma salvedad sobre el formato
de `tt`. Con el PAC falso el PDF lo dice en grande: NO tiene validez fiscal.
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

from app.facturacion import esquemas
from app.facturacion.catalogos import FORMA_PAGO, METODO_PAGO, USO_CFDI
from app.nomina_cfdi.pdf import contenido_qr

N = {"c": esquemas.NS_CFDI, "t": esquemas.NS_TFD, "p": esquemas.NS_PAGOS}
TITULO = {"I": "Factura (CFDI de ingreso)", "E": "Nota de crédito (CFDI de egreso)",
          "P": "Recibo electrónico de pago (CFDI con complemento de pagos 2.0)"}
IMPUESTO = {"001": "ISR", "002": "IVA"}


def leer(xml: bytes) -> dict[str, Any]:
    raiz = esquemas.parsear(xml)

    def at(ruta: str) -> dict[str, str]:
        n = raiz.find(ruta, N)
        return dict(n.attrib) if n is not None else {}

    tfd = raiz.find("c:Complemento/t:TimbreFiscalDigital", N)
    conceptos = []
    for c in raiz.findall("c:Conceptos/c:Concepto", N):
        conceptos.append({**dict(c.attrib), "impuestos": [
            {**dict(i.attrib), "tipo": "retencion" if i.tag.endswith("Retencion") else "traslado"}
            for i in c.findall("c:Impuestos/*/*", N)]})
    return {
        "raiz": dict(raiz.attrib), "emisor": at("c:Emisor"), "receptor": at("c:Receptor"),
        "conceptos": conceptos, "impuestos": at("c:Impuestos"),
        "traslados": [dict(n.attrib) for n in raiz.findall("c:Impuestos/c:Traslados/c:Traslado",
                                                           N)],
        "retenciones": [dict(n.attrib) for n in
                        raiz.findall("c:Impuestos/c:Retenciones/c:Retencion", N)],
        "relacionados": [(r.get("TipoRelacion", ""), [u.get("UUID", "") for u in r])
                         for r in raiz.findall("c:CfdiRelacionados", N)],
        "pagos": [{**dict(p.attrib), "documentos": [dict(d.attrib) for d in
                                                    p.findall("p:DoctoRelacionado", N)]}
                  for p in raiz.findall("c:Complemento/p:Pagos/p:Pago", N)],
        "timbre": dict(tfd.attrib) if tfd is not None else {},
        "cadena_tfd": esquemas.cadena_original_tfd(tfd) if tfd is not None else "",
    }


def _m(v: str | None) -> str:
    return f"${Decimal(v or '0'):,.2f}"


def factura(xml: bytes, es_prueba: bool = False) -> bytes:
    d = leer(xml)
    raiz, e, r, t = d["raiz"], d["emisor"], d["receptor"], d["timbre"]
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=LETTER)
    c.setTitle(TITULO.get(raiz.get("TipoDeComprobante", ""), "CFDI"))
    ancho, alto = LETTER
    y = alto - 46

    def linea(etiqueta: str, valor: str, x: float = 40, sep: float = 130) -> None:
        nonlocal y
        if y < 70:
            c.showPage()
            y = alto - 46
        c.setFont("Helvetica-Bold", 8.5)
        c.drawString(x, y, etiqueta)
        c.setFont("Helvetica", 8.5)
        c.drawString(x + sep, y, valor[:105])
        y -= 12

    c.setFont("Helvetica-Bold", 13)
    c.drawString(40, y, TITULO.get(raiz.get("TipoDeComprobante", ""), "CFDI 4.0"))
    if es_prueba:
        c.setFillColorRGB(0.75, 0.1, 0.1)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(40, y - 16, "DOCUMENTO DE PRUEBA - NO FISCAL - timbre sintético sin validez "
                                 "ante el SAT")
        c.setFillColorRGB(0, 0, 0)
    y -= 38
    linea("Emisor", f"{e.get('Nombre', '')}  RFC {e.get('Rfc', '')}  Régimen "
                    f"{e.get('RegimenFiscal', '')}")
    linea("Receptor", f"{r.get('Nombre', '')}  RFC {r.get('Rfc', '')}  CP "
                      f"{r.get('DomicilioFiscalReceptor', '')}  Régimen "
                      f"{r.get('RegimenFiscalReceptor', '')}")
    uso = r.get("UsoCFDI", "")
    linea("Uso CFDI", f"{uso} {USO_CFDI.get(uso, '')}")
    linea("Serie y folio", f"{raiz.get('Serie', '')}-{raiz.get('Folio', '')}  Fecha "
                           f"{raiz.get('Fecha', '')}  Lugar {raiz.get('LugarExpedicion', '')}")
    if raiz.get("TipoDeComprobante") != "P":
        fp, mp = raiz.get("FormaPago", ""), raiz.get("MetodoPago", "")
        linea("Pago", f"Forma {fp} {FORMA_PAGO.get(fp, '')} · Método {mp} "
                      f"{METODO_PAGO.get(mp, '')}")
    for tipo, uuids in d["relacionados"]:
        linea(f"Relación {tipo}", ", ".join(uuids))
    y -= 6
    c.setFont("Helvetica-Bold", 9)
    c.drawString(40, y, "Cant.  Clave  Descripción")
    c.drawRightString(ancho - 120, y, "V. unitario")
    c.drawRightString(ancho - 40, y, "Importe")
    y -= 12
    for k in d["conceptos"]:
        c.setFont("Helvetica", 8.5)
        c.drawString(40, y, f"{k.get('Cantidad')}  {k.get('ClaveProdServ')}  "
                            f"{k.get('Descripcion', '')}"[:85])
        c.drawRightString(ancho - 120, y, _m(k.get("ValorUnitario")))
        c.drawRightString(ancho - 40, y, _m(k.get("Importe")))
        y -= 11
        for i in k["impuestos"]:
            tasa = i.get("TasaOCuota")
            texto = (f"{'Ret.' if i['tipo'] == 'retencion' else 'Tras.'} "
                     f"{IMPUESTO.get(i.get('Impuesto', ''), '')} "
                     f"{i.get('TipoFactor')} {tasa or ''} base {_m(i.get('Base'))}")
            c.setFont("Helvetica", 7.5)
            c.drawString(60, y, texto)
            c.drawRightString(ancho - 40, y, _m(i.get("Importe")) if i.get("Importe") else "")
            y -= 10
    for p in d["pagos"]:
        linea("Pago", f"{p.get('FechaPago')}  forma {p.get('FormaDePagoP')}  monto "
                      f"{_m(p.get('Monto'))}")
        for doc in p["documentos"]:
            linea("  Documento", f"{doc.get('IdDocumento')} parcialidad "
                                 f"{doc.get('NumParcialidad')} saldo ant. "
                                 f"{_m(doc.get('ImpSaldoAnt'))} pagado {_m(doc.get('ImpPagado'))}"
                                 f" insoluto {_m(doc.get('ImpSaldoInsoluto'))}")
    y -= 4
    if raiz.get("TipoDeComprobante") != "P":
        linea("Subtotal", _m(raiz.get("SubTotal")), x=ancho - 250, sep=120)
        if raiz.get("Descuento"):
            linea("Descuento", _m(raiz.get("Descuento")), x=ancho - 250, sep=120)
        for i in d["traslados"]:
            linea(f"{IMPUESTO.get(i.get('Impuesto', ''), '')} {i.get('TasaOCuota') or 'exento'}",
                  _m(i.get("Importe")), x=ancho - 250, sep=120)
        for i in d["retenciones"]:
            linea(f"Ret. {IMPUESTO.get(i.get('Impuesto', ''), '')}", _m(i.get("Importe")),
                  x=ancho - 250, sep=120)
        linea("Total", _m(raiz.get("Total")), x=ancho - 250, sep=120)
    y -= 8
    for etiqueta, valor in (("Folio fiscal (UUID)", t.get("UUID", "")),
                            ("Fecha de certificación", t.get("FechaTimbrado", "")),
                            ("RFC del PAC", t.get("RfcProvCertif", "")),
                            ("No. de certificado del emisor", raiz.get("NoCertificado", "")),
                            ("No. de certificado SAT", t.get("NoCertificadoSAT", ""))):
        linea(etiqueta, valor, sep=150)
    if t:
        if y < 200:
            c.showPage()
            y = alto - 46
        qr = QrCodeWidget(contenido_qr({**d, "raiz": raiz}))
        x0, y0, x1, y1 = qr.getBounds()
        lado = 110
        dibujo = Drawing(lado, lado, transform=[lado / (x1 - x0), 0, 0, lado / (y1 - y0), 0, 0])
        dibujo.add(qr)
        renderPDF.draw(dibujo, c, ancho - 40 - lado, y - lado + 50)
    for etiqueta, valor in (("Sello digital del emisor", raiz.get("Sello", "")),
                            ("Sello del SAT", t.get("SelloSAT", "")),
                            ("Cadena original del complemento de certificación",
                             d["cadena_tfd"])):
        y -= 8
        c.setFont("Helvetica-Bold", 7)
        c.drawString(40, y, etiqueta)
        c.setFont("Courier", 6)
        for i in range(0, min(len(valor), 600), 110):
            y -= 8
            c.drawString(40, y, valor[i:i + 110])
    c.setFont("Helvetica", 7)
    c.drawString(40, 30, "Este documento es una representación impresa de un CFDI.")
    c.showPage()
    c.save()
    return buf.getvalue()
