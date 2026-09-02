/**
 * Cada URL que el front construye existe en el backend.
 *
 * POR QUÉ EXISTE
 * --------------
 * El 2026-09-02 el calendario patronal dio 404 en el navegador. El diagnóstico
 * fue que la API que respondía era de antes del merge que agregó la ruta — no un
 * bug de path—, pero el episodio dejó ver un agujero real: **las dos mitades del
 * contrato se prueban por separado y ninguna las compara**. El test de backend
 * de E-07 pega al router montado pero *hardcodea* la ruta; los tests de pantalla
 * stubbean `fetch` y aceptan cualquier URL. Un front que pidiera
 * `/api/v1/despacho/calendario-patronal` tendría las dos suites en verde.
 *
 * CÓMO LO PRUEBA, Y POR QUÉ ASÍ
 * -----------------------------
 * Llama a la función **de verdad** con `fetch` stubbeado y captura la URL que
 * armó. No hay regex sobre el código: si `obtenerCalendarioPatronal` construye
 * su path con una plantilla, una variable o tres helpers encadenados, aquí se ve
 * el resultado, que es lo único que le llega al servidor.
 *
 * La lista contra la que se compara es `rutasBackend.json`, generado desde
 * `app.main:app` por `apps/api/scripts/exportar_rutas.py` y vigilado por
 * `apps/api/tests/test_rutas_publicadas.py` para que no envejezca.
 *
 * LOS CONTEOS POR MÓDULO NO SON ADORNO
 * ------------------------------------
 * Una cobertura PARCIAL es invisible: si este archivo dejara de ejercitar tres
 * funciones, seguiría verde declarando que el contrato está verificado. Por eso
 * cada módulo afirma cuántas de sus funciones llaman al backend. Agregar una sin
 * agregarla aquí rompe el test, que es exactamente lo que se quiere.
 */

import { describe, expect, it, vi } from 'vitest';
import rutasBackend from './rutasBackend.json';
import * as despachoApi from './despachoApi';
import * as nominaDemoApi from './nominaDemoApi';
import * as fiscalAgentApi from './fiscalAgentApi';
import type { ClienteDetalle } from './despachoApi';

// ── El contrato ──

interface RutaBackend {
  path: string;
  metodos: string[];
}

const RUTAS: RutaBackend[] = rutasBackend.rutas;

/**
 * `/api/v1/despacho/clientes/{cliente_id}` ← la forma que declara FastAPI.
 * Un path concreto (`/api/v1/despacho/clientes/demo`) tiene que casar con ella,
 * así que se compara segmento a segmento y `{...}` acepta cualquier cosa.
 */
function coincide(patron: string, concreto: string): boolean {
  const a = patron.split('/');
  const b = concreto.split('/');
  if (a.length !== b.length) return false;
  return a.every((seg, i) => (seg.startsWith('{') && seg.endsWith('}') ? b[i] !== '' : seg === b[i]));
}

function rutaQueAtiende(path: string): RutaBackend | undefined {
  // Los literales primero: `/clientes/{id}` no debe robarse una ruta exacta.
  return RUTAS.find((r) => r.path === path) ?? RUTAS.find((r) => coincide(r.path, path));
}

// ── Captura de la llamada real ──

interface Llamada {
  path: string;
  metodo: string;
}

/**
 * Corre `accion` con `fetch` stubbeado y devuelve la petición que salió.
 *
 * La respuesta es un 200 con `{}`: a estas funciones se les mide la URL, no lo
 * que hacen con el cuerpo. Si alguna revienta al leer un campo ausente, no
 * importa — la URL ya se capturó, y por eso el `catch` se traga el error en vez
 * de obligar a construir una respuesta válida por endpoint.
 */
async function urlDe(accion: () => Promise<unknown>): Promise<Llamada> {
  let capturada: Llamada | null = null;

  vi.stubGlobal(
    'fetch',
    vi.fn(async (entrada: string, opciones?: RequestInit) => {
      capturada = {
        path: new URL(entrada).pathname,
        metodo: (opciones?.method ?? 'GET').toUpperCase(),
      };
      return new Response('{}', { status: 200, headers: { 'Content-Type': 'application/json' } });
    }),
  );

  await accion().catch(() => undefined);

  if (capturada === null) throw new Error('La función no llamó a fetch.');
  return capturada;
}

// ── Qué se ejercita, por módulo ──

