/**
 * Calculadoras (P3-08): cada tarjeta manda su formulario al endpoint de su motor
 * y pinta lo que el backend devuelve. `fetch` stubbeado.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';

vi.mock('../services/firebase', () => ({
  auth: { currentUser: { uid: 'uid-1', getIdToken: async () => 'tk' } },
  db: {},
  default: {},
}));

const { default: CalculadorasPage } = await import('./CalculadorasPage');

let peticiones: { url: string; body: unknown }[] = [];

beforeEach(() => {
  cleanup();
  peticiones = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string, init: RequestInit = {}) => {
    peticiones.push({ url, body: init.body ? JSON.parse(String(init.body)) : null });
    if (url.endsWith('/calculadoras/actualizacion-recargos')) {
      return Response.json({
        exito: true, monto_actualizado: '25275.00', actualizacion: '275.00', meses: 6,
        tasa_acumulada: '0.1242', recargos: '3139.16', total: '28414.16',
        total_a_pagar_ajustado: '28414.00', notas: [], fundamento: 'Arts. 17-A y 21 CFF',
      });
    }
    return Response.json({ exito: false, error: 'Faltan datos' }, { status: 422 });
  }));
});

describe('CalculadorasPage', () => {
  it('pinta una tarjeta por calculadora', () => {
    render(<CalculadorasPage />);
    for (const t of ['Actualización y recargos', 'ISR de sueldos', 'ISR RESICO personas físicas',
      'Aguinaldo', 'PTU', 'Finiquito y liquidación', 'Impuesto sobre nóminas']) {
      expect(screen.getByRole('region', { name: t })).toBeTruthy();
    }
  });

  it('actualización y recargos llama al motor y enseña el desglose', async () => {
    render(<CalculadorasPage />);
    const tarjeta = screen.getByRole('region', { name: 'Actualización y recargos' });
    fireEvent.change(within(tarjeta).getByLabelText('Contribución omitida'), { target: { value: '25000' } });
    fireEvent.change(within(tarjeta).getByLabelText('Fecha en que debió pagarse'), { target: { value: '2026-02-17' } });
    fireEvent.change(within(tarjeta).getByLabelText('Fecha de pago'), { target: { value: '2026-08-10' } });
    fireEvent.click(within(tarjeta).getByRole('button', { name: /Calcular/ }));
    await waitFor(() => expect(within(tarjeta).getByText('28414.16')).toBeTruthy());
    expect(peticiones[0].url).toContain('/api/v1/calculadoras/actualizacion-recargos');
    expect(peticiones[0].body).toMatchObject({
      monto: '25000', fecha_limite: '2026-02-17', fecha_pago: '2026-08-10', tipo_recargo: 'mora',
    });
    expect(within(tarjeta).getByText('3139.16')).toBeTruthy();
  });

  it('enseña el error del backend', async () => {
    render(<CalculadorasPage />);
    const tarjeta = screen.getByRole('region', { name: 'PTU' });
    fireEvent.click(within(tarjeta).getByRole('button', { name: /Calcular/ }));
    await waitFor(() => expect(within(tarjeta).getByRole('alert')).toBeTruthy());
  });
});
