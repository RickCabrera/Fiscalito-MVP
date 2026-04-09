/** PDF export para multi-periodo */

import jsPDF from 'jspdf';
import autoTable from 'jspdf-autotable';
import type { MultiPeriodoResponse } from './fiscalAgentApi';
import {
  PDF_COLORS, fmtMoney, addFooter,
  DEFAULT_HEAD_STYLES, DEFAULT_BODY_STYLES, DEFAULT_TABLE_STYLES, DEFAULT_ALT_ROW_STYLES,
} from './pdfUtils';

export function exportarMultiPeriodoPDF(data: MultiPeriodoResponse, contribuyente: { nombre: string; rfc: string }): void {
  const doc = new jsPDF({ unit: 'mm', format: 'letter' });
  const pageW = doc.internal.pageSize.getWidth();
  const mL = 20;
  let y = 20;

  doc.setFont('helvetica', 'bold');
  doc.setFontSize(16);
  doc.setTextColor(...PDF_COLORS.dark);
  doc.text('Fiscalito — Resumen multi-periodo', mL, y);
  y += 8;

  doc.setFont('helvetica', 'normal');
  doc.setFontSize(10);
  doc.setTextColor(...PDF_COLORS.gray);
  doc.text(`Año: ${data.year}`, mL, y);
  y += 5;
  if (contribuyente.nombre) doc.text(`Contribuyente: ${contribuyente.nombre}`, mL, y);
  if (contribuyente.rfc) doc.text(`RFC: ${contribuyente.rfc}`, mL + 120, y);
  y += 8;

  doc.setDrawColor(200, 200, 200);
  doc.line(mL, y, pageW - 20, y);
  y += 8;

  // Resumen
  const a = data.acumulado;
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(9);
  doc.setTextColor(...PDF_COLORS.accent);
  doc.text(`Total ISR: ${fmtMoney(a.total_isr_pagado)}    |    Total IVA: ${fmtMoney(a.total_iva_pagado)}    |    Total: ${fmtMoney(a.total_general_pagado)}    |    Promedio: ${fmtMoney(a.promedio_mensual)}`, mL, y);
  y += 8;

  const rows = data.resultados.map((r) => [
    r.periodo, fmtMoney(r.desglose.isr_a_pagar), fmtMoney(r.desglose.iva_a_pagar), fmtMoney(r.desglose.total_a_pagar), String(r.desglose.cantidad_facturas_ingreso ?? 0),
  ]);

  autoTable(doc, {
    startY: y, margin: { left: mL, right: 20 },
    head: [['Periodo', 'ISR', 'IVA', 'Total', 'Facturas']],
    body: rows,
    theme: 'grid',
    headStyles: { ...DEFAULT_HEAD_STYLES, fontSize: 8 },
    bodyStyles: { ...DEFAULT_BODY_STYLES, fontSize: 8 },
    columnStyles: { 1: { halign: 'right' }, 2: { halign: 'right' }, 3: { halign: 'right' }, 4: { halign: 'center' } },
    alternateRowStyles: DEFAULT_ALT_ROW_STYLES,
    styles: DEFAULT_TABLE_STYLES,
  });

  addFooter(doc);
  doc.save(`Fiscalito_MultiPeriodo_${data.year}.pdf`);
}
