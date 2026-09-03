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
 * LA COBERTURA SE MIDE CONTRA EL MÓDULO, NO CONTRA UN NÚMERO
 * ----------------------------------------------------------
 * Una cobertura PARCIAL es invisible: si este archivo dejara de ejercitar tres
 * funciones, seguiría verde declarando que el contrato está verificado. Por eso
 * la lista de llamadas se compara contra los **exports reales** de cada módulo
 * (menos una lista explícita de helpers puros). Un conteo escrito a mano no
 * sirve: sería otro literal del mismo archivo, y agregar una función sin
 * registrarla pasaría en verde.
 *
 * LÍMITE CONOCIDO
 * ---------------
 * `coincide` acepta cualquier segmento no vacío donde el backend declara un
 * `{param}`, así que un bug que produjera `/despacho/clientes/undefined` pasaría
 * este contrato. Aquí se verifica que la RUTA exista, no que el argumento sea
 * sensato; eso le toca a los tests de la pantalla que la llama.
 */

import { describe, expect, it, vi } from 'vitest';
import rutasBackend from './rutasBackend.json';
/**
 * R-07: `carteraBackend` pide el ID token ANTES de llamar a `fetch`, así que sin
 * sesión no llega a construir ninguna URL y este archivo no podría medirla.
 *
 * El doble también resuelve el otro problema: `services/firebase.ts` llama a
 * `getAuth()` al importarse y eso **lanza sin las llaves de Firebase** — local
 * verde, CI rojo. Ver `sinLlavesDeFirebase.test.ts`.
 */
vi.mock('./firebase', () => ({
  auth: { currentUser: { uid: 'uid-1', getIdToken: async () => 'token-de-prueba' } },
  db: {},
  default: {},
}));

