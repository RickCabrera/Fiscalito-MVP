/**
 * Resumen de impuestos (P3-02): pide el resumen del CLIENTE ACTIVO con la fecha
 * de pago, pinta la tabla y manda lo capturado al recalcular.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

vi.mock('../../services/firebase', () => ({
  auth: { currentUser: { uid: 'uid-1', getIdToken: async () => 'tk' } },
  db: {},
  default: {},
}));
vi.mock('../../context/usePerfilFiscal', () => ({
  usePerfilFiscal: () => ({ clienteId: 'taller', nombre: 'Taller Sintético', rfc: 'XEXX010101AB1' }),
}));

const { default: ResumenImpuestosTab } = await import('./ResumenImpuestosTab');

const renglon = (clave: string, concepto: string, total: string) => ({
  clave, grupo: 'IVA', concepto, aplica: true, importe_sistema: total, importe_a_pagar: total,
  actualizacion: '0.00', recargos: '0.00', subsidio: '0.00', compensaciones: '0.00', total,
  capturado: false, nota: '', factor: '', meses_recargo: 0,
});

let cuerpos: Record<string, unknown>[] = [];

beforeEach(() => {
  cleanup();
  cuerpos = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string, init: RequestInit = {}) => {
    const cuerpo = JSON.parse(String(init.body));
    cuerpos.push({ url, ...cuerpo });
    return Response.json({
      exito: true, anio: 2026, mes: 1, fecha_limite: '2026-02-17', fecha_pago: cuerpo.fecha_pago,
      renglones: [renglon('iva_a_cargo', 'IVA a cargo', '1600.00'),
        renglon('ret_isr_salarios', 'ISR retenido por salarios', '500.00')],
      totales: { importe_sistema: '2100.00', importe_a_pagar: '2100.00', actualizacion: '0.00',
        recargos: '0.00', subsidio: '0.00', compensaciones: '0.00', total: '2100.00' },
      total_a_pagar_ajustado: '2100.00', notas: ['Nota de prueba'],
    });
  }));
});

describe('ResumenImpuestosTab', () => {
  it('pide el resumen del cliente activo con fecha de pago y capturas', async () => {
    render(<ResumenImpuestosTab />);
    fireEvent.change(screen.getByLabelText('Fecha de pago'), { target: { value: '2026-08-10' } });
    fireEvent.click(screen.getByRole('button', { name: /Calcular/ }));
    await waitFor(() => expect(screen.getByText('IVA a cargo')).toBeTruthy());
    expect(String(cuerpos[0].url)).toContain('/api/v1/impuestos/clientes/taller/resumen');
    expect(cuerpos[0]).toMatchObject({ fecha_pago: '2026-08-10', formato: 'json' });
    expect(screen.getByTestId('total-ajustado').textContent).toBe('2100.00');
    expect(screen.getByText('Nota de prueba')).toBeTruthy();

    fireEvent.change(screen.getByLabelText('Compensaciones iva_a_cargo'), { target: { value: '100' } });
    fireEvent.change(screen.getByLabelText('Subsidio ret_isr_salarios'), { target: { value: '50' } });
    fireEvent.click(screen.getByRole('button', { name: /Calcular/ }));
    await waitFor(() => expect(cuerpos.length).toBe(2));
    expect(cuerpos[1].capturas).toEqual({
      iva_a_cargo: { compensaciones: '100' }, ret_isr_salarios: { subsidio: '50' },
    });
    // El subsidio sólo se captura en salarios.
    expect(screen.queryByLabelText('Subsidio iva_a_cargo')).toBeNull();
    expect(screen.getByRole('button', { name: /Excel/ })).toBeTruthy();
    expect(screen.getByRole('button', { name: /PDF/ })).toBeTruthy();
  });
});
