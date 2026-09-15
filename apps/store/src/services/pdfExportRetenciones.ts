/** PDF export para retenciones a terceros */

import jsPDF from 'jspdf';
import autoTable from 'jspdf-autotable';
import type { RetencionesResponse, RetencionTercero } from './fiscalAgentApi';
import {
  PDF_COLORS, fmtMoney, addFooter,
  DEFAULT_HEAD_STYLES, DEFAULT_BODY_STYLES, DEFAULT_TABLE_STYLES, DEFAULT_ALT_ROW_STYLES,
} from './pdfUtils';
import { MARCA_CORTA, PREFIJO_ARCHIVO } from './marca';

export function exportarRetencionesPDF(data: RetencionesResponse, contribuyente: { nombre: string; rfc: string }): void {
  const doc = new jsPDF({ unit: 'mm', format: 'letter' });
  const pageW = doc.internal.pageSize.getWidth();
  const mL = 20;
  let y = 20;

  doc.setFont('helvetica', 'bold');
  doc.setFontSize(16);
  doc.setTextColor(...PDF_COLORS.dark);
  doc.text(`${MARCA_CORTA} — Retenciones a terceros`, mL, y);
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
  doc.save(`${PREFIJO_ARCHIVO}_Retenciones_${data.periodo.replace(/\s/g, '_')}.pdf`);
}

// ── Constancia individual por tercero (T5) ──

/**
 * ESTO NO ES UN CFDI DE RETENCIONES, Y EL PDF LO DICE EN GRANDE
 * -------------------------------------------------------------
 * La constancia que el SAT reconoce es el **CFDI de Retenciones e Información
 * de Pagos**, timbrado por un PAC. Este documento es un resumen informativo
 * armado con los XML que el usuario subió: sirve para que el tercero sepa qué
 * se le retuvo y para cuadrar contra su propia contabilidad, y no sustituye al
 * comprobante timbrado.
 *
 * Decirlo sólo en el pie sería insuficiente: el pie de este repo dice
 * "Estimación generada por…", que es una frase genérica, y el documento que
 * alguien imprime y le entrega a un proveedor necesita la advertencia arriba,
 * donde se lee antes que los importes. Por eso la banda `demo` va bajo el
 * título y no al final. El timbrado con PAC está fuera de alcance por
 * `CLAUDE.md`.
 */
const AVISO_NO_TIMBRADA =
  'Documento informativo. No es un CFDI de Retenciones e Informacion de Pagos ' +
  'timbrado por un PAC y no lo sustituye.';

/**
 * El nombre del archivo, saneado.
 *
 * El criterio de la tarea pide literalmente `constancia-{RFC}-{periodo}.pdf`, y
 * el periodo llega del backend como `"Enero 2025"` — con espacio. Se cambia por
 * guion en vez de quitarlo: `constancia-XAXX010101000-Enero2025.pdf` pierde el
 * corte entre mes y año, y estos archivos se ordenan a ojo en una carpeta.
 */
function nombreConstancia(rfc: string, periodo: string): string {
  const limpio = (s: string) => s.trim().replace(/\s+/g, '-').replace(/[^A-Za-z0-9-]/g, '');
  return `constancia-${limpio(rfc.toUpperCase())}-${limpio(periodo)}.pdf`;
}

/** Un bloque "RETENEDOR" / "RETENIDO": etiqueta, nombre y RFC. */
function bloqueParte(
  doc: jsPDF,
  etiqueta: string,
  parte: { nombre: string; rfc: string },
  x: number,
  y: number,
): void {
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(8);
  doc.setTextColor(...PDF_COLORS.gray);
  doc.text(etiqueta, x, y);

  doc.setFont('helvetica', 'normal');
  doc.setFontSize(10);
  doc.setTextColor(...PDF_COLORS.dark);
  // Sin nombre capturado no se inventa uno: el RFC solo ya identifica a la
  // parte, y un "—" dice que el dato falta en vez de fingir que no hacia falta.
  doc.text(parte.nombre || '—', x, y + 5);
  doc.setFont('courier', 'normal');
  doc.setFontSize(9);
  doc.text(parte.rfc || '—', x, y + 10);
}

