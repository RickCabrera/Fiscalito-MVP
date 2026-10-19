/**
 * `EstadoTrabajos` (P0-04): lista, polling mientras hay algo vivo, y reintento.
 *
 * Se stubbea `fetch` (no el módulo de servicio) para medir también la URL que sale.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { Trabajo } from '../../services/trabajosApi';

vi.mock('../../services/firebase', () => ({
  auth: { currentUser: { uid: 'uid-1', getIdToken: async () => 'tok' } },
  db: {},
  default: {},
}));

const { default: EstadoTrabajos } = await import('./EstadoTrabajos');

function trabajo(parcial: Partial<Trabajo>): Trabajo {
  return {
    id: 1, tipo: 'diagnostico.cliente', estado: 'hecho', cliente: 'taller', intentos: 1,
    max_intentos: 5, ejecutar_en: '2026-10-19T15:00:00Z', iniciado_en: null,
    terminado_en: '2026-10-19T15:00:05Z', creado_en: '2026-10-19T15:00:00Z', error: null,
    resultado: { empleados: 3 }, carga: {}, ...parcial,
  };
}

let respuestas: Trabajo[][] = [];
let llamadas: Array<{ url: string; metodo: string }> = [];

beforeEach(() => {
  llamadas = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string, op?: RequestInit) => {
    const metodo = (op?.method ?? 'GET').toUpperCase();
    llamadas.push({ url, metodo });
    if (metodo === 'POST') {
      return new Response(JSON.stringify({ exito: true, trabajo: trabajo({ estado: 'pendiente' }) }));
    }
    const lote = respuestas.length > 1 ? respuestas.shift()! : respuestas[0];
    return new Response(JSON.stringify({ exito: true, trabajos: lote }));
  }));
});

afterEach(() => { cleanup(); vi.useRealTimers(); });

describe('EstadoTrabajos', () => {
  it('pide los trabajos del cliente y pinta resultado', async () => {
    respuestas = [[trabajo({})]];
    render(<EstadoTrabajos cliente="taller" />);
    expect(await screen.findByText('Listo')).toBeTruthy();
    expect(screen.getByText('empleados: 3')).toBeTruthy();
    expect(llamadas[0].url).toContain('/api/v1/trabajos?cliente=taller');
  });

  it('sin trabajos lo dice', async () => {
    respuestas = [[]];
    render(<EstadoTrabajos cliente="taller" />);
    expect(await screen.findByText(/No hay procesos/)).toBeTruthy();
  });

  it('refresca mientras haya un pendiente y se detiene cuando termina', async () => {
    respuestas = [[trabajo({ estado: 'pendiente', resultado: null })], [trabajo({})]];
    render(<EstadoTrabajos cliente="taller" intervaloMs={20} />);
    expect(await screen.findByText('En cola')).toBeTruthy();
    expect(await screen.findByText('Listo')).toBeTruthy();
    const despues = llamadas.length;
    await act(async () => { await new Promise((r) => setTimeout(r, 80)); });
    expect(llamadas.length).toBe(despues);
  });

  it('un fallido muestra su error y se puede reintentar', async () => {
    respuestas = [[trabajo({ id: 9, estado: 'fallido', error: 'boom', resultado: null })]];
    render(<EstadoTrabajos cliente="taller" />);
    expect(await screen.findByText('boom')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Reintentar trabajo 9' }));
    await waitFor(() =>
      expect(llamadas.some((l) => l.metodo === 'POST' && l.url.endsWith('/trabajos/9/reintentar')))
        .toBe(true),
    );
  });

  it('un error del backend se ve en pantalla', async () => {
    vi.stubGlobal('fetch', vi.fn(async () =>
      new Response(JSON.stringify({ exito: false, error: 'No existe el cliente' }), { status: 404 })));
    render(<EstadoTrabajos cliente="otro" />);
    expect(await screen.findByText(/No existe el cliente/)).toBeTruthy();
  });
});
