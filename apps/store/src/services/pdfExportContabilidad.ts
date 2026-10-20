/**
 * PDF de los reportes contables (P2-05): balanza, auxiliar, estado de
 * resultados, balance general e impresión de pólizas. Se arma en el navegador
 * con jspdf + autotable a partir de la MISMA respuesta que pinta la pantalla:
 * el PDF no suma nada, sólo transcribe los importes que calculó el backend.
 */

import jsPDF from 'jspdf';
import autoTable, { type RowInput } from 'jspdf-autotable';
import type { Auxiliar, Balanza, EstadoFinanciero, Poliza } from './contabilidadApi';
import {
  PDF_COLORS, addFooter, DEFAULT_BODY_STYLES, DEFAULT_HEAD_STYLES, DEFAULT_TABLE_STYLES,
} from './pdfUtils';
import { PREFIJO_ARCHIVO } from './marca';

export interface ClientePdf { nombre: string; rfc: string; clave: string }

/** "1234.5" → "1,234.50"; ceros como guion para que la tabla respire. */
export function importePdf(valor: string | undefined, cero = '—'): string {
  const n = Number(valor ?? 0);
  if (n === 0) return cero;
  return n.toLocaleString('es-MX', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

type Doc = jsPDF & { lastAutoTable?: { finalY: number } };

function documento(titulo: string, cliente: ClientePdf, periodo: string, apaisado = false): { doc: Doc; y: number } {
  const doc = new jsPDF({ unit: 'mm', format: 'letter', orientation: apaisado ? 'landscape' : 'portrait' }) as Doc;
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(14);
  doc.setTextColor(...PDF_COLORS.dark);
  doc.text(titulo, 14, 16);
  doc.setFont('helvetica', 'normal');
  doc.setFontSize(9);
  doc.setTextColor(...PDF_COLORS.gray);
  doc.text(`${cliente.nombre} · RFC ${cliente.rfc}`, 14, 22);
  doc.text(periodo, 14, 27);
  return { doc, y: 32 };
}

function tabla(doc: Doc, y: number, head: string[], body: RowInput[], numericas: number[]): void {
  const columnStyles: Record<number, { halign: 'right' }> = {};
  for (const i of numericas) columnStyles[i] = { halign: 'right' };
  autoTable(doc, {
    startY: y, head: [head], body, theme: 'grid', margin: { left: 14, right: 14 },
    headStyles: { ...DEFAULT_HEAD_STYLES, fontSize: 8 },
    bodyStyles: { ...DEFAULT_BODY_STYLES, fontSize: 7.5 },
    styles: DEFAULT_TABLE_STYLES, columnStyles,
  });
}

const negrita = (texto: string) => ({ content: texto, styles: { fontStyle: 'bold' as const } });

function guardar(doc: Doc, nombre: string, cliente: ClientePdf): void {
  addFooter(doc);
  doc.save(`${PREFIJO_ARCHIVO}_${nombre}_${cliente.clave}.pdf`);
}

export function pdfBalanza(b: Balanza, cliente: ClientePdf): void {
  const { doc, y } = documento('Balanza de comprobación', cliente, `Del ${b.desde} al ${b.hasta}`, true);
  const cols = ['inicial_deudor', 'inicial_acreedor', 'cargos', 'abonos', 'final_deudor', 'final_acreedor'] as const;
  const body: RowInput[] = b.renglones.map((r) => [
    r.numero, `${'  '.repeat(r.nivel - 1)}${r.nombre}`, ...cols.map((c) => importePdf(r[c])),
  ]);
  body.push([negrita('Totales'), '', ...cols.map((c) => negrita(importePdf(b.totales[c], '0.00')))]);
  tabla(doc, y, ['Cuenta', 'Nombre', 'Inicial deudor', 'Inicial acreedor', 'Cargos', 'Abonos', 'Final deudor', 'Final acreedor'],
    body, [2, 3, 4, 5, 6, 7]);
  doc.text(b.cuadra ? 'La balanza cuadra.' : 'La balanza NO cuadra.', 14, (doc.lastAutoTable?.finalY ?? y) + 6);
  guardar(doc, `balanza_${b.desde}`, cliente);
}

export function pdfAuxiliar(a: Auxiliar & { desde?: string; hasta?: string }, cliente: ClientePdf): void {
  const { doc, y } = documento(`Auxiliar ${a.cuenta.numero} ${a.cuenta.nombre}`, cliente,
    `Del ${a.desde ?? ''} al ${a.hasta ?? ''}`, true);
  const body: RowInput[] = [['', '', '', negrita('Saldo inicial'), '', '', negrita(importePdf(a.saldo_inicial, '0.00'))]];
  for (const m of a.movimientos) {
    body.push([m.fecha, m.folio, m.cuenta, m.concepto, importePdf(m.cargo, ''), importePdf(m.abono, ''), importePdf(m.saldo, '0.00')]);
  }
  body.push(['', '', '', negrita('Totales y saldo final'), negrita(importePdf(a.cargos, '0.00')),
    negrita(importePdf(a.abonos, '0.00')), negrita(importePdf(a.saldo_final, '0.00'))]);
  tabla(doc, y, ['Fecha', 'Póliza', 'Cuenta', 'Concepto', 'Cargo', 'Abono', 'Saldo'], body, [4, 5, 6]);
  guardar(doc, `auxiliar_${a.cuenta.numero}`, cliente);
}

export function pdfEstadoFinanciero(e: EstadoFinanciero): void {
  const periodo = e.reporte === 'balance_general' ? `Al ${e.hasta}` : `Del ${e.desde} al ${e.hasta}`;
  const extra = e.comparativo ? ` · comparativo ${e.comparativo.desde} a ${e.comparativo.hasta}` : '';
  const moneda = e.tipo_cambio ? ` · ${e.moneda} (TC ${e.tipo_cambio})` : ` · ${e.moneda}`;
  const { doc, y } = documento(e.titulo, { ...e.cliente }, `${periodo}${extra}${moneda}`);
  const body: RowInput[] = e.lineas.map((l) => {
    if (l.tipo === 'encabezado') return [negrita(l.etiqueta), ...e.columnas.map(() => '')];
    const valores = e.columnas.map((c) => importePdf(l.valores?.[c.clave], l.tipo === 'cuenta' ? '—' : '0.00'));
    if (l.tipo === 'cuenta') return [`${'  '.repeat(Math.max(0, l.nivel - 1))}${l.numero ?? ''} ${l.etiqueta}`, ...valores];
    return [negrita(l.etiqueta), ...valores.map(negrita)];
  });
  tabla(doc, y, ['Concepto', ...e.columnas.map((c) => c.etiqueta)], body, e.columnas.map((_, i) => i + 1));
  if (e.reporte === 'balance_general') {
    doc.text(e.cuadra ? 'Activo = pasivo + capital.' : `No cuadra: diferencia ${e.diferencia}`,
      14, (doc.lastAutoTable?.finalY ?? y) + 6);
  }
  guardar(doc, `${e.reporte}_${e.hasta}`, e.cliente);
}

export function pdfPolizas(lista: Poliza[], cliente: ClientePdf, desde: string, hasta: string): void {
  const { doc, y } = documento('Pólizas', cliente, `Del ${desde} al ${hasta}`);
  const body: RowInput[] = [];
  for (const p of lista) {
    const cancelada = p.estado === 'cancelada' ? ' (CANCELADA)' : '';
    body.push([negrita(p.folio), negrita(p.fecha), { content: `${p.concepto}${cancelada}`, colSpan: 3, styles: { fontStyle: 'bold' } }]);
    for (const m of p.movimientos ?? []) {
      body.push([m.cuenta ?? '', '', `${m.nombre_cuenta ?? ''} · ${m.concepto}`, importePdf(m.cargo, ''), importePdf(m.abono, '')]);
    }
    body.push(['', '', negrita('Total póliza'), negrita(importePdf(p.total_cargos, '0.00')), negrita(importePdf(p.total_abonos, '0.00'))]);
  }
  tabla(doc, y, ['Cuenta / folio', 'Fecha', 'Concepto', 'Cargo', 'Abono'], body, [3, 4]);
  guardar(doc, `polizas_${desde}`, cliente);
}
