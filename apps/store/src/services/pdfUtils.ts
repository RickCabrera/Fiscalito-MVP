/** Utilidades compartidas para exportacion de PDFs de Fiscalito */

import jsPDF from 'jspdf';

// ── Color tuples ──
type RGBTuple = [number, number, number];

export const PDF_COLORS = {
  dark: [33, 33, 33] as RGBTuple,
  gray: [100, 100, 100] as RGBTuple,
  lightGray: [160, 160, 160] as RGBTuple,
  accent: [55, 80, 100] as RGBTuple,
  altRow: [245, 247, 250] as RGBTuple,
  lineColor: [220, 220, 220] as RGBTuple,
} as const;

// ── Formatters ──

function fmt(n: number): string {
  return n.toLocaleString('es-MX', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export function fmtMoney(n: number): string {
  return `$${fmt(n)}`;
}

export function fmtTasa(n: number): string {
  return `${(n * 100).toFixed(2)}%`;
}

export function fmtFecha(d: string | Date): string {
  const date = typeof d === 'string' ? new Date(d) : d;
  return date.toLocaleDateString('es-MX', {
    day: '2-digit', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit',
  });
}

// ── Shared autoTable style configs ──

export const DEFAULT_HEAD_STYLES = {
  fillColor: [...PDF_COLORS.accent] as [number, number, number],
  textColor: 255 as const,
  fontStyle: 'bold' as const,
  fontSize: 9,
};

export const DEFAULT_BODY_STYLES = {
  fontSize: 9,
  textColor: [40, 40, 40] as [number, number, number],
};

export const DEFAULT_TABLE_STYLES = {
  cellPadding: 3,
  lineColor: [...PDF_COLORS.lineColor] as [number, number, number],
  lineWidth: 0.2,
};

export const DEFAULT_ALT_ROW_STYLES = {
  fillColor: [...PDF_COLORS.altRow] as [number, number, number],
};

// ── Shared footer ──

export function addFooter(doc: jsPDF): void {
  const total = doc.getNumberOfPages();
  const pageW = doc.internal.pageSize.getWidth();
  for (let i = 1; i <= total; i++) {
    doc.setPage(i);
    const h = doc.internal.pageSize.getHeight();
    doc.setFont('helvetica', 'normal');
    doc.setFontSize(7);
    doc.setTextColor(...PDF_COLORS.lightGray);
    doc.text('Estimación generada por Fiscalito. No sustituye asesoría profesional.', 20, h - 10);
    doc.text(`Página ${i}/${total}`, pageW - 20, h - 10, { align: 'right' });
  }
}
