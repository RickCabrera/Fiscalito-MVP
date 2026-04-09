/** PDF export para estado de cuenta fiscal */

import jsPDF from 'jspdf';
import type { EstadoCuentaResponse } from './fiscalAgentApi';
import { PDF_COLORS, fmtMoney, addFooter } from './pdfUtils';

export function exportarEstadoCuentaPDF(data: EstadoCuentaResponse, contribuyente: { nombre: string; rfc: string }): void {
  const doc = new jsPDF({ unit: 'mm', format: 'letter' });
  const pageW = doc.internal.pageSize.getWidth();
  const mL = 20;
  const cW = pageW - 40;
  let y = 20;

  const { dark, gray, accent, lightGray } = PDF_COLORS;

  doc.setFont('helvetica', 'bold');
  doc.setFontSize(16);
  doc.setTextColor(...dark);
  doc.text('Fiscalito — Estado de cuenta fiscal', mL, y);
  y += 8;

  doc.setFont('helvetica', 'normal');
  doc.setFontSize(10);
  doc.setTextColor(...gray);
  doc.text(`Año: ${data.year}`, mL, y);
  y += 5;
  if (contribuyente.nombre) doc.text(`Contribuyente: ${contribuyente.nombre}`, mL, y);
  if (contribuyente.rfc) doc.text(`RFC: ${contribuyente.rfc}`, mL + 120, y);
  y += 8;

  doc.setDrawColor(200, 200, 200);
  doc.line(mL, y, pageW - 20, y);
  y += 10;

  // Section helper
  const section = (label: string, value: string, sub?: string) => {
    doc.setFont('helvetica', 'normal');
    doc.setFontSize(8);
    doc.setTextColor(...gray);
    doc.text(label, mL, y);
    doc.setFont('helvetica', 'bold');
    doc.setFontSize(12);
    doc.setTextColor(...dark);
    doc.text(value, mL, y + 6);
    if (sub) {
      doc.setFont('helvetica', 'normal');
      doc.setFontSize(8);
      doc.setTextColor(...lightGray);
      doc.text(sub, mL, y + 12);
    }
    y += sub ? 18 : 14;
  };

  section('Ingresos acumulados', fmtMoney(data.ingresos_acumulados), `Proyección anual: ${fmtMoney(data.proyeccion_ingresos_anuales)}`);
  section('Egresos acumulados', fmtMoney(data.egresos_acumulados), `Proporción gastos/ingresos: ${data.proporcion_gastos_ingresos.toFixed(1)}%`);

  y += 2;
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(10);
  doc.setTextColor(...accent);
  doc.text('ISR ANUAL', mL, y);
  y += 6;

  const isrItems = [
    ['ISR anual estimado', fmtMoney(data.isr_anual_estimado)],
    ['ISR retenido acumulado', fmtMoney(data.isr_retenido_acumulado)],
    ['ISR faltante', data.isr_faltante <= 0 ? `${fmtMoney(Math.abs(data.isr_faltante))} a favor` : fmtMoney(data.isr_faltante)],
  ];
  for (const [label, value] of isrItems) {
    doc.setFont('helvetica', 'normal');
    doc.setFontSize(9);
    doc.setTextColor(...gray);
    doc.text(label, mL + 4, y);
    doc.setFont('helvetica', 'bold');
    doc.text(value, mL + cW, y, { align: 'right' });
    y += 6;
  }
  y += 6;

  const ivaNeto = data.iva_cobrado_acumulado - data.iva_pagado_acumulado - data.iva_retenido_acumulado;
  section('IVA neto acumulado', fmtMoney(ivaNeto), `Cobrado: ${fmtMoney(data.iva_cobrado_acumulado)} · Pagado: ${fmtMoney(data.iva_pagado_acumulado)}`);
  section('Mes con más ingresos', data.mes_mayor_ingreso);
  section('Mes con más gastos', data.mes_mayor_gasto);

  // Advertencias
  if (data.advertencias.length > 0) {
    y += 4;
    doc.setFont('helvetica', 'bold');
    doc.setFontSize(10);
    doc.setTextColor(180, 120, 40);
    doc.text('ADVERTENCIAS', mL, y);
    y += 6;
    doc.setFont('helvetica', 'normal');
    doc.setFontSize(8.5);
    doc.setTextColor(...gray);
    for (const adv of data.advertencias) {
      if (y > 250) { doc.addPage(); y = 20; }
      const lines = doc.splitTextToSize(`•  ${adv}`, cW - 4);
      for (const line of lines) { doc.text(line, mL + 2, y); y += 4; }
      y += 1;
    }
  }

  addFooter(doc);
  doc.save(`Fiscalito_EstadoCuenta_${data.year}.pdf`);
}
