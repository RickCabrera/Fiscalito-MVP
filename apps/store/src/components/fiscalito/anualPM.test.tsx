/**
 * P3-01 / P3-06: el tab de pagos provisionales PM y el de la anual piden al
 * backend del CLIENTE ACTIVO y pintan lo que el motor devuelve, sin calcular.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

vi.mock('../../services/firebase', () => ({
  auth: { currentUser: { uid: 'uid-1', getIdToken: async () => 'tk' } },
  db: {},
  default: {},
}));
vi.mock('../../context/usePerfilFiscal', () => ({
  usePerfilFiscal: () => ({ clienteId: 'moral', nombre: 'Moral SA', rfc: 'PMS010101AB1' }),
}));

const { default: PagosProvisionalesPMTab } = await import('./PagosProvisionalesPMTab');
const { default: AnualClienteTab } = await import('./AnualClienteTab');

const pago = (mes: number, determinado: string) => ({
  mes, ingresos_mes: '1.00', ingresos_acumulados: '3800000.00', deducciones_acumuladas: '0.00',
  coeficiente: '0.1845', utilidad_estimada: '701100.00', ptu_disminuida: '0.00', estimulos: '0.00',
  perdidas: '150000.00', base: '551100.00', isr_causado: '165330.00', pagos_anteriores: '95000.00',
  retenciones: '5000.00', pago_determinado: determinado, pago_efectuado: determinado,
  pago_capturado: false, a_pagar_pesos: determinado,
});

let llamadas: { url: string; metodo: string; cuerpo: unknown }[] = [];

function responder(url: string) {
  if (url.endsWith('/pm/pagos-provisionales')) {
    return Response.json({
      exito: true, anio: 2026, mes: 3, tipo: 'pm', fuente: 'boveda', coeficiente: '0.1845',
      origen_coeficiente: 'capturado', tasa: '0.30', fecha_limite: '2026-04-17',
      pagos: [pago(1, '40000.00'), pago(2, '55000.00'), pago(3, '65330.00')],
      notas: ['Coeficiente de utilidad 0.1845 (capturado; Art. 14 fr. I LISR).'],
    });
  }
  if (url.includes('/pm/datos/')) {
    return Response.json({ exito: true, anio: 2026, datos: { coeficiente_utilidad: '0.1845', perdidas: [] } });
  }
  if (url.endsWith('/anual/papeles')) {
    return new Response('PK', { headers: { 'Content-Type': 'application/octet-stream' } });
  }
  return Response.json({
    exito: true, tipo: 'pm', anio: 2025, regimen: '601', fuente: 'contabilidad',
    renglones: [
      { clave: 'isr_ejercicio', concepto: 'ISR del ejercicio (30 %)', importe: '525077.69', fundamento: 'Art. 9' },
      { clave: 'a_cargo', concepto: 'ISR a cargo', importe: '123077.69', fundamento: 'Art. 76 fr. V' },
    ],
    meses: [{ mes: 1, ingresos: '100.00', deducciones: '50.00', no_deducibles: '0.00',
      retenciones: '0.00', pago_provisional: '15.00' }],
    coeficiente: { siguiente: '0.1859' }, ptu: { a_repartir: '200922.50' },
    notas: ['Nota anual'],
  });
}

beforeEach(() => {
  cleanup();
  llamadas = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string, init: RequestInit = {}) => {
    llamadas.push({ url, metodo: init.method ?? 'GET', cuerpo: init.body ? JSON.parse(String(init.body)) : null });
    return responder(url);
  }));
});

afterEach(() => vi.unstubAllGlobals());

describe('PagosProvisionalesPMTab', () => {
  it('pide los pagos del cliente activo y pinta el del mes con su coeficiente', async () => {
    render(<PagosProvisionalesPMTab />);
    fireEvent.change(screen.getByLabelText('Año'), { target: { value: '2026' } });
    fireEvent.change(screen.getByLabelText('Mes'), { target: { value: '3' } });
    fireEvent.click(screen.getByRole('button', { name: /Calcular/ }));
    await waitFor(() => expect(screen.getByTestId('pago-pm').textContent).toBe('65330.00'));
    expect(llamadas[0].url).toContain('/api/v1/impuestos/clientes/moral/pm/pagos-provisionales');
    expect(llamadas[0].cuerpo).toEqual({ anio: 2026, mes: 3 });
    expect(screen.getByText('0.1845')).toBeTruthy();
    expect(screen.getByRole('table', { name: 'Pagos provisionales' })).toBeTruthy();
    // Ya no es la estimación del navegador.
    expect(screen.queryByText(/motor PM en desarrollo/)).toBeNull();
  });

  it('guarda los datos del ejercicio y recalcula', async () => {
    render(<PagosProvisionalesPMTab />);
    fireEvent.click(screen.getByRole('button', { name: 'Datos del ejercicio' }));
    await waitFor(() => expect(screen.getByLabelText(/Coeficiente de utilidad/)).toBeTruthy());
    fireEvent.change(screen.getByLabelText(/PTU pagada/), { target: { value: '80000' } });
    fireEvent.change(screen.getByLabelText('Retención 3'), { target: { value: '5000' } });
    fireEvent.click(screen.getByRole('button', { name: /Guardar datos/ }));
    await waitFor(() => expect(llamadas.some((l) => l.metodo === 'PUT')).toBe(true));
    const put = llamadas.find((l) => l.metodo === 'PUT');
    expect(put?.url).toContain('/impuestos/clientes/moral/pm/datos/');
    expect(put?.cuerpo).toMatchObject({
      coeficiente_utilidad: '0.1845', ptu_pagada: '80000', retenciones_bancarias: { 3: '5000' },
    });
    await waitFor(() => expect(llamadas.some((l) => l.url.endsWith('/pm/pagos-provisionales'))).toBe(true));
  });
});

describe('AnualClienteTab', () => {
  it('calcula la anual y genera el archivo de papeles de trabajo', async () => {
    render(<AnualClienteTab />);
    fireEvent.change(screen.getByLabelText('Ejercicio'), { target: { value: '2025' } });
    fireEvent.click(screen.getByRole('button', { name: /Calcular/ }));
    await waitFor(() => expect(screen.getByTestId('anual-a_cargo').textContent).toBe('123077.69'));
    expect(llamadas[0].url).toContain('/api/v1/impuestos/clientes/moral/anual');
    expect(llamadas[0].cuerpo).toEqual({ anio: 2025, pagos_provisionales: {} });
    expect(screen.getByText('0.1859')).toBeTruthy();
    expect(screen.getByRole('table', { name: 'Mes a mes' })).toBeTruthy();

    const crear = vi.fn(() => 'blob:x');
    Object.assign(URL, { createObjectURL: crear, revokeObjectURL: vi.fn() });
    fireEvent.click(screen.getByRole('button', { name: /Generar archivo/ }));
    await waitFor(() => expect(crear).toHaveBeenCalled());
    expect(llamadas.some((l) => l.url.endsWith('/anual/papeles'))).toBe(true);
  });

  it('muestra el error del backend', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => Response.json(
      { exito: false, error: 'Captura el régimen de este cliente.' }, { status: 422 })));
    render(<AnualClienteTab />);
    fireEvent.click(screen.getByRole('button', { name: /Calcular/ }));
    await waitFor(() => expect(screen.getByRole('alert').textContent).toContain('régimen'));
  });
});
