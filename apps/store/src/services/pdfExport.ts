/** Servicio para exportar pre-declaraciones como PDF profesional */

import jsPDF from 'jspdf';
import autoTable from 'jspdf-autotable';
import {
  PDF_COLORS, fmtMoney, fmtTasa, fmtFecha,
  DEFAULT_HEAD_STYLES, DEFAULT_BODY_STYLES, DEFAULT_TABLE_STYLES, DEFAULT_ALT_ROW_STYLES,
} from './pdfUtils';

interface DesgloseData {
  total_ingresos_facturados: number;
  total_ingresos_gravados: number;
  total_deducciones_autorizadas?: number;
  total_egresos?: number;
  base_isr: number;
  tasa_isr: number;
  isr_causado: number;
  isr_retenido?: number;
  isr_a_pagar: number;
  iva_trasladado_cobrado?: number;
  iva_trasladado_pagado?: number;
  iva_retenido?: number;
  iva_a_pagar: number;
  total_a_pagar: number;
}

export interface ExportPDFData {
  periodo: string;
  tipo: string;
  regimen: string;
  desglose: DesgloseData;
  explicacion: string | null;
  advertencias: string[];
  recomendaciones: string[];
  contribuyente: { nombre: string; rfc: string };
  fechaCalculo: Date;
}

function sanitizeFilename(s: string): string {
  return s.replace(/[^a-zA-Z0-9_-]/g, '_');
}