/** Una ficha mínima: `calcularNomina` la lee para armar el cuerpo, no la URL. */
const FICHA_VACIA = {
  prima_riesgo: '0.0113065',
  clave_periodicidad: '04',
  empleados: [],
} as unknown as ClienteDetalle;

const LLAMADAS: Record<string, Record<string, () => Promise<unknown>>> = {
  'despachoApi.ts': {
    obtenerClientes: () => despachoApi.obtenerClientes(),
    obtenerCliente: () => despachoApi.obtenerCliente('demo'),
    obtenerCalendarioPatronal: () => despachoApi.obtenerCalendarioPatronal(2026),
  },
  'nominaDemoApi.ts': {
    obtenerPlantillaDemo: () => nominaDemoApi.obtenerPlantillaDemo('demo'),
    obtenerEventos: () => nominaDemoApi.obtenerEventos('demo'),
    cerrarPeriodo: () =>
      nominaDemoApi.cerrarPeriodo('demo', ['E-01'], { inicio: '2026-08-16', fin: '2026-08-31' }),
    calcularNomina: () =>
      nominaDemoApi.calcularNomina(
        'demo',
        { inicio: '2026-08-16', fin: '2026-08-31', fecha_pago: null },
        [],
        FICHA_VACIA,
      ),
  },
  'fiscalAgentApi.ts': {
    healthCheck: () => fiscalAgentApi.healthCheck(),
    calcularPreDeclaracion: () => fiscalAgentApi.calcularPreDeclaracion({} as never),
    calcularPreDeclaracionAnual: () => fiscalAgentApi.calcularPreDeclaracionAnual({} as never),
    calcularDeduccionesPersonales: () =>
      fiscalAgentApi.calcularDeduccionesPersonales({} as never),
    obtenerCalendario: () => fiscalAgentApi.obtenerCalendario({} as never),
    compararRegimenes: () => fiscalAgentApi.compararRegimenes({} as never),
    generarDIOT: () => fiscalAgentApi.generarDIOT({} as never),
    obtenerRetencionesTerceros: () => fiscalAgentApi.obtenerRetencionesTerceros({} as never),
    calcularMultiPeriodo: () => fiscalAgentApi.calcularMultiPeriodo({} as never),
    obtenerEstadoCuenta: () => fiscalAgentApi.obtenerEstadoCuenta({} as never),
    llamarAgentePreDeclaracion: () => fiscalAgentApi.llamarAgentePreDeclaracion({} as never),
  },
};

/**
 * Cuántas funciones de cada módulo pegan al backend HOY.
 *
 * Si agregas una y no la pones arriba, este número deja de cuadrar y el test
 * falla. Ese es el único mecanismo que impide que la cobertura se degrade en
 * silencio, que es como se ve un test de contrato podrido.
 */
const ESPERADAS: Record<string, number> = {
  'despachoApi.ts': 3,
  'nominaDemoApi.ts': 4,
  'fiscalAgentApi.ts': 11,
};

// ── Los tests ──

describe('contrato de rutas front ↔ backend', () => {
  it('el JSON de rutas del backend está presente y no está vacío', () => {
    expect(RUTAS.length).toBeGreaterThanOrEqual(15);
  });

  for (const [modulo, funciones] of Object.entries(LLAMADAS)) {
    describe(modulo, () => {
      it(`ejercita las ${ESPERADAS[modulo]} funciones que pegan al backend`, () => {
        expect(Object.keys(funciones)).toHaveLength(ESPERADAS[modulo]);
      });

      for (const [nombre, llamar] of Object.entries(funciones)) {
        it(`${nombre} pide una ruta que el backend publica`, async () => {
          const { path, metodo } = await urlDe(llamar);
          const ruta = rutaQueAtiende(path);

          expect(
            ruta,
            `${nombre} pide ${path}, que el backend NO publica. ` +
              'O el path del front está mal, o la ruta se movió y hay que ' +
              'regenerar rutasBackend.json (ver apps/api/scripts/exportar_rutas.py).',
          ).toBeDefined();

          expect(
            ruta!.metodos,
            `${nombre} usa ${metodo} contra ${path}, que sólo acepta ${ruta!.metodos.join(', ')}.`,
          ).toContain(metodo);
        });
      }
    });
  }

  it('el calendario patronal pide exactamente la ruta que el backend publica', async () => {
    // El caso del 2026-09-02, anclado en el lado del front.
    const { path, metodo } = await urlDe(() => despachoApi.obtenerCalendarioPatronal(2026));
    expect(path).toBe('/api/v1/despacho/calendario');
    expect(metodo).toBe('GET');
  });
});
