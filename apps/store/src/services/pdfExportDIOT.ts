/** PDF export para DIOT */

import jsPDF from 'jspdf';
import autoTable from 'jspdf-autotable';
import type { DIOTResponse } from './fiscalAgentApi';
import {
  PDF_COLORS, fmtMoney, addFooter,
  DEFAULT_HEAD_STYLES, DEFAULT_BODY_STYLES, DEFAULT_TABLE_STYLES, DEFAULT_ALT_ROW_STYLES,
} from './pdfUtils';

export function exportarDIOTPDF(data: DIOTResponse, contribuyente: { nombre: string; rfc: string }): void {
  const doc = new jsPDF({ unit: 'mm', format: 'letter' });
  const pageW = doc.internal.pageSize.getWidth();
  const mL = 20;
  let y = 20;

  doc.setFont('helvetica', 'bold');
  doc.setFontSize(16);
  doc.setTextColor(...PDF_COLORS.dark);
  doc.text('Fiscalito — DIOT', mL, y);
  y += 8;

  doc.setFont('helvetica', 'normal');
  doc.setFontSize(10);
  doc.setTextColor(...PDF_COLORS.gray);
  doc.text(`Periodo: ${data.periodo}`, mL, y);
  y += 5;
  if (contribuyente.nombre) doc.text(`Contribuyente: ${contribuyente.nombre}`, mL, y);
  if (contribuyente.rfc) { doc.text(`RFC: ${contribuyente.rfc}`, mL + 120, y); }
  y += 8;

  doc.setDrawColor(200, 200, 200);
  doc.line(mL, y, pageW - 20, y);
  y += 6;

  const rows = data.proveedores.map((p) => [
    p.rfc, p.nombre, fmtMoney(p.total_operaciones), fmtMoney(p.iva_pagado), String(p.cantidad_facturas),
  ]);
  rows.push(['', 'TOTALES', fmtMoney(data.total_operaciones), fmtMoney(data.total_iva), String(data.total_proveedores)]);

  autoTable(doc, {
    startY: y, margin: { left: mL, right: 20 },
    head: [['RFC Proveedor', 'Nombre', 'Total operaciones', 'IVA pagado', '# Facturas']],
    body: rows,
    theme: 'grid',
    headStyles: { ...DEFAULT_HEAD_STYLES, fontSize: 8 },
    bodyStyles: { ...DEFAULT_BODY_STYLES, fontSize: 8 },
    columnStyles: { 2: { halign: 'right' }, 3: { halign: 'right' }, 4: { halign: 'center' } },
    alternateRowStyles: DEFAULT_ALT_ROW_STYLES,
    styles: DEFAULT_TABLE_STYLES,
  });

  addFooter(doc);
  doc.save(`Fiscalito_DIOT_${data.periodo.replace(/\s/g, '_')}.pdf`);
}
