/**
 * La cartera va SIEMPRE por la API. (R-07 → P0-01)
 *
 * Reemplaza a `carteraFirestore.test.ts`, `carteraBackend.test.ts` y al test del
 * despachador: ya no hay dos dueños del dato ni interruptor. Los mismos criterios que
 * aquellos medían —vacía es escribible, un fallo se dice y no se sustituye por datos
 * ajenos, la lectura no se cuelga, el periodo se refresca, el uid no viaja— se miden
 * aquí contra la API con `fetch` stubbeado.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('./firebase', () => ({
  auth: { currentUser: { uid: 'uid-1', getIdToken: async () => 'token-1' } },
  db: {},
  default: {},
}));

const PERIODO_VIVO = { inicio: '2026-09-01', fin: '2026-09-15', fecha_pago: '2026-09-15' };
const PERIODO_GUARDADO = { inicio: '2026-08-16', fin: '2026-08-31', fecha_pago: '2026-08-31' };

const obtenerPeriodoSugerido = vi.fn();
vi.mock('./despachoApi', () => ({
  obtenerPeriodoSugerido: (clave: string) => obtenerPeriodoSugerido(clave),
  obtenerClientes: async () => [],
  obtenerCliente: async () => ({}),
}));

const {
  cargarCartera, guardarCliente, borrarCliente, guardarEmpleado, borrarEmpleado,
} = await import('./cartera');

const CLIENTE = {
  id: 'mio', nombre: 'Cliente Propio', giro: 'G', origen: 'propio',
  prima_riesgo: '0.005', clase_riesgo: null, clave_periodicidad: '04', zona: 'general',
  periodo_sugerido: PERIODO_GUARDADO,
};
const EMPLEADO = { empleado_no: 'E-01', nombre: 'ANA', employee_no: '7' };
const ILEGIBLE = { empleado_no: 'E-99', nombre: 'BETO', razon: 'nss: debe tener 11 dígitos' };

interface Peticion { url: string; method: string; body?: string; auth?: string }
const peticiones: Peticion[] = [];

function responder(cuerpoPara: (url: string) => unknown, status = 200) {
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    const headers = (init?.headers ?? {}) as Record<string, string>;
    peticiones.push({
      url, method: init?.method ?? 'GET', body: init?.body as string, auth: headers.Authorization,
    });
    return new Response(JSON.stringify(cuerpoPara(url)), {
      status, headers: { 'Content-Type': 'application/json' },
    });
  }));
}

beforeEach(() => {
  peticiones.length = 0;
  obtenerPeriodoSugerido.mockReset();
  obtenerPeriodoSugerido.mockImplementation(async (clave: string) => ({
    clave_periodicidad: clave, periodo: PERIODO_VIVO, dias_naturales: 15,
  }));
  responder((url) =>
    url.endsWith('/empleados')
      ? { empleados: [EMPLEADO], ilegibles: ['E-99'], ilegibles_detalle: [ILEGIBLE] }
      : { clientes: [CLIENTE] },
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe('cargarCartera', () => {
  it('lee clientes y plantillas de la API, con el token', async () => {
    const r = await cargarCartera('uid-1');

    expect(r.error).toBeNull();
    expect(r.origen).toBe('propia');
    expect(r.clientes.map((c) => c.id)).toEqual(['mio']);
    expect(r.clientes[0].empleados).toEqual([EMPLEADO]);
    expect(peticiones.map((p) => p.url)).toEqual([
      'http://localhost:8000/api/v1/cartera/clientes',
      'http://localhost:8000/api/v1/cartera/clientes/mio/empleados',
    ]);
    expect(peticiones.every((p) => p.auth === 'Bearer token-1')).toBe(true);
  });

  it('trae los ilegibles CON su razón para la ficha (R-10)', async () => {
    const r = await cargarCartera('uid-1');
    expect(r.clientes[0].ilegibles).toEqual([ILEGIBLE]);
  });

  it('una cartera vacía es vacía y ESCRIBIBLE, no un error', async () => {
    responder(() => ({ clientes: [] }));
    const r = await cargarCartera('uid-1');
    expect(r).toEqual({ clientes: [], origen: 'propia', error: null });
  });

  it('sin sesión devuelve vacío escribible sin pedir nada', async () => {
    const r = await cargarCartera(null);
    expect(r).toEqual({ clientes: [], origen: 'propia', error: null });
    expect(peticiones).toEqual([]);
  });

  it('un fallo de la API se DICE y no se sustituye por datos de otra persona', async () => {
    responder(() => ({ exito: false, error: 'boom' }), 500);
    const r = await cargarCartera('uid-1');
    expect(r.clientes).toEqual([]);
    expect(r.error).toContain('No se pudo leer tu cartera');
    expect(r.origen).toBe('propia');
  });

  it('si la API se cuelga, la cota la rescata (nunca spinner eterno)', async () => {
    vi.useFakeTimers();
    vi.stubGlobal('fetch', vi.fn((_url: string, init?: RequestInit) =>
      new Promise((_, rechazar) => {
        init?.signal?.addEventListener('abort', () =>
          rechazar(new DOMException('abortado', 'AbortError')));
      })));

    const promesa = cargarCartera('uid-1');
    await vi.advanceTimersByTimeAsync(9000);
    const r = await promesa;

    expect(r.error).toContain('tardó demasiado');
    expect(r.clientes).toEqual([]);
  });
});

describe('cargarCartera · el periodo se REFRESCA, no se sirve del snapshot', () => {
  it('devuelve el periodo vivo de su periodicidad, no el guardado', async () => {
    const r = await cargarCartera('uid-1');
    expect(obtenerPeriodoSugerido).toHaveBeenCalledWith('04');
    expect(r.clientes[0].periodo_sugerido).toEqual(PERIODO_VIVO);
  });

  it('pide UNA vez por clave, no una por cliente', async () => {
    responder((url) =>
      url.endsWith('/empleados')
        ? { empleados: [] }
        : {
            clientes: [
              { ...CLIENTE, id: 'a' },
              { ...CLIENTE, id: 'b' },
              { ...CLIENTE, id: 'c', clave_periodicidad: '05' },
            ],
          },
    );
    await cargarCartera('uid-1');
    expect(obtenerPeriodoSugerido).toHaveBeenCalledTimes(2);
  });

  it('si el periodo no se puede pedir, conserva el snapshot', async () => {
    obtenerPeriodoSugerido.mockRejectedValue(new Error('422 sin tarifa'));
    const r = await cargarCartera('uid-1');
    expect(r.error).toBeNull();
    expect(r.clientes[0].periodo_sugerido).toEqual(PERIODO_GUARDADO);
  });
});

describe('escrituras: verbo, ruta, cuerpo y token', () => {
  const ultima = () => peticiones[peticiones.length - 1];

  it('guardarCliente hace PUT sin plantilla ni ilegibles en el cuerpo', async () => {
    await guardarCliente({ ...CLIENTE, empleados: [EMPLEADO], ilegibles: [ILEGIBLE] } as never);
    const p = ultima();
    expect(p.method).toBe('PUT');
    expect(p.url).toBe('http://localhost:8000/api/v1/cartera/clientes/mio');
    const cuerpo = JSON.parse(p.body!);
    expect(cuerpo.id).toBe('mio');
    expect(cuerpo).not.toHaveProperty('empleados');
    expect(cuerpo).not.toHaveProperty('ilegibles');
    expect(p.auth).toBe('Bearer token-1');
  });

  it('borrarCliente hace DELETE', async () => {
    await borrarCliente('mio');
    expect(ultima()).toMatchObject({
      method: 'DELETE', url: 'http://localhost:8000/api/v1/cartera/clientes/mio',
    });
  });

  it('guardarEmpleado hace PUT a la llave del cálculo', async () => {
    await guardarEmpleado('mio', EMPLEADO as never);
    expect(ultima().method).toBe('PUT');
    expect(ultima().url).toContain('/cartera/clientes/mio/empleados/E-01');
    expect(JSON.parse(ultima().body!).empleado_no).toBe('E-01');
  });

  it('borrarEmpleado hace DELETE', async () => {
    await borrarEmpleado('mio', 'E-01');
    expect(ultima().method).toBe('DELETE');
    expect(ultima().url).toContain('/cartera/clientes/mio/empleados/E-01');
  });

  it('los ids se codifican en la URL', async () => {
    await borrarEmpleado('mi cliente', 'E/01');
    expect(ultima().url).toContain('/cartera/clientes/mi%20cliente/empleados/E%2F01');
  });

  it('el uid NO viaja en la URL ni en el cuerpo: lo resuelve el token', async () => {
    await guardarCliente(CLIENTE as never);
    await guardarEmpleado('mio', EMPLEADO as never);
    for (const p of peticiones) {
      expect(p.url).not.toContain('uid-1');
      expect(p.body ?? '').not.toContain('uid-1');
    }
  });

  it('un rechazo del backend llega como Error con su mensaje', async () => {
    responder(() => ({ exito: false, error: 'La prima de riesgo está fuera del Art. 72' }), 422);
    await expect(guardarCliente(CLIENTE as never)).rejects.toThrow(/Art\. 72/);
  });
});
