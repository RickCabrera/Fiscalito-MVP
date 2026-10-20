"""Estado de cuenta del cliente en PDF (reportlab) y Excel (openpyxl) (P5-03)."""

from __future__ import annotations

import io
from decimal import Decimal
from typing import Any

from openpyxl import Workbook
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas

from app.exportar.excel_seguro import libro_a_bytes

TRAMOS_TEXTO = {"0_30": "0-30 días", "31_60": "31-60 días", "61_90": "61-90 días",
                "mas_90": "Más de 90 días"}


def _m(valor: str) -> str:
    return f"${Decimal(valor):,.2f}"


def excel(ec: dict[str, Any], despacho: str) -> bytes:
    wb = Workbook()
    h = wb.active
    h.title = "Estado de cuenta"
    h.append([f"Estado de cuenta · {ec['cliente_nombre'] or ec['cliente']}"])
    h.append([f"{despacho} · al {ec['hoy']}"])
    h.append([])
    h.append(["Fecha", "Concepto", "Vencimiento", "Cargo", "Abono", "Saldo", "UUID"])
    for m in ec["movimientos"]:
        h.append([m["fecha"], m["concepto"], m["vencimiento"] or "", Decimal(m["cargo"]),
                  Decimal(m["abono"]), Decimal(m["saldo"]), m["uuid"] or ""])
    h.append([])
    h.append(["Saldo", "", "", "", "", Decimal(ec["saldo"])])
    h.append(["Vencido", "", "", "", "", Decimal(ec["vencido"])])
    a = wb.create_sheet("Antigüedad")
    a.append(["Tramo", "Importe"])
    for k, texto in TRAMOS_TEXTO.items():
        a.append([texto, Decimal(ec["antiguedad"][k])])
    return libro_a_bytes(wb)


def pdf(ec: dict[str, Any], despacho: str) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=LETTER)
    c.setTitle("Estado de cuenta")
    ancho, alto = LETTER
    y = alto - 50

    def renglon(cols: list[tuple[float, str]], negrita: bool = False) -> None:
        nonlocal y
        if y < 60:
            c.showPage()
            y = alto - 50
        c.setFont("Helvetica-Bold" if negrita else "Helvetica", 9)
        for x, t in cols:
            c.drawString(x, y, t[:60])
        y -= 14

    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, y, f"Estado de cuenta · {ec['cliente_nombre'] or ec['cliente']}")
    y -= 18
    c.setFont("Helvetica", 10)
    c.drawString(40, y, f"{despacho} · al {ec['hoy']}")
    y -= 26
    cols = (40, 105, 300, 380, 450, 520)
    renglon(list(zip(cols, ("Fecha", "Concepto", "Vence", "Cargo", "Abono", "Saldo"),
                     strict=True)), negrita=True)
    for m in ec["movimientos"]:
        renglon(list(zip(cols, (m["fecha"], m["concepto"][:36], m["vencimiento"] or "",
                                _m(m["cargo"]) if Decimal(m["cargo"]) else "",
                                _m(m["abono"]) if Decimal(m["abono"]) else "",
                                _m(m["saldo"])), strict=True)))
    y -= 10
    renglon([(40, "Saldo"), (520, _m(ec["saldo"]))], negrita=True)
    renglon([(40, "Vencido"), (520, _m(ec["vencido"]))])
    y -= 10
    renglon([(40, "Antigüedad del saldo (días desde la fecha del cargo)")], negrita=True)
    for k, texto in TRAMOS_TEXTO.items():
        renglon([(40, texto), (520, _m(ec["antiguedad"][k]))])
    c.showPage()
    c.save()
    return buf.getvalue()
