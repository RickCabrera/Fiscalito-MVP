"""
Los documentos que se le mandan al trabajador (P4-13).

- **Timbrado**: si el recibo tiene `uuid_cfdi` y el CFDI está en la bóveda del cliente
  (`comprobantes`, P0-03), se adjunta su XML tal cual y, si el comprobante declara
  `datos["ruta_pdf"]` (o el recibo trae `ruta_pdf`), su PDF. Es el punto de enganche con
  P4-11 (timbrado): este módulo no timbra ni arma el PDF fiscal.
- **Sin timbrar**: el PDF del recibo guardado, marcado en grande "SIN TIMBRAR — no es un
  CFDI". No hay XML que mandar: el pre-CFDI sin timbre no es un comprobante.

Nada se recalcula: el PDF imprime las partidas e importes guardados en `nomina_recibos`.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integraciones.almacenamiento import obtener_almacenamiento
from app.modelos.cfdi import Comprobante
from app.modelos.nomina import NominaPeriodo, ReciboNomina
from app.modelos.nucleo import Cliente


@dataclass(frozen=True)
class Documentos:
    pdf: bytes | None
    xml: bytes | None
    timbrado: bool
    nombre_base: str


def _importe(partida: dict[str, Any]) -> Decimal:
    if partida.get("importe") not in (None, ""):
        return Decimal(str(partida["importe"]))
    return Decimal(str(partida.get("gravado") or 0)) + Decimal(str(partida.get("exento") or 0))


def pdf_sin_timbrar(cliente: Cliente, periodo: NominaPeriodo, recibo: ReciboNomina) -> bytes:
    """Una página con las partidas guardadas y la leyenda SIN TIMBRAR."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=LETTER)
    c.setTitle(f"Recibo de nomina {recibo.empleado_no}")
    _, alto = LETTER
    y = alto - 50
    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, y, "Recibo de nómina")
    c.setFillColorRGB(0.75, 0.1, 0.1)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, y - 18, "SIN TIMBRAR — no es un CFDI ni tiene validez fiscal")
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica", 10)
    y -= 44
    for linea in (
        f"Patrón: {cliente.nombre} {('RFC ' + cliente.rfc) if cliente.rfc else ''}",
        f"Trabajador: {recibo.nombre} (núm. {recibo.empleado_no})",
        f"Periodo: {periodo.inicio:%d/%m/%Y} al {periodo.fin:%d/%m/%Y} · pago "
        f"{periodo.fecha_pago:%d/%m/%Y}",
    ):
        c.drawString(40, y, linea)
        y -= 14
    for titulo, partidas in (("Percepciones", recibo.percepciones),
                             ("Deducciones", recibo.deducciones),
                             ("Otros pagos", recibo.otros_pagos)):
        if not partidas:
            continue
        y -= 8
        c.setFont("Helvetica-Bold", 10)
        c.drawString(40, y, titulo)
        c.setFont("Helvetica", 9)
        y -= 13
        for p in partidas:
            c.drawString(50, y, f"{p.get('clave', '')} {p.get('concepto', '')}"[:80])
            c.drawRightString(560, y, f"{_importe(p):,.2f}")
            y -= 12
            if y < 80:
                c.showPage()
                y = alto - 50
    y -= 10
    c.setFont("Helvetica-Bold", 10)
    for etiqueta, valor in (("Total percepciones", recibo.total_percepciones),
                            ("Total deducciones", recibo.total_deducciones),
                            ("Neto a pagar", recibo.neto)):
        c.drawString(330, y, etiqueta)
        c.drawRightString(560, y, f"{valor:,.2f}")
        y -= 14
    c.save()
    return buf.getvalue()


def documentos_del_recibo(db: Session, cliente: Cliente, periodo: NominaPeriodo,
                          recibo: ReciboNomina) -> Documentos:
    base = f"recibo_{periodo.inicio:%Y%m%d}_{recibo.empleado_no}"
    if recibo.uuid_cfdi:
        cfdi = db.scalar(select(Comprobante).where(
            Comprobante.cliente_id == cliente.id,
            Comprobante.uuid == recibo.uuid_cfdi.upper()))
        if cfdi is not None:
            almacen = obtener_almacenamiento()
            xml = almacen.leer(cfdi.ruta_xml)
            ruta_pdf = (cfdi.datos or {}).get("ruta_pdf") or getattr(recibo, "ruta_pdf", None)
            # Sin PDF fiscal todavía: sólo el XML. Mandar el PDF "SIN TIMBRAR" junto a un
            # CFDI timbrado diría dos cosas distintas del mismo recibo.
            pdf = almacen.leer(ruta_pdf) if ruta_pdf else None
            return Documentos(pdf=pdf, xml=xml, timbrado=True, nombre_base=base)
    return Documentos(pdf=pdf_sin_timbrar(cliente, periodo, recibo), xml=None,
                      timbrado=False, nombre_base=f"{base}_SIN_TIMBRAR")
