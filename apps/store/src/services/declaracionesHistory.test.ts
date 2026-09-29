/**
 * El historial de declaraciones, por cliente (C-02), contra un Firestore de
 * mentira en memoria.
 *
 * Lo que protege:
 *  1. El contribuyente guarda y lee EXACTAMENTE como antes.
 *  2. Dos clientes del mismo despacho no se pisan el mismo periodo.
 *  3. El acumulado del Art. 106 no suma meses de otro cliente.
 *  4. Un cliente no ve el historial de otro, ni el contribuyente el de un cliente.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';

type Doc = Record<string, unknown>;
const almacen = new Map<string, Doc>();

class TimestampFalso {
  constructor(private readonly ms: number) {}
  static now() { return new TimestampFalso(Date.now()); }
  toMillis() { return this.ms; }
  toDate() { return new Date(this.ms); }
}

type Restriccion = { where?: [string, string, unknown] };

vi.mock('firebase/firestore', () => ({
  collection: (_db: unknown, ...partes: string[]) => ({ path: partes.join('/') }),
  doc: (ref: { path: string }, id: string) => ({ path: `${ref.path}/${id}`, id }),
  setDoc: async (ref: { path: string }, data: Doc) => { almacen.set(ref.path, data); },
  deleteDoc: async (ref: { path: string }) => { almacen.delete(ref.path); },
  where: (campo: string, op: string, valor: unknown) => ({ where: [campo, op, valor] }),
  orderBy: () => ({}),
  limit: () => ({}),
  query: (ref: { path: string }, ...restricciones: Restriccion[]) => ({ ref, restricciones }),
  getDocs: async (q: { ref?: { path: string }; path?: string; restricciones?: Restriccion[] }) => {
    const base = q.ref?.path ?? q.path ?? '';
    const docs = [...almacen.entries()]
      .filter(([path]) => path.startsWith(`${base}/`))
      .filter(([, data]) => (q.restricciones ?? []).every((r) => !r.where || data[r.where[0]] === r.where[2]))
      .map(([path, data]) => ({ id: path.slice(base.length + 1), data: () => data }));
    return { docs };
  },
  Timestamp: TimestampFalso,
}));
vi.mock('./firebase', () => ({ db: {} }));

const {
  guardarDeclaracion, guardarDIOT, obtenerAcumuladoAnterior, obtenerHistorial, limpiarDuplicados,
} = await import('./declaracionesHistory');

const UID = 'uid-demo';
const RUTA = `users/${UID}/declaraciones`;

function desglose(ingresos: number, isr: number) {
  return {
    total_ingresos_facturados: ingresos, total_ingresos_gravados: ingresos, cantidad_facturas_ingreso: 1,
    total_egresos: 0, total_deducciones_autorizadas: 0, cantidad_facturas_egreso: 0,
    base_isr: ingresos, tasa_isr: 0, isr_causado: isr, isr_retenido: 0, isr_a_pagar: isr,
    iva_trasladado_cobrado: 0, iva_trasladado_pagado: 0, iva_retenido: 0, iva_a_pagar: 0, total_a_pagar: isr,
  };
}

function mensual(periodo: string, ingresos: number, isr: number) {
  return { tipo: 'mensual', periodo, regimen: '612', fecha_calculo: new Date(), desglose: desglose(ingresos, isr) };
}

beforeEach(() => almacen.clear());

describe('guardar', () => {
  it('el contribuyente guarda con el id de siempre y SIN cliente_id', async () => {
    const id = await guardarDeclaracion(UID, mensual('Enero 2026', 1000, 10));
    expect(id).toBe('predeclaracion_enero_2026');
    expect(almacen.get(`${RUTA}/predeclaracion_enero_2026`)).not.toHaveProperty('cliente_id');
  });

  it('el mismo periodo de dos clientes queda en dos documentos, cada uno con su cliente_id', async () => {
    await guardarDeclaracion(UID, mensual('Enero 2026', 1000, 10), 'predeclaracion', 'taller');
    await guardarDeclaracion(UID, mensual('Enero 2026', 5000, 50), 'predeclaracion', 'resico');
    const docs = [...almacen.values()];
    expect(docs).toHaveLength(2);
    expect(docs.map((d) => d.cliente_id).sort()).toEqual(['resico', 'taller']);
  });

  it('los guardados de los otros tabs también llevan el cliente', async () => {
    await guardarDIOT(UID, {
      periodo: 'Enero 2026', proveedores: [], total_operaciones: 0, total_iva: 0,
    } as unknown as Parameters<typeof guardarDIOT>[1], 0, 'taller');
    expect(almacen.get(`${RUTA}/c_taller__diot_enero_2026`)?.cliente_id).toBe('taller');
  });
});

describe('obtenerAcumuladoAnterior (Art. 106)', () => {
  beforeEach(async () => {
    await guardarDeclaracion(UID, mensual('Enero 2026', 1000, 10), 'predeclaracion', 'taller');
    await guardarDeclaracion(UID, mensual('Enero 2026', 5000, 50), 'predeclaracion', 'resico');
    await guardarDeclaracion(UID, mensual('Febrero 2026', 7000, 70));
  });

  it('un cliente sólo acumula SUS meses', async () => {
    const r = await obtenerAcumuladoAnterior(UID, 2026, 3, 'taller');
    expect(r.ingresos_acumulados).toBe(1000);
    expect(r.isr_pagado_anterior).toBe(10);
    expect(r.meses_faltantes).toEqual([2]);
  });

  it('el contribuyente no acumula los meses de ningún cliente', async () => {
    const r = await obtenerAcumuladoAnterior(UID, 2026, 3);
    expect(r.ingresos_acumulados).toBe(7000);
    expect(r.meses_encontrados).toEqual([2]);
  });
});

describe('obtenerHistorial', () => {
  it('con cliente: sólo los suyos, del más reciente al más viejo, con límite y categoría', async () => {
    almacen.set(`${RUTA}/a`, { categoria: 'predeclaracion', periodo: 'Enero 2026', cliente_id: 'taller', fecha_calculo: new TimestampFalso(1) });
    almacen.set(`${RUTA}/b`, { categoria: 'predeclaracion', periodo: 'Febrero 2026', cliente_id: 'taller', fecha_calculo: new TimestampFalso(3) });
    almacen.set(`${RUTA}/c`, { categoria: 'diot', periodo: 'Enero 2026', cliente_id: 'taller', fecha_calculo: new TimestampFalso(2) });
    almacen.set(`${RUTA}/d`, { categoria: 'predeclaracion', periodo: 'Enero 2026', cliente_id: 'resico', fecha_calculo: new TimestampFalso(9) });
    almacen.set(`${RUTA}/e`, { categoria: 'predeclaracion', periodo: 'Enero 2026', fecha_calculo: new TimestampFalso(8) });

    expect((await obtenerHistorial(UID, 10, undefined, 'taller')).map((r) => r.id)).toEqual(['b', 'c', 'a']);
    expect((await obtenerHistorial(UID, 1, undefined, 'taller')).map((r) => r.id)).toEqual(['b']);
    expect((await obtenerHistorial(UID, 10, 'diot', 'taller')).map((r) => r.id)).toEqual(['c']);
  });

  it('sin cliente: el contribuyente no ve los cálculos de un cliente', async () => {
    almacen.set(`${RUTA}/propio`, { categoria: 'predeclaracion', periodo: 'Enero 2026', fecha_calculo: new TimestampFalso(1) });
    almacen.set(`${RUTA}/ajeno`, { categoria: 'predeclaracion', periodo: 'Enero 2026', cliente_id: 'taller', fecha_calculo: new TimestampFalso(2) });
    expect((await obtenerHistorial(UID, 10)).map((r) => r.id)).toEqual(['propio']);
  });
});

describe('limpiarDuplicados', () => {
  it('no toma el mismo periodo de dos clientes como duplicado', async () => {
    almacen.set(`${RUTA}/x`, { categoria: 'predeclaracion', periodo: 'Enero 2026', cliente_id: 'taller', fecha_calculo: new TimestampFalso(1) });
    almacen.set(`${RUTA}/y`, { categoria: 'predeclaracion', periodo: 'Enero 2026', cliente_id: 'resico', fecha_calculo: new TimestampFalso(2) });
    expect(await limpiarDuplicados(UID)).toBe(0);
    expect(almacen.size).toBe(2);
  });
});