import * as despachoApi from './despachoApi';
import * as nominaDemoApi from './nominaDemoApi';
import * as fiscalAgentApi from './fiscalAgentApi';
import * as carteraApi from './carteraApi';
// R-07: el cliente del CRUD con el backend como dueño. Un revisor lo encontró
// AUSENTE de este archivo — un módulo entero con cinco funciones que pegan al
// backend entró por debajo del test que existe para impedir exactamente eso.
import * as carteraBackend from './carteraBackend';
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
  /** La URL completa: hace falta para anclar QUERY PARAMS, no sólo rutas (O-01). */
  url: string;
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
        url: entrada,
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
    // O-01: se ejercita con `empresa_unica=true`, que es el modo por default de
    // la app. La RUTA es la misma en los dos modos; el query param lo ancla su
    // propio caso al final del archivo, porque este barrido mide cobertura de
    // exports —una entrada por función— y no valores de parámetros.
    obtenerCalendarioPatronal: () => despachoApi.obtenerCalendarioPatronal(2026, true),
    // O-03: el periodo que la app propone sale del backend, por periodicidad.
    // Antes se copiaba la quincena del cliente `demo` a todos.
    obtenerPeriodoSugerido: () => despachoApi.obtenerPeriodoSugerido('05'),
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
        [],
      ),
  },
  'carteraBackend.ts': {
    cargarCartera: () => carteraBackend.cargarCartera('uid-1'),
    guardarCliente: () =>
      carteraBackend.guardarCliente('uid-1', { id: 'mio' } as never),
    borrarCliente: () => carteraBackend.borrarCliente('uid-1', 'mio'),
    guardarEmpleado: () =>
      carteraBackend.guardarEmpleado('uid-1', 'mio', { empleado_no: 'E-01' } as never),
    borrarEmpleado: () => carteraBackend.borrarEmpleado('uid-1', 'mio', 'E-01'),
  },
  'carteraApi.ts': {
    obtenerEmpleadosSemilla: () => carteraApi.obtenerEmpleadosSemilla('demo'),
    integrarSBC: () => carteraApi.integrarSBC({ salario_diario: '500.00', fecha: '2026-09-01' }),
    obtenerPrimasDeRiesgo: () => carteraApi.obtenerPrimasDeRiesgo('2026-09-01'),
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
 * Los módulos de verdad, para contar sus exports en tiempo de test.
 *
 * Contra un número escrito a mano, esto es lo que hace la guarda REAL: un
 * literal `ESPERADAS: {'despachoApi.ts': 3}` y la lista `LLAMADAS` son dos
 * literales del mismo archivo, así que nada obliga a que reflejen el módulo.
 * Agregar `obtenerLoQueSea()` a `despachoApi.ts` sin registrarla aquí pasaba en
 * verde — o sea, exactamente la degradación silenciosa que este test viene a
 * impedir. Ahora la lista se compara contra los exports reales.
 */
const MODULOS: Record<string, Record<string, unknown>> = {
  'despachoApi.ts': despachoApi,
  'nominaDemoApi.ts': nominaDemoApi,
  'fiscalAgentApi.ts': fiscalAgentApi,
  'carteraApi.ts': carteraApi,
  'carteraBackend.ts': carteraBackend,
};

/**
 * Funciones exportadas que NO pegan al backend: formateo y mapeo puros.
 *
 * Es una lista explícita y corta a propósito. Cualquier export nuevo se
 * considera candidato a llamar al backend hasta que alguien lo declare aquí, y
 * declararlo obliga a mirarlo. Lo contrario —una heurística por nombre— dejaría
 * pasar la función que sí pega.
 */
const HELPERS_PUROS = new Set([
  'etiquetaOrigen',
  'primaComoPorcentaje',
  'tipoParaApi',
  'tipoParaCalendario',
  'estaVinculado',
  'contarSinVincular',
]);

/**
 * Exenciones **por módulo**, no por nombre.
 *
 * `HELPERS_PUROS` es global, así que eximir `sembrarDemo` ahí lo eximía en
 * TODOS los módulos — y `carteraFirestore.sembrarDemo` **sí** pega al backend,
 * vía `carteraDelBackend`. Hoy no rompe nada porque ese módulo no está en
 * `MODULOS`, pero es exactamente la "heurística por nombre" que el docstring de
 * arriba rechaza, y el día que alguien agregue `carteraFirestore.ts` aquí, la
 * función que sí pega entraría exenta.
 */
const PUROS_POR_MODULO: Record<string, Set<string>> = {
  // Del backend LANZA a propósito: no existe ese endpoint, y darle uno que copia
  // salarios de terceros a la cuenta de quien llame sería la escalada que R-06
  // vino a cerrar.
  'carteraBackend.ts': new Set(['sembrarDemo']),
};

function funcionesQueDeberianPegar(
  modulo: Record<string, unknown>,
  nombreDelModulo = '',
): string[] {
  const propios = PUROS_POR_MODULO[nombreDelModulo] ?? new Set<string>();
  return Object.keys(modulo)
    .filter(
      (k) => typeof modulo[k] === 'function' && !HELPERS_PUROS.has(k) && !propios.has(k),
    )
    .sort();
}

// ── Los tests ──

describe('contrato de rutas front ↔ backend', () => {
  it('el JSON de rutas del backend está presente y no está vacío', () => {
    expect(RUTAS.length).toBeGreaterThanOrEqual(15);
  });

  for (const [modulo, funciones] of Object.entries(LLAMADAS)) {
    describe(modulo, () => {
      it('ejercita TODAS sus funciones que pegan al backend', () => {
        expect(
          Object.keys(funciones).sort(),
          `Hay funciones exportadas por ${modulo} que este test no ejercita. ` +
            'Agrégalas a LLAMADAS, o a HELPERS_PUROS si no llaman al backend. ' +
            'Una cobertura parcial es invisible: el test seguiría verde ' +
            'declarando que el contrato está verificado.',
        ).toEqual(funcionesQueDeberianPegar(MODULOS[modulo], modulo));
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
    const { path, metodo } = await urlDe(() =>
      despachoApi.obtenerCalendarioPatronal(2026, false),
    );
    expect(path).toBe('/api/v1/despacho/calendario');
    expect(metodo).toBe('GET');
  });

  /**
   * O-01. El query param **también** se ancla aquí.
   *
   * `empresa_unica` no es cosmético: decide si el backend hace fan-out sobre
   * los tres clientes del catálogo de demostración o devuelve un solo juego de
   * obligaciones. Si el front mandara un nombre que el backend no publica, el
   * parámetro se ignoraría en silencio y el calendario de la empresa saldría
   * triplicado con los nombres de tres clientes que no son suyos — un 200 que
   * miente, que es la forma exacta del defecto de X-01.
   */
  it('el calendario de la empresa única manda el query param que el backend publica', async () => {
    const { url } = await urlDe(() => despachoApi.obtenerCalendarioPatronal(2026, true));
    const params = new URL(url).searchParams;
    expect(params.get('empresa_unica')).toBe('true');
    expect(params.get('anio_de_las_cuotas')).toBe('2026');
  });
});
