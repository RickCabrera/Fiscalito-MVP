/** Cobranza del despacho (P5-03): saldo y antigüedad por cliente, estado de cuenta y acciones. */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../services/firebase', () => ({
  auth: { currentUser: { uid: 'uid-1', getIdToken: async () => 'tok' } },
  db: {},
  default: {},
}));

const { default: CobranzaPage } = await import('./CobranzaPage');

const SALDO = {
  total_cargos: '20000.00', total_pagos: '7000.00', saldo: '13000.00', vencido: '8000.00',
  antiguedad: { '0_30': '5000.00', '31_60': '5000.00', '61_90': '3000.00', mas_90: '0.00' },
  desde: '2026-08-05', vencido_desde: '2026-08-15',
};
const RESUMEN = {
  exito: true, hoy: '2026-10-19', totales: SALDO,
  clientes: [{ cliente: 'taller', cliente_nombre: 'Taller', iguala_mensual: '5000.00', ...SALDO }],
};
const DETALLE = {
  exito: true, hoy: '2026-10-19', cliente: 'taller', cliente_nombre: 'Taller', ...SALDO,
  movimientos: [{ fecha: '2026-08-05', tipo: 'cargo', id: 1, concepto: 'Honorarios 2026-08',
    cargo: '5000.00', abono: '0.00', saldo: '5000.00', vencimiento: '2026-08-15', uuid: null }],
  honorarios: null, recordatorios: [],
};

let llamadas: { url: string; metodo: string; cuerpo: unknown }[] = [];

beforeEach(() => {
  llamadas = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    const metodo = init?.method ?? 'GET';
    llamadas.push({ url, metodo, cuerpo: init?.body ? JSON.parse(String(init.body)) : null });
    if (url.includes('/recordatorios')) {
      return new Response(JSON.stringify({ recordatorio: { estado: 'enviado', canal: 'correo', error: '' } }));
    }
    if (url.endsWith('/cobranza/resumen')) return new Response(JSON.stringify(RESUMEN));
    if (url.endsWith('/cobranza/clientes/taller')) return new Response(JSON.stringify(DETALLE));
    return new Response(JSON.stringify({ exito: true, cargos: 1, periodo: '2026-10' }));
  }));
});
afterEach(cleanup);

const montar = (ruta = '/app/cobranza') =>
  render(<MemoryRouter initialEntries={[ruta]}><CobranzaPage /></MemoryRouter>);

describe('CobranzaPage', () => {
  it('muestra qué debe cada cliente y desde cuándo', async () => {
    montar();
    expect(await screen.findByText('Taller')).toBeTruthy();
    expect(screen.getAllByText('2026-08-05').length).toBeGreaterThan(0);
    expect(screen.getAllByText(/13,000\.00/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/3,000\.00/).length).toBeGreaterThan(0);
  });

  it('entra al estado de cuenta con ?cliente= y manda un recordatorio', async () => {
    montar('/app/cobranza?cliente=taller');
    expect(await screen.findByRole('region', { name: 'Estado de cuenta de Taller' })).toBeTruthy();
    expect(screen.getByText('Honorarios 2026-08')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: /Recordar por correo/ }));
    await waitFor(() => expect(llamadas.some((l) => l.url.includes('/recordatorios'))).toBe(true));
    const r = llamadas.find((l) => l.url.includes('/recordatorios'))!;
    expect(r).toMatchObject({ metodo: 'POST', cuerpo: { canal: 'correo', programado_para: null } });
    expect(await screen.findByText('Recordatorio enviado por correo.')).toBeTruthy();
  });

  it('registra un pago con UUID opcional', async () => {
    montar('/app/cobranza?cliente=taller');
    await screen.findByRole('region', { name: 'Estado de cuenta de Taller' });
    fireEvent.change(screen.getByLabelText('Importe del pago'), { target: { value: '2500' } });
    fireEvent.change(screen.getByLabelText('UUID del CFDI'), { target: { value: 'abc' } });
    fireEvent.click(screen.getByRole('button', { name: 'Registrar pago' }));
    await waitFor(() => expect(llamadas.some((l) => l.url.endsWith('/pagos'))).toBe(true));
    expect(llamadas.find((l) => l.url.endsWith('/pagos'))!.cuerpo).toMatchObject({
      importe: '2500', cfdi_uuid: 'abc', fecha: '2026-10-19' });
  });

  it('un 403 (auxiliar) se ve como error', async () => {
    vi.stubGlobal('fetch', vi.fn(async () =>
      new Response(JSON.stringify({ exito: false, error: 'Tu rol no permite esta acción.' }), { status: 403 })));
    montar();
    expect(await screen.findByText(/Tu rol no permite/)).toBeTruthy();
  });
});
