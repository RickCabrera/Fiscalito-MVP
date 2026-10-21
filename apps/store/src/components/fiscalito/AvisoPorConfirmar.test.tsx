/**
 * O12: cuando el motor usó un índice o una tasa de fuente secundaria, la pantalla
 * lo dice (resumen de impuestos y calculadoras). El front no decide nada: pinta
 * `por_confirmar` y `fuentes_por_confirmar` tal como llegan.
 */

import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

vi.mock('../../services/firebase', () => ({
  auth: { currentUser: { uid: 'uid-1', getIdToken: async () => 'tk' } },
  db: {},
  default: {},
}));

const { default: AvisoPorConfirmar } = await import('./AvisoPorConfirmar');
const { fuentesPorConfirmar } = await import('./porConfirmar');
const { default: TablaResumen } = await import('./TablaResumen');
const { default: TarjetaCalculadora } = await import('../calculadoras/TarjetaCalculadora');
const { CALCULADORAS } = await import('../calculadoras/definiciones');

const FUENTE = 'INPC 2025-04 (139.620): tablas secundarias, sin cotejar con el boletín del INEGI';

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe('AvisoPorConfirmar', () => {
  it('no pinta nada sin fuentes y lista las que llegan', () => {
    const { container } = render(<AvisoPorConfirmar fuentes={[]} />);
    expect(container.innerHTML).toBe('');
    render(<AvisoPorConfirmar fuentes={[FUENTE]} />);
    expect(screen.getByRole('note', { name: 'Fuente por confirmar' }).textContent).toContain(FUENTE);
  });

  it('saca las fuentes de cualquier respuesta del motor', () => {
    expect(fuentesPorConfirmar({ por_confirmar: false, fuentes_por_confirmar: [FUENTE] })).toEqual([]);
    expect(fuentesPorConfirmar({ por_confirmar: true, fuentes_por_confirmar: [FUENTE] })).toEqual([FUENTE]);
    // ISN: trae `por_confirmar` y el fundamento, sin lista.
    expect(fuentesPorConfirmar({ por_confirmar: true, fundamento: 'FUENTE POR CONFIRMAR: ley' }))
      .toEqual(['FUENTE POR CONFIRMAR: ley']);
  });

  it('marca el renglón del resumen y el total', () => {
    const fila = {
      clave: 'iva_a_cargo', grupo: 'IVA', concepto: 'IVA a cargo', aplica: true,
      importe_sistema: '10000.00', importe_a_pagar: '10000.00', actualizacion: '64.00',
      recargos: '443.82', subsidio: '0.00', compensaciones: '0.00', total: '10507.82',
      capturado: false, nota: '', factor: '1.0064', meses_recargo: 3, por_confirmar: true,
    };
    render(<TablaResumen capturas={{}} onCapturar={() => undefined} resumen={{
      exito: true, anio: 2025, mes: 2, fecha_limite: '2025-03-17', fecha_pago: '2025-05-20',
      renglones: [fila, { ...fila, clave: 'isr_pm', concepto: 'ISR PM', por_confirmar: false }],
      totales: {}, total_a_pagar_ajustado: '10508.00', notas: [],
      por_confirmar: true, fuentes_por_confirmar: [FUENTE],
    }} />);
    expect(screen.getByTestId('por-confirmar-iva_a_cargo')).toBeTruthy();
    expect(screen.queryByTestId('por-confirmar-isr_pm')).toBeNull();
    expect(screen.getByRole('note').textContent).toContain(FUENTE);
  });

  it('la calculadora de actualización avisa cuando el motor lo marca', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => Response.json({
      exito: true, total: '10507.82', notas: [], por_confirmar: true, fuentes_por_confirmar: [FUENTE],
    })));
    const def = CALCULADORAS.find((c) => c.id === 'actualizacion-recargos');
    if (!def) throw new Error('falta la calculadora');
    render(<TarjetaCalculadora def={def} />);
    fireEvent.click(screen.getByRole('button', { name: /Calcular/ }));
    await waitFor(() => expect(screen.getByRole('note').textContent).toContain(FUENTE));
  });
});
