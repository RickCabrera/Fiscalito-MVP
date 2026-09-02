/**
 * El PDF de la nómina (E-03).
 *
 * POR QUÉ ESTE ARCHIVO EXISTE
 * ---------------------------
 * La banda "DATOS DE DEMOSTRACIÓN" colgaba de `origen_plantilla === 'demo'`.
 * E-03 hace que la pantalla mande la plantilla en el request —obligatorio para
 * los clientes sintéticos—, con lo que ese campo pasó a valer `"request"`
 * siempre. Nadie lo habría notado: el PDF sigue generándose, sólo que **sin la
 * única marca que dice que esos nueve nombres y nueve sueldos no son la nómina
 * de un cliente de verdad**.
 *
 * La banda es privacidad, no estética. Estos tests son su candado.
 */

import { afterEach, describe, expect, it, vi } from 'vitest';
import type { ClienteDetalle } from './despachoApi';
import type { NominaPeriodo } from './nominaDemoApi';

/** Texto que jsPDF fue recibiendo, para poder asertar sobre el documento. */
const textos: string[] = [];

vi.mock('jspdf', () => {
  class FakeDoc {
    internal = { pageSize: { getWidth: () => 216, getHeight: () => 279 } };
    getNumberOfPages() { return 1; }
    // `autoTable` real lo deja para que el llamador sepa dónde sigue el texto.
    lastAutoTable = { finalY: 120 };
    // El real parte el texto en líneas; aquí basta con devolverlo entero para
    // poder asertar sobre su contenido.
    splitTextToSize(t: string) { return [t]; }
    setFont() { return this; }
    setFontSize() { return this; }
    setTextColor() { return this; }
    setFillColor() { return this; }
    setDrawColor() { return this; }
    setPage() { return this; }
    rect() { return this; }
    line() { return this; }
    addPage() { return this; }
    save() { return this; }
    text(t: string | string[]) {
      textos.push(Array.isArray(t) ? t.join(' ') : t);
      return this;
    }
  }
  return { default: FakeDoc };
});

vi.mock('jspdf-autotable', () => ({ default: vi.fn() }));

const { exportarNominaPDF } = await import('./pdfExportNomina');

function cliente(id: string, nombre: string, origen: string): ClienteDetalle {
  return {
    id, nombre, origen,
    giro: 'Giro de prueba',
    num_empleados: 1,
    prima_riesgo: '0.0054355',
    clase_riesgo: null,
    clave_periodicidad: '04',
    zona: 'general',
    fecha_referencia: '2026-09-01',
    empleados: [],
    periodo_sugerido: { inicio: '2026-08-16', fin: '2026-08-31', fecha_pago: '2026-08-31' },
  };
}

function nomina(origenPlantilla: string): NominaPeriodo {
  return {
    cliente: 'x',
    periodo: { inicio: '2026-08-16', fin: '2026-08-31', fecha_pago: '2026-08-31' },
    fecha_pago_efectiva: '2026-08-31',
    origen_plantilla: origenPlantilla,
    recibos: [{
      empleado_no: 'E-01', nombre: 'PERSONA UNA', sbc: '331.58', es_salario_minimo: false,
      dias_periodo: 16, dias_ausentismo: 0, dias_pagados: 16,
      percepciones: [], deducciones: [], otros_pagos: [],
      total_percepciones: '5056.00', total_deducciones: '217.07', neto: '4838.93',
      cuota_obrera: '125.99', cuota_patronal: '600.00', absorbio_cuota_obrera: false, ramos: [],
    }],
    porcion_mensual: { periodicidad: 'mensual', por_ramo: {}, total_patron: '600.00', total_obrero: '125.99', total: '725.99', empleados: 1 },
    porcion_bimestral: { periodicidad: 'bimestral', por_ramo: {}, total_patron: '300.00', total_obrero: '0.00', total: '300.00', empleados: 1 },
    advertencias: ['Aviso del motor que tiene que llegar al papel'],
  };
}

afterEach(() => {
  textos.length = 0;
});

describe('banda de demostración', () => {
  /**
   * EL CASO QUE VALE EL ARCHIVO. Con `origen_plantilla: "request"` —lo que
   * devuelve el backend desde que la plantilla viaja en el body— la banda tiene
   * que seguir ahí.
   */
  it('se pinta aunque la plantilla haya viajado en el request', () => {
    exportarNominaPDF(nomina('request'), cliente('demo', 'Cliente Demo', 'fixtures-s04'));
    expect(textos.some((t) => t.includes('DATOS DE DEMOSTRACIÓN'))).toBe(true);
  });

  it.each([
    ['demo', 'fixtures-s04'],
    ['cafeteria', 'sintetico'],
    ['taller', 'sintetico'],
  ])('se pinta para el cliente %s', (id, origen) => {
    exportarNominaPDF(nomina('request'), cliente(id, `Cliente ${id}`, origen));
    expect(textos.some((t) => t.includes('DATOS DE DEMOSTRACIÓN'))).toBe(true);
  });
});

describe('de quién es la nómina', () => {
  it('el PDF imprime el nombre del cliente', () => {
    exportarNominaPDF(nomina('request'), cliente('taller', 'Taller Mecanico Nogal', 'sintetico'));
    expect(textos.some((t) => t.includes('Taller Mecanico Nogal'))).toBe(true);
  });

  it('y si son datos sintéticos, lo dice', () => {
    exportarNominaPDF(nomina('request'), cliente('taller', 'Taller Mecanico Nogal', 'sintetico'));
    expect(textos.some((t) => t.includes('Datos sintéticos'))).toBe(true);
  });

  it('el caso real anonimizado va etiquetado como tal', () => {
    exportarNominaPDF(nomina('request'), cliente('demo', 'Cliente Demo', 'fixtures-s04'));
    expect(textos.some((t) => t.includes('Caso real anonimizado'))).toBe(true);
  });
});

describe('las advertencias del motor llegan al papel', () => {
  it('imprime los avisos que vienen en la respuesta', () => {
    /**
     * Es lo único que separa una nómina de gente que no fue a trabajar de una
     * mentira. Si se pierden al mudar la pantalla, el PDF sale limpio y falso.
     */
    exportarNominaPDF(nomina('request'), cliente('taller', 'Taller Nogal', 'sintetico'));
    expect(textos.some((t) => t.includes('Aviso del motor que tiene que llegar al papel'))).toBe(true);
  });
});
