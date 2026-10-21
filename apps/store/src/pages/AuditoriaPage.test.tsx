/** Bitácora de auditoría (P0-07): carga, filtros y error de permisos. */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../services/firebase', () => ({
  auth: { currentUser: { uid: 'uid-1', getIdToken: async () => 'tok' } },
  db: {},
  default: {},
}));

const { default: AuditoriaPage } = await import('./AuditoriaPage');

const EVENTO = {
  id: 1, fecha: '2026-10-19T15:00:00Z', uid: 'uid-1', cliente: 'taller',
  accion: 'http.POST', entidad: 'ruta', entidad_id: '/api/v1/trabajos/1/cancelar',
  detalle: { status: 409 }, ip: '',
};

let urls: string[] = [];

beforeEach(() => {
  urls = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    urls.push(url);
    return new Response(JSON.stringify({ exito: true, eventos: [EVENTO], total: 1, pagina: 1, por_pagina: 50 }));
  }));
});

afterEach(cleanup);

function montar() {
  return render(<MemoryRouter><AuditoriaPage /></MemoryRouter>);
}

describe('AuditoriaPage', () => {
  it('pinta los renglones con usuario, cliente y acción', async () => {
    montar();
    expect(await screen.findByText('taller')).toBeTruthy();
    expect(screen.getByText('http.POST')).toBeTruthy();
    expect(screen.getByText('POST /api/v1/trabajos/1/cancelar (409)')).toBeTruthy();
    expect(urls[0]).toContain('/api/v1/auditoria?pagina=1&por_pagina=50');
  });

  it('los filtros viajan en la consulta', async () => {
    montar();
    await screen.findByText('taller');
    fireEvent.change(screen.getByLabelText('Cliente (clave)'), { target: { value: 'taller' } });
    fireEvent.change(screen.getByLabelText('Desde'), { target: { value: '2026-10-01' } });
    fireEvent.click(screen.getByRole('button', { name: 'Filtrar' }));
    await waitFor(() => expect(urls.length).toBe(2));
    expect(urls[1]).toContain('cliente=taller');
    expect(urls[1]).toContain('desde=2026-10-01');
    expect(urls[1]).not.toContain('usuario=');
  });

  it('un 403 se ve como error', async () => {
    vi.stubGlobal('fetch', vi.fn(async () =>
      new Response(JSON.stringify({ exito: false, error: 'Tu rol no permite esta acción.' }), { status: 403 })));
    montar();
    expect(await screen.findByText(/Tu rol no permite/)).toBeTruthy();
  });
});
