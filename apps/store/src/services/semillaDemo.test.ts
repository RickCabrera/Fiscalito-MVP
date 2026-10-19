/**
 * La siembra de demostración va por las MISMAS rutas que el alta a mano. (R-06 → P0-01)
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('./firebase', () => ({
  auth: { currentUser: { uid: 'uid-1', getIdToken: async () => 'token-1' } },
  db: {},
  default: {},
}));

const RESUMEN = {
  id: 'demo', nombre: 'Cliente Demo', giro: 'Servicios', origen: 'fixtures-s04',
  num_empleados: 1, prima_riesgo: '0.0054355', clase_riesgo: null,
  clave_periodicidad: '04', zona: 'general',
};
const EMPLEADO = { empleado_no: 'E-01', nombre: 'ANA' };

vi.mock('./despachoApi', () => ({
  obtenerClientes: async () => [RESUMEN],
  obtenerCliente: async () => ({ periodo_sugerido: { inicio: 'a', fin: 'b', fecha_pago: null } }),
}));
vi.mock('./carteraApi', () => ({
  obtenerEmpleadosSemilla: async () => ({ empleados: [EMPLEADO] }),
}));

const { sembrarDemo } = await import('./semillaDemo');

const escrituras: { url: string; body: unknown }[] = [];
let yaHay: unknown[] = [];

beforeEach(() => {
  escrituras.length = 0;
  yaHay = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === 'PUT') escrituras.push({ url, body: JSON.parse(init.body as string) });
    return new Response(JSON.stringify({ clientes: yaHay }), {
      status: 200, headers: { 'Content-Type': 'application/json' },
    });
  }));
});

afterEach(() => { vi.unstubAllGlobals(); });

describe('sembrarDemo', () => {
  it('no escribe nada si la cartera ya tiene clientes', async () => {
    yaHay = [{ id: 'mio' }];
    expect(await sembrarDemo()).toBe(false);
    expect(escrituras).toEqual([]);
  });

  it('da de alta cliente y empleados con PUT, sin la plantilla dentro del cliente', async () => {
    expect(await sembrarDemo()).toBe(true);
    expect(escrituras.map((e) => new URL(e.url).pathname)).toEqual([
      '/api/v1/cartera/clientes/demo',
      '/api/v1/cartera/clientes/demo/empleados/E-01',
    ]);
    expect(escrituras[0].body).not.toHaveProperty('empleados');
    expect((escrituras[0].body as { nombre: string }).nombre).toBe('Cliente Demo');
  });
});
