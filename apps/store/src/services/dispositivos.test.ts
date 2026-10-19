/**
 * Los dispositivos van por la API, no por Firestore. (R-09 → P0-01)
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('./firebase', () => ({
  auth: { currentUser: { uid: 'uid-1', getIdToken: async () => 'token-1' } },
  db: {},
  default: {},
}));

const { listarDispositivos, guardarDispositivo, borrarDispositivo } = await import('./dispositivos');
const { dispositivoVacio } = await import('./dispositivosApi');

const BASE = 'http://localhost:8000/api/v1/cartera/clientes/taller/dispositivos';
const peticiones: { url: string; method: string; body?: string; auth?: string }[] = [];

beforeEach(() => {
  peticiones.length = 0;
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    const headers = (init?.headers ?? {}) as Record<string, string>;
    peticiones.push({
      url, method: init?.method ?? 'GET', body: init?.body as string, auth: headers.Authorization,
    });
    const cuerpo = init?.method === 'POST'
      ? { id: 'nuevo-id' }
      : { dispositivos: [{ ...dispositivoVacio(), id: 'd1', nombre: 'Entrada' }] };
    return new Response(JSON.stringify(cuerpo), {
      status: init?.method === 'POST' ? 201 : 200,
      headers: { 'Content-Type': 'application/json' },
    });
  }));
});

afterEach(() => { vi.unstubAllGlobals(); });

describe('dispositivos por la API', () => {
  it('lista con GET y el token', async () => {
    const r = await listarDispositivos('taller');
    expect(r.map((d) => d.id)).toEqual(['d1']);
    expect(peticiones[0]).toMatchObject({ url: BASE, method: 'GET', auth: 'Bearer token-1' });
  });

  it('el alta (sin id) hace POST y devuelve el id que genera el backend', async () => {
    const id = await guardarDispositivo('taller', { ...dispositivoVacio(), nombre: 'Entrada' });
    expect(id).toBe('nuevo-id');
    expect(peticiones[0]).toMatchObject({ url: BASE, method: 'POST' });
    const cuerpo = JSON.parse(peticiones[0].body!);
    expect(cuerpo).not.toHaveProperty('id');
    expect(cuerpo.nombre).toBe('Entrada');
  });

  it('la edición (con id) hace PUT a ese id y conserva el id', async () => {
    const id = await guardarDispositivo('taller', { ...dispositivoVacio(), id: 'd1', nombre: 'X' });
    expect(id).toBe('d1');
    expect(peticiones[0]).toMatchObject({ url: `${BASE}/d1`, method: 'PUT' });
    expect(JSON.parse(peticiones[0].body!)).not.toHaveProperty('id');
  });

  it('la baja hace DELETE', async () => {
    await borrarDispositivo('taller', 'd1');
    expect(peticiones[0]).toMatchObject({ url: `${BASE}/d1`, method: 'DELETE' });
  });

  it('un rechazo del backend llega como Error', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(
      JSON.stringify({ exito: false, error: 'Ya hay otro dispositivo con el serial S1.' }),
      { status: 422, headers: { 'Content-Type': 'application/json' } },
    )));
    await expect(
      guardarDispositivo('taller', { ...dispositivoVacio(), nombre: 'X', serial: 'S1' }),
    ).rejects.toThrow(/serial S1/);
  });
});
