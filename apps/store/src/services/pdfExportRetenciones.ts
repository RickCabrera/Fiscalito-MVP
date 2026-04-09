/** PDF export para retenciones a terceros */

import jsPDF from 'jspdf';
import autoTable from 'jspdf-autotable';
import type { RetencionesResponse } from './fiscalAgentApi';
import {
  PDF_COLORS, fmtMoney, addFooter,
  DEFAULT_HEAD_STYLES, DEFAULT_BODY_STYLES, DEFAULT_TABLE_STYLES, DEFAULT_ALT_ROW_STYLES,
} from './pdfUtils';

export function exportarRetencionesPDF(data: RetencionesResponse, contribuyente: { nombre: string; rfc: string }): void {
  const doc = new jsPDF({ unit: 'mm', format: 'letter' });
  const pageW = doc.internal.pageSize.getWidth();
  const mL = 20;
  let y = 20;

  doc.setFont('helvetica', 'bold');
  doc.setFontSize(16);
  doc.setTextColor(...PDF_COLORS.dark);
  doc.text('Fiscalito — Retenciones a terceros', mL, y);
  y += 8;

  doc.setFont('helvetica', 'normal');
  doc.setFontSize(10);
  doc.setTextColor(...PDF_COLORS.gray);
  doc.text(`Periodo: ${data.periodo}`, mL, y);
  y += 5;
  if (contribuyente.nombre) doc.text(`Contribuyente: ${contribuyente.nombre}`, mL, y);
  if (contribuyente.rfc) doc.text(`RFC: ${contribuyente.rfc}`, mL + 120, y);
  y += 8;

  doc.setDrawColor(200, 200, 200);
  doc.line(mL, y, pageW - 20, y);
  y += 6;

  const rows = data.terceros.map((r) => [
    r.rfc, r.nombre, fmtMoney(r.total_pagado), fmtMoney(r.isr_retenido), fmtMoney(r.iva_retenido), String(r.cantidad_facturas),
  ]);
  const totalPagado = data.terceros.reduce((s, t) => s + t.total_pagado, 0);
  const totalFacturas = data.terceros.reduce((s, t) => s + t.cantidad_facturas, 0);
  rows.push(['', 'TOTALES', fmtMoney(totalPagado), fmtMoney(data.total_isr_retenido), fmtMoney(data.total_iva_retenido), String(totalFacturas)]);

  autoTable(doc, {
    startY: y, margin: { left: mL, right: 20 },
    head: [['RFC', 'Nombre', 'Total pagado', 'ISR retenido', 'IVA retenido', '#']],
    body: rows,
    theme: 'grid',
    headStyles: { ...DEFAULT_HEAD_STYLES, fontSize: 8 },
    bodyStyles: { ...DEFAULT_BODY_STYLES, fontSize: 8 },
    columnStyles: { 2: { halign: 'right' }, 3: { halign: 'right' }, 4: { halign: 'right' }, 5: { halign: 'center' } },
    alternateRowStyles: DEFAULT_ALT_ROW_STYLES,
    styles: DEFAULT_TABLE_STYLES,
  });

  addFooter(doc);
  doc.save(`Fiscalito_Retenciones_${data.periodo.replace(/\s/g, '_')}.pdf`);
}