export function exportarDeclaracionPDF(data: ExportPDFData): void {
  const { periodo, tipo, regimen, desglose, explicacion, advertencias, recomendaciones, contribuyente, fechaCalculo } = data;
  const doc = new jsPDF({ unit: 'mm', format: 'letter' });

  const pageW = doc.internal.pageSize.getWidth();
  const marginL = 20;
  const marginR = 20;
  const contentW = pageW - marginL - marginR;
  let y = 20;

  const { dark, gray, lightGray, accent } = PDF_COLORS;

  // ── Header ──
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(18);
  doc.setTextColor(...dark);
  doc.text('Fiscalito', marginL, y);
  doc.setFont('helvetica', 'normal');
  doc.setFontSize(18);
  doc.setTextColor(...lightGray);
  doc.text(' — Pre-declaración fiscal', marginL + doc.getTextWidth('Fiscalito'), y);
  y += 10;

  doc.setFontSize(11);
  doc.setTextColor(...gray);
  doc.text(`${tipo.charAt(0).toUpperCase() + tipo.slice(1)} · ${periodo} · ${regimen}`, marginL, y);
  y += 6;
  doc.setFontSize(9);
  doc.text(`Fecha de cálculo: ${fmtFecha(fechaCalculo)}`, marginL, y);
  y += 6;

  // Contribuyente
  if (contribuyente.nombre || contribuyente.rfc) {
    doc.setFontSize(9);
    doc.setTextColor(...gray);
    const parts: string[] = [];
    if (contribuyente.nombre) parts.push(`Contribuyente: ${contribuyente.nombre}`);
    if (contribuyente.rfc) parts.push(`RFC: ${contribuyente.rfc}`);
    doc.text(parts.join('   |   '), marginL, y);
    y += 4;
  }

  // Separator
  y += 2;
  doc.setDrawColor(200, 200, 200);
  doc.setLineWidth(0.3);
  doc.line(marginL, y, pageW - marginR, y);
  y += 8;

  // ── Seccion 1 — Resumen ──
  const totalAPagar = desglose.total_a_pagar;
  const esAFavor = totalAPagar <= 0;

  doc.setFont('helvetica', 'bold');
  doc.setFontSize(10);
  doc.setTextColor(...dark);
  doc.text('TOTAL ESTIMADO', marginL, y);
  y += 8;

  doc.setFontSize(22);
  if (esAFavor) {
    doc.setTextColor(39, 174, 96);
    doc.text(`${fmtMoney(Math.abs(totalAPagar))} a favor`, marginL, y);
  } else {
    doc.setTextColor(...dark);
    doc.text(fmtMoney(totalAPagar), marginL, y);
  }
  y += 5;

  doc.setFontSize(8);
  doc.setTextColor(...lightGray);
  doc.text(esAFavor ? 'Saldo a favor estimado (ISR + IVA)' : 'Total estimado a pagar (ISR + IVA)', marginL, y);
  y += 10;

  // ── Seccion 2 — Desglose ISR (tabla) ──
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(10);
  doc.setTextColor(...accent);
  doc.text('DESGLOSE ISR', marginL, y);
  y += 2;

  const isrRows: string[][] = [
    ['Ingresos facturados', fmtMoney(desglose.total_ingresos_facturados)],
    ['Ingresos gravados', fmtMoney(desglose.total_ingresos_gravados)],
    ['Deducciones autorizadas', fmtMoney(desglose.total_deducciones_autorizadas ?? 0)],
    ['Base ISR', fmtMoney(desglose.base_isr)],
    ['Tasa ISR', fmtTasa(desglose.tasa_isr)],
    ['ISR causado', fmtMoney(desglose.isr_causado)],
    ['ISR retenido', fmtMoney(desglose.isr_retenido ?? 0)],
    ['ISR a pagar', fmtMoney(desglose.isr_a_pagar)],
  ];

  autoTable(doc, {
    startY: y,
    margin: { left: marginL, right: marginR },
    head: [['Concepto', 'Monto']],
    body: isrRows,
    theme: 'grid',
    headStyles: DEFAULT_HEAD_STYLES,
    bodyStyles: DEFAULT_BODY_STYLES,
    columnStyles: {
      0: { cellWidth: contentW * 0.6 },
      1: { cellWidth: contentW * 0.4, halign: 'right', fontStyle: 'bold' },
    },
    alternateRowStyles: DEFAULT_ALT_ROW_STYLES,
    styles: DEFAULT_TABLE_STYLES,
  });

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  y = (doc as any).lastAutoTable?.finalY ?? y + 50;
  y += 8;

  // ── Seccion 3 — Desglose IVA ──
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(10);
  doc.setTextColor(...accent);
  doc.text('DESGLOSE IVA', marginL, y);
  y += 2;

  const ivaRows: string[][] = [
    ['IVA cobrado', fmtMoney(desglose.iva_trasladado_cobrado ?? 0)],
    ['IVA pagado (acreditable)', fmtMoney(desglose.iva_trasladado_pagado ?? 0)],
    ['IVA retenido', fmtMoney(desglose.iva_retenido ?? 0)],
    ['IVA a pagar', fmtMoney(desglose.iva_a_pagar)],
  ];

  autoTable(doc, {
    startY: y,
    margin: { left: marginL, right: marginR },
    head: [['Concepto', 'Monto']],
    body: ivaRows,
    theme: 'grid',
    headStyles: DEFAULT_HEAD_STYLES,
    bodyStyles: DEFAULT_BODY_STYLES,
    columnStyles: {
      0: { cellWidth: contentW * 0.6 },
      1: { cellWidth: contentW * 0.4, halign: 'right', fontStyle: 'bold' },
    },
    alternateRowStyles: DEFAULT_ALT_ROW_STYLES,
    styles: DEFAULT_TABLE_STYLES,
  });

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  y = (doc as any).lastAutoTable?.finalY ?? y + 30;
  y += 8;

  // ── Seccion 4 — Explicacion ──
  if (explicacion) {
    if (y > 230) { doc.addPage(); y = 20; }
    doc.setFont('helvetica', 'bold');
    doc.setFontSize(10);
    doc.setTextColor(...accent);
    doc.text('EXPLICACIÓN', marginL, y);
    y += 6;

    doc.setFont('helvetica', 'normal');
    doc.setFontSize(8.5);
    doc.setTextColor(...gray);
    const lines = doc.splitTextToSize(explicacion, contentW);
    for (const line of lines) {
      if (y > 255) { doc.addPage(); y = 20; }
      doc.text(line, marginL, y);
      y += 4;
    }
    y += 4;
  }

  // ── Seccion 5 — Advertencias ──
  if (advertencias.length > 0) {
    if (y > 240) { doc.addPage(); y = 20; }
    doc.setFont('helvetica', 'bold');
    doc.setFontSize(10);
    doc.setTextColor(180, 120, 40);
    doc.text('ADVERTENCIAS', marginL, y);
    y += 6;

    doc.setFont('helvetica', 'normal');
    doc.setFontSize(8.5);
    doc.setTextColor(...gray);
    for (const adv of advertencias) {
      if (y > 255) { doc.addPage(); y = 20; }
      const wrapped = doc.splitTextToSize(`•  ${adv}`, contentW - 4);
      for (const wl of wrapped) { doc.text(wl, marginL + 2, y); y += 4; }
      y += 1;
    }
    y += 4;
  }

  // ── Seccion 5b — Recomendaciones ──
  if (recomendaciones.length > 0) {
    if (y > 240) { doc.addPage(); y = 20; }
    doc.setFont('helvetica', 'bold');
    doc.setFontSize(10);
    doc.setTextColor(39, 120, 120);
    doc.text('RECOMENDACIONES', marginL, y);
    y += 6;

    doc.setFont('helvetica', 'normal');
    doc.setFontSize(8.5);
    doc.setTextColor(...gray);
    for (const rec of recomendaciones) {
      if (y > 255) { doc.addPage(); y = 20; }
      const wrapped = doc.splitTextToSize(`•  ${rec}`, contentW - 4);
      for (const wl of wrapped) { doc.text(wl, marginL + 2, y); y += 4; }
      y += 1;
    }
  }

  // ── Pie de pagina (version extendida con disclaimer completo) ──
  const totalPages = doc.getNumberOfPages();
  for (let i = 1; i <= totalPages; i++) {
    doc.setPage(i);
    const pageH = doc.internal.pageSize.getHeight();

    doc.setDrawColor(200, 200, 200);
    doc.setLineWidth(0.2);
    doc.line(marginL, pageH - 18, pageW - marginR, pageH - 18);

    doc.setFont('helvetica', 'normal');
    doc.setFontSize(7);
    doc.setTextColor(...lightGray);
    doc.text(
      'Este documento es una estimación generada por Fiscalito. No sustituye la asesoría de un contador público certificado.',
      marginL, pageH - 14,
    );
    doc.text(
      'Verifica los montos en el portal del SAT antes de presentar tu declaración.',
      marginL, pageH - 10,
    );
    doc.text(`Página ${i} de ${totalPages}`, pageW - marginR, pageH - 10, { align: 'right' });
  }

  // ── Descargar ──
  const fechaStr = fechaCalculo.toISOString().substring(0, 10);
  const filename = `Fiscalito_PreDeclaracion_${sanitizeFilename(periodo)}_${fechaStr}.pdf`;
  doc.save(filename);
}
