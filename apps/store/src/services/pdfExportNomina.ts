/** PDF export de la nómina del periodo (D-07). DEMO: se borra en F2. */

import jsPDF from 'jspdf';
import autoTable from 'jspdf-autotable';
import type { NominaPeriodo, ReciboNomina } from './nominaDemoApi';
import {
  PDF_COLORS, fmtMoney, addFooter,
  DEFAULT_HEAD_STYLES, DEFAULT_BODY_STYLES, DEFAULT_TABLE_STYLES, DEFAULT_ALT_ROW_STYLES,
} from './pdfUtils';

function isr(recibo: ReciboNomina): number {
  return recibo.deducciones
    .filter((d) => d.tipo === '002')
    .reduce((suma, d) => suma + Number(d.importe), 0);
}

/**
 * Exporta la nómina del periodo.
 *
 * La banda "DATOS DE DEMOSTRACIÓN" se pinta **si y sólo si** la plantilla salió
 * del servidor de demo. Un PDF con nueve nombres y nueve sueldos que circule
 * sin esa banda parece la nómina de un cliente real; y ponérsela a una nómina
 * que sí es real sería igual de falso.
 */
export function exportarNominaPDF(data: NominaPeriodo): void {
  const doc = new jsPDF({ unit: 'mm', format: 'letter' });
  const pageW = doc.internal.pageSize.getWidth();
  const mL = 20;
  let y = 20;

  doc.setFont('helvetica', 'bold');
  doc.setFontSize(16);
  doc.setTextColor(...PDF_COLORS.dark);
  doc.text('Fiscalito — Nómina del periodo', mL, y);
  y += 8;

  if (data.origen_plantilla === 'demo') {
    doc.setFillColor(...PDF_COLORS.demo);
    doc.rect(mL, y - 4, pageW - mL - 20, 7, 'F');
    doc.setTextColor(...PDF_COLORS.white);
    doc.setFontSize(9);
    doc.text('DATOS DE DEMOSTRACIÓN — identidades sintéticas, no es la nómina de un cliente', mL + 2, y + 1);
    y += 10;
  }

  doc.setFont('helvetica', 'normal');
  doc.setFontSize(10);
  doc.setTextColor(...PDF_COLORS.gray);
  doc.text(`Periodo: ${data.periodo.inicio} a ${data.periodo.fin}`, mL, y);
  y += 5;
  doc.text(`Fecha de pago: ${data.fecha_pago_efectiva}`, mL, y);
  y += 8;

  doc.setDrawColor(200, 200, 200);
  doc.line(mL, y, pageW - 20, y);
  y += 6;

  autoTable(doc, {
    startY: y, margin: { left: mL, right: 20 },
    head: [['Empleado', 'SBC', 'Días', 'Percepciones', 'ISR', 'Cuota obrera', 'Neto']],
    body: data.recibos.map((r) => [
      `${r.nombre} (${r.empleado_no})`,
      fmtMoney(Number(r.sbc)),
      String(r.dias_pagados),
      fmtMoney(Number(r.total_percepciones)),
      fmtMoney(isr(r)),
      fmtMoney(Number(r.cuota_obrera)),
      fmtMoney(Number(r.neto)),
    ]),
    theme: 'grid',
    headStyles: { ...DEFAULT_HEAD_STYLES, fontSize: 8 },
    bodyStyles: { ...DEFAULT_BODY_STYLES, fontSize: 8 },
    columnStyles: { 1: { halign: 'right' }, 2: { halign: 'center' }, 3: { halign: 'right' }, 4: { halign: 'right' }, 5: { halign: 'right' }, 6: { halign: 'right' } },
    alternateRowStyles: DEFAULT_ALT_ROW_STYLES,
    styles: DEFAULT_TABLE_STYLES,
  });

  const ramos = [
    ...Object.entries(data.porcion_mensual.por_ramo).map(([c, m]) => ['Mensual', c, fmtMoney(Number(m))]),
    ...Object.entries(data.porcion_bimestral.por_ramo).map(([c, m]) => ['Bimestral', c, fmtMoney(Number(m))]),
  ];

  autoTable(doc, {
    margin: { left: mL, right: 20 },
    head: [['Entero', 'Ramo', 'Devengado en el periodo']],
    body: ramos,
    theme: 'grid',
    headStyles: { ...DEFAULT_HEAD_STYLES, fontSize: 8 },
    bodyStyles: { ...DEFAULT_BODY_STYLES, fontSize: 8 },
    columnStyles: { 2: { halign: 'right' } },
    alternateRowStyles: DEFAULT_ALT_ROW_STYLES,
    styles: DEFAULT_TABLE_STYLES,
  });

  // Las advertencias vienen del backend y se imprimen tal cual: ahí va la nota
  // de que las cuotas son la porción del periodo y no el entero del Art. 39.
  // Un PDF sin ellas invita a pagarle al IMSS el número equivocado.
  let yA = (doc as unknown as { lastAutoTable: { finalY: number } }).lastAutoTable.finalY + 8;
  doc.setFontSize(8);
  doc.setTextColor(...PDF_COLORS.gray);
  for (const aviso of data.advertencias) {
    for (const linea of doc.splitTextToSize(aviso, pageW - mL - 20) as string[]) {
      doc.text(linea, mL, yA);
      yA += 4;
    }
    yA += 2;
  }

  addFooter(doc);
  doc.save(`Fiscalito_Nomina_${data.periodo.inicio}_${data.periodo.fin}.pdf`);
}
