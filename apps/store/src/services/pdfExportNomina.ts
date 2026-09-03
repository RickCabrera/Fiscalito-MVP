/** PDF export de la nómina del periodo (D-07). DEMO: se borra en F2. */

import jsPDF from 'jspdf';
import autoTable from 'jspdf-autotable';
import type { NominaPeriodo, ReciboNomina } from './nominaDemoApi';
import { etiquetaOrigen, type ClienteDetalle } from './despachoApi';
import { modoEmpresaUnica } from './modoEmpresa';
import { esClienteDemo } from './entorno';
import {
  PDF_COLORS, fmtMoney, addFooter,
  DEFAULT_HEAD_STYLES, DEFAULT_BODY_STYLES, DEFAULT_TABLE_STYLES, DEFAULT_ALT_ROW_STYLES,
} from './pdfUtils';
import { MARCA_CORTA, PREFIJO_ARCHIVO } from './marca';

function isr(recibo: ReciboNomina): number {
  return recibo.deducciones
    .filter((d) => d.tipo === '002')
    .reduce((suma, d) => suma + Number(d.importe), 0);
}

/**
 * Exporta la nómina del periodo, con el cliente al que pertenece.
 *
 * LA BANDA "DATOS DE DEMOSTRACIÓN" ES PARTE DE LA PRIVACIDAD, NO DE LA ESTÉTICA.
 * Un PDF con nueve nombres, nueve sueldos y cuotas IMSS reales que circule sin
 * ella parece la nómina de un cliente de verdad. Por eso se pinta para **toda**
 * la cartera: los tres clientes de E-02 son de demostración hasta que exista el
 * alta real (F1-09), y el día que haya clientes reales esta condición tiene que
 * volverse explícita en vez de desaparecer.
 *
 * Colgaba de `origen_plantilla === 'demo'`, que dejó de variar en E-03.
 */