/**
 * Una constancia por RFC de tercero.
 *
 * Los importes salen **tal cual** de `RetencionTercero`, que es lo que devolvio
 * `POST /api/v1/retenciones`. Aqui no se suma, no se prorratea y no se
 * reconstruye nada: el desglose por factura no viaja en la respuesta, asi que
 * la constancia dice el acumulado del periodo y cuantos comprobantes lo
 * componen, que es exactamente lo que el backend sabe.
 */
export function exportConstanciaRetencion(
  tercero: RetencionTercero,
  retenedor: { nombre: string; rfc: string },
  periodo: string,
): void {
  const doc = new jsPDF({ unit: 'mm', format: 'letter' });
  const pageW = doc.internal.pageSize.getWidth();
  const mL = 20;
  let y = 20;

  doc.setFont('helvetica', 'bold');
  doc.setFontSize(16);
  doc.setTextColor(...PDF_COLORS.dark);
  doc.text('Constancia de retenciones', mL, y);
  y += 7;

  doc.setFont('helvetica', 'normal');
  doc.setFontSize(10);
  doc.setTextColor(...PDF_COLORS.gray);
  doc.text(`Periodo: ${periodo}`, mL, y);
  y += 7;

  // Banda de advertencia, antes de cualquier importe.
  doc.setFillColor(...PDF_COLORS.demo);
  doc.rect(mL, y - 4, pageW - mL - 20, 9, 'F');
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(8);
  doc.setTextColor(...PDF_COLORS.white);
  doc.text(AVISO_NO_TIMBRADA, mL + 3, y + 1.5, { maxWidth: pageW - mL - 26 });
  y += 14;

  bloqueParte(doc, 'RETENEDOR', retenedor, mL, y);
  bloqueParte(doc, 'RETENIDO', { nombre: tercero.nombre, rfc: tercero.rfc }, mL + 90, y);
  y += 18;

  doc.setDrawColor(200, 200, 200);
  doc.line(mL, y, pageW - 20, y);
  y += 6;

  autoTable(doc, {
    startY: y,
    margin: { left: mL, right: 20 },
    head: [['Concepto', 'Importe']],
    body: [
      ['Total pagado en el periodo', fmtMoney(tercero.total_pagado)],
      ['ISR retenido', fmtMoney(tercero.isr_retenido)],
      ['IVA retenido', fmtMoney(tercero.iva_retenido)],
      ['Comprobantes que lo integran', String(tercero.cantidad_facturas)],
    ],
    theme: 'grid',
    headStyles: DEFAULT_HEAD_STYLES,
    bodyStyles: DEFAULT_BODY_STYLES,
    columnStyles: { 1: { halign: 'right' } },
    alternateRowStyles: DEFAULT_ALT_ROW_STYLES,
    styles: DEFAULT_TABLE_STYLES,
  });

  addFooter(doc);
  doc.save(nombreConstancia(tercero.rfc, periodo));
}

/**
 * Todas las constancias del periodo, una descarga por tercero.
 *
 * SON N ARCHIVOS Y NO UN PDF DE N PAGINAS, A PROPOSITO
 * ----------------------------------------------------
 * Una constancia se le entrega a **un** proveedor. Un PDF con las de todos
 * obligaria a recortarlo antes de mandar cada una, y el primer descuido manda a
 * un proveedor los importes de los demas.
 *
 * El respiro entre descargas no es decorativo: `doc.save()` sintetiza un clic
 * por archivo, y Chrome bloquea una rafaga de clics sinteticos seguidos
 * (ademas de pedir permiso para "descargar varios archivos"). Van espaciados
 * para que el navegador los procese como descargas distintas.
 */
export async function exportTodasLasConstancias(
  data: RetencionesResponse,
  retenedor: { nombre: string; rfc: string },
): Promise<void> {
  for (const tercero of data.terceros) {
    exportConstanciaRetencion(tercero, retenedor, data.periodo);
    await new Promise((resolve) => setTimeout(resolve, 350));
  }
}
