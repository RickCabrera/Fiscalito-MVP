/**
 * El cliente del CRUD con el backend como dueño. (R-07)
 *
 * POR QUÉ ESTE ARCHIVO EXISTE
 * ---------------------------
 * `cartera.test.ts` compara las dos implementaciones por identidad y aridad;
 * `contratoRutas.test.ts` fija que las URLs existan en el backend. Ninguno mide
 * **comportamiento**, y un revisor lo señaló dos veces.
 *
 * El caso que más importa es el refresco del periodo: es el único arreglo de
 * R-07 que toca directamente la costura con el motor, y era el que quedó sin
 * guarda.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('./firebase', () => ({
  auth: { currentUser: { uid: 'uid-1', getIdToken: async () => 'token' } },
  db: {},
  default: {},
}));

/**
 * El periodo que devuelve el catálogo del backend al refrescar. Distinto del
 * guardado, que es lo que permite ver cuál ganó.
 */
const PERIODO_VIVO = { inicio: '2026-09-01', fin: '2026-09-15', fecha_pago: '2026-09-15' };
const PERIODO_GUARDADO = { inicio: '2026-08-16', fin: '2026-08-31', fecha_pago: '2026-08-31' };

vi.mock('./despachoApi', () => ({
  obtenerCliente: async () => ({ periodo_sugerido: PERIODO_VIVO }),
  obtenerClientes: async () => [],
  // O-03: `conPeriodoAlDia` —que este módulo reusa— pide el periodo por
  // periodicidad, y ya no copia la quincena del cliente `demo` a todos.
  obtenerPeriodoSugerido: async (clave: string) => ({
    clave_periodicidad: clave,
    periodo: PERIODO_VIVO,
    dias_naturales: 16,
  }),
}));

const { cargarCartera, guardarEmpleado, borrarCliente } = await import('./carteraBackend');

const CLIENTE_GUARDADO = {
  id: 'mio', nombre: 'Cliente Propio', giro: 'G', origen: 'propio',
  prima_riesgo: '0.005', clase_riesgo: null, clave_periodicidad: '04', zona: 'general',
  periodo_sugerido: PERIODO_GUARDADO,
};

const peticiones: { url: string; method: string; body?: string }[] = [];

beforeEach(() => {
  peticiones.length = 0;
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    peticiones.push({ url, method: init?.method ?? 'GET', body: init?.body as string });
    const cuerpo = url.includes('/empleados')
      ? { empleados: [] }
      : url.includes('/cartera/clientes')
        ? { clientes: [CLIENTE_GUARDADO] }
        : {};
    return new Response(JSON.stringify(cuerpo), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });
  }));
});

afterEach(() => { vi.unstubAllGlobals(); });

describe('cargarCartera · el periodo se REFRESCA, no se sirve del snapshot', () => {
  it('devuelve el periodo vivo, no el guardado en Firestore', async () => {
    /**
     * LA COSTURA CON EL MOTOR. `periodo_sugerido` alimenta la `fecha_pago` que
     * va al cálculo, y de ella dependen UMA, salario mínimo, la tarifa del
     * Anexo 8 y el transitorio de enero del subsidio (§D18).
     *
     * El camino de Firestore refresca el periodo al leer —su docstring explica
     * que un snapshot deja a cada cliente con una quincena vencida dos semanas
     * después de sembrar—. El camino del backend devolvía el snapshot y nadie
     * lo notaba: quitar el refresco dejaba las 468 pruebas en verde.
     */
    const r = await cargarCartera('uid-1');

    expect(r.clientes).toHaveLength(1);
    expect(r.clientes[0].periodo_sugerido.inicio).toBe(PERIODO_VIVO.inicio);
    expect(r.clientes[0].periodo_sugerido.inicio).not.toBe(PERIODO_GUARDADO.inicio);
  });

  it('nunca lanza: un fallo vuelve como error, no como excepción', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('{}', { status: 500 })));

    const r = await cargarCartera('uid-1');
    expect(r.clientes).toEqual([]);
    expect(r.error).toContain('No se pudo leer tu cartera');
  });

  it('sin sesión devuelve vacío ESCRIBIBLE, sin pedir nada', async () => {
    // Misma semántica que fijó R-06: vacía es vacía, y `origen: firestore` es lo
    // que hace que el botón de alta funcione.
    const r = await cargarCartera(null);
    expect(r).toEqual({ clientes: [], origen: 'firestore', error: null });
    expect(peticiones).toEqual([]);
  });
});

describe('las escrituras mandan el token y el verbo correcto', () => {
  it('guardarEmpleado hace PUT con el empleado en el cuerpo', async () => {
    await guardarEmpleado('uid-1', 'mio', { empleado_no: 'E-01', nombre: 'ANA' } as never);

    // `.at()` no está en el target de tsconfig del proyecto; se indexa.
    const p = peticiones[peticiones.length - 1];
    expect(p.method).toBe('PUT');
    expect(p.url).toContain('/cartera/clientes/mio/empleados/E-01');
    expect(JSON.parse(p.body!).empleado_no).toBe('E-01');
  });

  it('borrarCliente hace DELETE', async () => {
    await borrarCliente('uid-1', 'mio');
    expect(peticiones[peticiones.length - 1].method).toBe('DELETE');
  });

  it('el uid NO viaja en la URL ni en el cuerpo: lo resuelve el token', async () => {
    // Si viajara, el backend podría creerle al navegador de quién es la cartera.
    await guardarEmpleado('uid-1', 'mio', { empleado_no: 'E-01' } as never);

    // `.at()` no está en el target de tsconfig del proyecto; se indexa.
    const p = peticiones[peticiones.length - 1];
    expect(p.url).not.toContain('uid-1');
    expect(p.body).not.toContain('uid-1');
  });
});