export function exportarNominaPDF(
  data: NominaPeriodo,
  cliente: ClienteDetalle,
  /**
   * Cuántos empleados de la cartera quedaron FUERA de este cálculo por no
   * tener `employeeNo` (G-02). Default 0 para no romper a quien no lo sepa.
   */
  sinVincular = 0,
): void {
  const doc = new jsPDF({ unit: 'mm', format: 'letter' });
  const pageW = doc.internal.pageSize.getWidth();
  const mL = 20;
  let y = 20;

  doc.setFont('helvetica', 'bold');
  doc.setFontSize(16);
  doc.setTextColor(...PDF_COLORS.dark);
  doc.text(`${MARCA_CORTA} — Nómina del periodo`, mL, y);
  y += 8;

  // La banda cuelga del CLIENTE, no de `origen_plantilla` (E-03).
  //
  // Colgaba de `origen_plantilla === 'demo'`, y ese campo vale "request" desde
  // que la pantalla manda la plantilla en el request — obligatorio para los
  // clientes sintéticos. Dejarlo así habría **apagado la banda en los tres**:
  // un PDF con nueve nombres, nueve sueldos y cuotas IMSS reales saldría de la
  // sala sin la única marca que dice que no es la nómina de un cliente de
  // verdad.
  //
  // **O-01 ES ESE DÍA.** Este comentario decía "el día que deje de serlo, la
  // condición se escriba aquí y no se olvide", y el pivote lo volvió cierto: en
  // modo empresa única la nómina es la de Orca, con nombres y sueldos REALES.
  //
  // Sellarla "identidades sintéticas" es peor en papel que en pantalla. La
  // banda es un control de PRIVACIDAD: existe para que un PDF con nueve
  // nombres y nueve sueldos no salga de la sala pareciendo la nómina de un
  // cliente de verdad. Afirmando lo contrario sobre datos reales, deja de ser
  // un control y pasa a ser una etiqueta falsa que invita a compartirlo.
  //
  // Es la MISMA expresión que `EncabezadoNomina.tsx`, y a propósito: la
  // pantalla y el papel no pueden discrepar sobre si esto es una demostración.
  // En modo despacho sigue siendo incondicional — toda la cartera de E-02 es de
  // demostración hasta que exista el alta real de clientes (F1-09).
  const esDeDemostracion = modoEmpresaUnica() ? esClienteDemo(cliente.origen) : true;
  if (esDeDemostracion) {
    doc.setFillColor(...PDF_COLORS.demo);
    doc.rect(mL, y - 4, pageW - mL - 20, 7, 'F');
    doc.setTextColor(...PDF_COLORS.white);
    doc.setFontSize(9);
    doc.text('DATOS DE DEMOSTRACIÓN — identidades sintéticas, no es la nómina de un cliente', mL + 2, y + 1);
    y += 10;
  }

  // De quién es esta nómina. Si la pantalla lo dice y el papel no, la honestidad
  // se queda en la sala y el PDF se va sin ella.
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(11);
  doc.setTextColor(...PDF_COLORS.dark);
  const empresaUnica = modoEmpresaUnica();
  doc.text(`${empresaUnica ? 'Empresa' : 'Cliente'}: ${cliente.nombre}`, mL, y);
  y += 5;
  doc.setFont('helvetica', 'normal');
  doc.setFontSize(9);
  doc.setTextColor(...PDF_COLORS.gray);
  // `etiquetaOrigen('propio')` devuelve el slug crudo, así que en modo empresa
  // única el papel decía "· propio". El origen sólo distingue clientes de
  // demostración de reales, y con un solo patrón no hay nada que distinguir.
  const subtitulo = [cliente.giro, empresaUnica ? '' : etiquetaOrigen(cliente.origen)]
    .filter(Boolean)
    .join(' · ');
  if (subtitulo) {
    doc.text(subtitulo, mL, y);
    y += 7;
  } else {
    y += 2;
  }

  doc.setFont('helvetica', 'normal');
  doc.setFontSize(10);
  doc.setTextColor(...PDF_COLORS.gray);
  doc.text(`Periodo: ${data.periodo.inicio} a ${data.periodo.fin}`, mL, y);
  y += 5;
  doc.text(`Fecha de pago: ${data.fecha_pago_efectiva}`, mL, y);
  y += 5;

  // G-02: excluir gente del cálculo es una decisión con consecuencia fiscal, y
  // este papel es el que llega al contador y al patrón. Si la pantalla lo dice
  // y el PDF no, la honestidad se queda en la sala — y aquí es peor que en el
  // encabezado del cliente, porque además las cuotas patronales de abajo salen
  // cortas: se calculan sólo sobre los incluidos.
  if (sinVincular > 0) {
    doc.setTextColor(...PDF_COLORS.demo);
    doc.setFont('helvetica', 'bold');
    doc.text(
      `${sinVincular} ${sinVincular === 1 ? 'empleado no está vinculado' : 'empleados no están vinculados'} ` +
        `al checador y NO ${sinVincular === 1 ? 'entra' : 'entran'} en este cálculo.`,
      mL,
      y,
    );
    y += 5;
    doc.setFont('helvetica', 'normal');
    doc.setFontSize(9);
    doc.text('Las cuotas patronales de abajo sólo cubren a los incluidos.', mL, y);
    doc.setFontSize(10);
    y += 5;
    doc.setTextColor(...PDF_COLORS.gray);
  }
  y += 3;

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
  // El cliente va en el NOMBRE del archivo: sin él, los tres clientes exportan
  // el mismo nombre para la misma quincena y caen en Descargas como
  // `…(1)`, `…(2)`, sin que ninguno diga de quién es hasta abrirlo.
  const idArchivo = cliente.id.replace(/[^A-Za-z0-9_-]/g, '_');
  doc.save(`${PREFIJO_ARCHIVO}_Nomina_${idArchivo}_${data.periodo.inicio}_${data.periodo.fin}.pdf`);
}
