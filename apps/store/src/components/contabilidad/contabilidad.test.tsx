/**
 * Pantallas de Contabilito (P2-01 a P2-04) con `fetch` stubbeado: lo que se
 * mide es qué se le pide al backend y qué se pinta con su respuesta. Ningún
 * importe se calcula aquí: el cuadre lo dice el backend.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { enArbol, mesDe, sumaCentavos, aCentavos } from './comun';
import type { Cuenta } from '../../services/contabilidadApi';

vi.mock('../../services/firebase', () => ({
  auth: { currentUser: { uid: 'uid-1', getIdToken: async () => 'tk' } },
  db: {},
  default: {},
}));

const { default: PolizasCliente } = await import('./PolizasCliente');
const { default: BalanzaCliente } = await import('./BalanzaCliente');
const { default: CatalogoCuentas } = await import('./CatalogoCuentas');
const { default: FormPoliza } = await import('./FormPoliza');

const cuenta = (id: number, numero: string, padre: number | null, afectable = true): Cuenta => ({
  id, numero, nombre: `Cuenta ${numero}`, nivel: numero.split('.').length, naturaleza: 'deudora',
  tipo: 'activo', padre_id: padre, codigo_agrupador: numero.split('.').slice(0, 2).join('.'), afectable,
});
const CUENTAS = [cuenta(1, '102', null, false), cuenta(2, '102.01', 1), cuenta(3, '301.01', null)];

const POLIZA = {
  id: 9, folio: 'D-2026-03-0001', tipo: 'diario', numero: 1, fecha: '2026-03-10', concepto: 'Venta T1',
  origen: 'automatica', estado: 'activa', uuid_cfdi: 'UUID-1', tipo_cfdi: 'I', total_cargos: '1160.00',
  total_abonos: '1160.00', diferencia: '0.00', advertencias: [], editada: false, reversa_de_id: null,
  motivo_cancelacion: '', cancelada_en: null,
  movimientos: [
    { id: 1, cuenta_id: 2, cuenta: '105.01', nombre_cuenta: 'Clientes', concepto: 'Clientes', cargo: '1160.00', abono: '0.00', uuid: 'UUID-1', rfc: 'COM' },
    { id: 2, cuenta_id: 3, cuenta: '401.01', nombre_cuenta: 'Ingresos', concepto: 'Ingreso', cargo: '0.00', abono: '1160.00', uuid: 'UUID-1', rfc: 'COM' },
  ],
};

const RENGLON = {
  cuenta_id: 2, numero: '105.01', nombre: 'Clientes', nivel: 2, naturaleza: 'deudora', afectable: true,
  codigo_agrupador: '105.01', saldo_inicial: '0.00', saldo_final: '1160.00', inicial_deudor: '0.00',
  inicial_acreedor: '0.00', cargos: '1160.00', abonos: '0.00', final_deudor: '1160.00', final_acreedor: '0.00',
};

let peticiones: { url: string; method: string; body: string }[] = [];

beforeEach(() => {
  cleanup();
  peticiones = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string, init: RequestInit = {}) => {
    const method = init.method ?? 'GET';
    peticiones.push({ url, method, body: String(init.body ?? '') });
    const ruta = new URL(url).pathname;
    if (ruta.endsWith('/polizas/generar')) {
      return Response.json({ exito: true, en_segundo_plano: false, resultado: { generadas: 3, ya_existian: 1, omitidas: 0, canceladas: 0, revertidas: 0, errores: [] } });
    }
    if (ruta.endsWith('/polizas/9')) return Response.json({ exito: true, poliza: POLIZA });
    if (ruta.endsWith('/polizas') && method === 'POST') return Response.json({ exito: true, poliza: POLIZA }, { status: 201 });
    if (ruta.endsWith('/polizas')) return Response.json({ exito: true, total: 1, pagina: 1, por_pagina: 50, polizas: [POLIZA] });
    if (ruta.endsWith('/auxiliar')) {
      return Response.json({ exito: true, cuenta: CUENTAS[1], saldo_inicial: '0.00', cargos: '1160.00', abonos: '0.00', saldo_final: '1160.00', truncado: false,
        movimientos: [{ poliza_id: 9, folio: 'D-2026-03-0001', fecha: '2026-03-10', tipo_poliza: 'diario', concepto: 'Clientes', cuenta: '105.01', cargo: '1160.00', abono: '0.00', saldo: '1160.00', uuid: 'UUID-1', rfc: 'COM', xml_disponible: true }] });
    }
    if (ruta.endsWith('/balanza')) {
      return Response.json({ exito: true, desde: '2026-03-01', hasta: '2026-03-31', renglones: [RENGLON], cuadra: false,
        totales: { inicial_deudor: '0', inicial_acreedor: '0', cargos: '1160.00', abonos: '1000.00', final_deudor: '1160.00', final_acreedor: '0' },
        diferencias: { saldo_inicial: '0.00', movimientos: '160.00', saldo_final: '160.00' } });
    }
    if (ruta.endsWith('/codigo-agrupador')) return Response.json({ exito: true, fuente: 'Anexo 24 RMF', codigos: [] });
    if (ruta.endsWith('/cuentas/sembrar')) return Response.json({ exito: true, creadas: 120 });
    if (ruta.endsWith('/cuentas')) return Response.json({ exito: true, cuentas: CUENTAS });
    return Response.json({ exito: true });
  }));
});

describe('utilidades', () => {
  it('mes, árbol y centavos', () => {
    expect(mesDe('2026-02-14')).toEqual({ desde: '2026-02-01', hasta: '2026-02-28' });
    expect(enArbol([CUENTAS[2], CUENTAS[1], CUENTAS[0]]).map((c) => c.numero)).toEqual(['102', '102.01', '301.01']);
    expect(sumaCentavos(['0.10', '0.20'])).toBe(30);
    expect(aCentavos('$1,234.5')).toBe('1234.50');
    expect(aCentavos('-3')).toBe('');
  });
});

describe('P2-03 · Pólizas', () => {
  it('lista las del mes del cliente y genera las del periodo', async () => {
    render(<PolizasCliente clave="taller" />);
    expect(await screen.findByText('D-2026-03-0001')).toBeTruthy();
    expect(peticiones[0].url).toContain('/contabilidad/clientes/taller/polizas?desde=');
    fireEvent.click(screen.getByRole('button', { name: /Generar pólizas del periodo/ }));
    expect(await screen.findByText(/3 generadas · 1 ya existían/)).toBeTruthy();
    const gen = peticiones.find((p) => p.url.endsWith('/polizas/generar'))!;
    expect(gen.method).toBe('POST');
    expect(JSON.parse(gen.body)).toMatchObject({ desde: mesDe().desde, hasta: mesDe().hasta });
  });

  it('abre el detalle con sus movimientos', async () => {
    render(<PolizasCliente clave="taller" polizaInicial={9} />);
    const detalle = await screen.findByRole('region', { name: 'Detalle de la póliza' });
    expect(await within(detalle).findByText(/Totales · cuadra/)).toBeTruthy();
    expect(within(detalle).getByText('401.01')).toBeTruthy();
  });
});

describe('P2-03 · Póliza manual', () => {
  it('no deja guardar hasta que cuadra y manda importes a centavos', async () => {
    const listo = vi.fn();
    render(<FormPoliza clave="taller" onListo={listo} onCancelar={() => undefined} />);
    await screen.findAllByRole('option', { name: /102.01/ });
    fireEvent.change(screen.getByLabelText('Cuenta del renglón 1'), { target: { value: '2' } });
    fireEvent.change(screen.getByLabelText('Cuenta del renglón 2'), { target: { value: '3' } });
    fireEvent.change(screen.getByLabelText('Cargo del renglón 1'), { target: { value: '100' } });
    fireEvent.change(screen.getByLabelText('Abono del renglón 2'), { target: { value: '90' } });
    const guardar = screen.getByRole('button', { name: 'Guardar póliza' }) as HTMLButtonElement;
    expect(guardar.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText('Abono del renglón 2'), { target: { value: '100' } });
    expect(guardar.disabled).toBe(false);
    fireEvent.click(guardar);
    await waitFor(() => expect(listo).toHaveBeenCalled());
    const alta = peticiones.find((p) => p.method === 'POST')!;
    expect(JSON.parse(alta.body).movimientos).toEqual([
      { cuenta_id: 2, concepto: '', cargo: '100.00', abono: '0.00', uuid: '', rfc: '' },
      { cuenta_id: 3, concepto: '', cargo: '0.00', abono: '100.00', uuid: '', rfc: '' },
    ]);
  });
});

describe('P2-04 · Balanza', () => {
  it('enseña el descuadre del backend y baja al auxiliar y a la póliza', async () => {
    const abrir = vi.fn();
    render(<BalanzaCliente clave="taller" onAbrirPoliza={abrir} />);
    expect(await screen.findByText(/La balanza NO cuadra/)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Auxiliar de 105.01' }));
    const aux = await screen.findByRole('region', { name: 'Auxiliar de 105.01' });
    expect(peticiones.some((p) => p.url.includes('/cuentas/2/auxiliar?desde='))).toBe(true);
    expect(within(aux).getByRole('button', { name: 'Descargar XML UUID-1' })).toBeTruthy();
    fireEvent.click(within(aux).getByRole('button', { name: 'D-2026-03-0001' }));
    expect(abrir).toHaveBeenCalledWith(9);
  });
});

describe('P2-01 · Catálogo', () => {
  it('pinta el árbol y siembra el catálogo base', async () => {
    render(<CatalogoCuentas clave="taller" />);
    expect(await screen.findByText('Cuenta 102.01')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: /catálogo base/ }));
    await waitFor(() => expect(peticiones.some((p) => p.url.endsWith('/cuentas/sembrar') && p.method === 'POST')).toBe(true));
    fireEvent.click(screen.getByRole('button', { name: 'Agregar subcuenta a 102.01' }));
    expect(screen.getByText(/Subcuenta de 102.01/)).toBeTruthy();
  });
});
