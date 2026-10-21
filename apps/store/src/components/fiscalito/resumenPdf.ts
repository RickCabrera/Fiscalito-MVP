/** PDF del resumen de impuestos (P3-02). Sólo acomoda lo que calculó el backend. */

import jsPDF from 'jspdf';
import autoTable from 'jspdf-autotable';
import type { ResumenImpuestos } from '../../services/impuestosApi';
import {
  PDF_COLORS, addFooter,
  DEFAULT_HEAD_STYLES, DEFAULT_BODY_STYLES, DEFAULT_TABLE_STYLES, DEFAULT_ALT_ROW_STYLES,
} from '../../services/pdfUtils';
import { MARCA_CORTA, PREFIJO_ARCHIVO } from '../../services/marca';

const COLUMNAS = [
  'importe_sistema', 'importe_a_pagar', 'actualizacion', 'recargos', 'subsidio', 'compensaciones', 'total',
] as const;

export function exportarResumenPdf(r: ResumenImpuestos, cliente: string): void {
  const doc = new jsPDF({ unit: 'mm', format: 'letter', orientation: 'landscape' });
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(14);
  doc.setTextColor(...PDF_COLORS.dark);
  doc.text(`${MARCA_CORTA} — Resumen y actualización de impuestos`, 15, 16);
  doc.setFont('helvetica', 'normal');
  doc.setFontSize(9);
  doc.setTextColor(...PDF_COLORS.gray);
  doc.text(`${cliente} · periodo ${String(r.mes).padStart(2, '0')}/${r.anio} · fecha límite ${r.fecha_limite}`
    + ` · fecha de pago ${r.fecha_pago}`, 15, 22);
  autoTable(doc, {
    startY: 27,
    head: [['Concepto', 'Sistema', 'A pagar', 'Actualización', 'Recargos', 'Subsidio', 'Compensaciones', 'Total']],
    body: [
      ...r.renglones.map((x) => [x.concepto, ...COLUMNAS.map((k) => x[k])]),
      ['Total', ...COLUMNAS.map((k) => r.totales[k] ?? '')],
    ],
    headStyles: DEFAULT_HEAD_STYLES,
    bodyStyles: DEFAULT_BODY_STYLES,
    alternateRowStyles: DEFAULT_ALT_ROW_STYLES,
    styles: DEFAULT_TABLE_STYLES,
    columnStyles: Object.fromEntries(COLUMNAS.map((_, i) => [i + 1, { halign: 'right' as const }])),
  });
  const y = (doc as unknown as { lastAutoTable: { finalY: number } }).lastAutoTable.finalY + 8;
  doc.setFontSize(10);
  doc.setTextColor(...PDF_COLORS.dark);
  doc.text(`Total a pagar (ajustado a pesos, Art. 20 CFF): ${r.total_a_pagar_ajustado}`, 15, y);
  doc.setFontSize(8);
  doc.setTextColor(...PDF_COLORS.gray);
  r.notas.forEach((n, i) => doc.text(n, 15, y + 6 + i * 4, { maxWidth: 250 }));
  addFooter(doc);
  doc.save(`${PREFIJO_ARCHIVO}-resumen-impuestos-${r.anio}-${String(r.mes).padStart(2, '0')}.pdf`);
}
