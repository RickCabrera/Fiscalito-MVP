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
 * R-07/P0-01: `cartera` y `dispositivos` piden el ID token ANTES de llamar a `fetch`, así que sin
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
// P0-01: la cartera y los dispositivos van SIEMPRE por la API. Se registran aquí
// el mismo día que nacen: en R-07 un módulo entero de cartera entró por debajo de
// este test, que existe para impedir exactamente eso.
import * as cartera from './cartera';
import * as dispositivos from './dispositivos';
import * as semillaDemo from './semillaDemo';
// T4: el CFDI de nómina sin timbrar. Se registra el mismo día que nace.
import * as cfdiNominaApi from './cfdiNominaApi';
// P0-03: la bóveda de CFDI. Se registra el día que nace.
import * as bovedaApi from './bovedaApi';
import * as satDescargaApi from './satDescargaApi';
// P0-05: bóveda de e.firma y CSD. Se registra el día que nace.
import * as credencialesApi from './credencialesApi';
// P0-04 / P0-07: trabajos en segundo plano y bitácora de auditoría.
import * as trabajosApi from './trabajosApi';
// P1-03/04/05: estatus de CFDI, listas 69-B y opinión de cumplimiento.
import * as satVerificacionApi from './satVerificacionApi';
import * as contabilidadApi from './contabilidadApi';
import * as conciliacionApi from './conciliacionApi';
import * as contabilidadElectronicaApi from './contabilidadElectronicaApi';
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
  /** P0-02: los encabezados, para exigir la sesión en todo `/api/v1`. */
  encabezados: Record<string, string>;
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
        encabezados: Object.fromEntries(new Headers(opciones?.headers).entries()),
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

const SOLICITUD_A24 = {
  documento: 'catalogo', anio: 2026, mes: 3, tipo_envio: 'N', fecha_mod_bal: null,
  tipo_solicitud: '', num_orden: '', num_tramite: '', sellar: false,
} as const;

const LLAMADAS: Record<string, Record<string, () => Promise<unknown>>> = {
  'despachoApi.ts': {
    obtenerClientes: () => despachoApi.obtenerClientes(),
    obtenerCliente: () => despachoApi.obtenerCliente('demo'),
    obtenerCalendarioPatronal: () => despachoApi.obtenerCalendarioPatronal(2026),
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
  'cartera.ts': {
    cargarCartera: () => cartera.cargarCartera('uid-1'),
    guardarCliente: () => cartera.guardarCliente({ id: 'mio' } as never),
    borrarCliente: () => cartera.borrarCliente('mio'),
    guardarEmpleado: () => cartera.guardarEmpleado('mio', { empleado_no: 'E-01' } as never),
    borrarEmpleado: () => cartera.borrarEmpleado('mio', 'E-01'),
    // Lo primero que pide es la cartera propia (para no sembrar sobre ella).
    sembrarDemo: () => cartera.sembrarDemo(),
  },
  'semillaDemo.ts': {
    sembrarDemo: () => semillaDemo.sembrarDemo(),
    carteraDelCatalogo: () => semillaDemo.carteraDelCatalogo(),
  },
  'dispositivos.ts': {
    listarDispositivos: () => dispositivos.listarDispositivos('mio'),
    guardarDispositivo: () => dispositivos.guardarDispositivo('mio', { id: '' } as never),
    borrarDispositivo: () => dispositivos.borrarDispositivo('mio', 'd1'),
  },
  'carteraApi.ts': {
    obtenerEmpleadosSemilla: () => carteraApi.obtenerEmpleadosSemilla('demo'),
    integrarSBC: () => carteraApi.integrarSBC({ salario_diario: '500.00', fecha: '2026-09-01' }),
    obtenerPrimasDeRiesgo: () => carteraApi.obtenerPrimasDeRiesgo('2026-09-01'),
  },
  'cfdiNominaApi.ts': {
    generarCFDINomina: () => cfdiNominaApi.generarCFDINomina({} as never),
  },
  'bovedaApi.ts': {
    importarCfdi: () => bovedaApi.importarCfdi('taller', []),
    listarCfdi: () => bovedaApi.listarCfdi('taller', { tipo: 'I', pagina: 2 }),
    descargarXml: () => bovedaApi.descargarXml('taller', 'AAAA-BBBB'),
    borrarCfdi: () => bovedaApi.borrarCfdi('taller', 'AAAA-BBBB'),
    resumenBoveda: () => bovedaApi.resumenBoveda('taller'),
    // P1-06: los CFDI del periodo en la forma de los cálculos.
    facturasParaCalculo: () => bovedaApi.facturasParaCalculo('taller', { desde: '2026-03-01', hasta: '2026-03-31' }),
  },
  'satDescargaApi.ts': {
    obtenerConfigSat: () => satDescargaApi.obtenerConfigSat('taller'),
    guardarConfigSat: () => satDescargaApi.guardarConfigSat('taller', { activa: true }),
    descargarAhora: () => satDescargaApi.descargarAhora('taller', '2026-09-01', '2026-09-02'),
    descargaHistorica: () => satDescargaApi.descargaHistorica('taller', '2026-01-01'),
    listarSolicitudesSat: () => satDescargaApi.listarSolicitudesSat('taller', 2),
    obtenerBitacoraSat: () => satDescargaApi.obtenerBitacoraSat('taller', 2026, 9),
  },
  'credencialesApi.ts': {
    listarCredenciales: () => credencialesApi.listarCredenciales('taller'),
    subirCredencial: () =>
      credencialesApi.subirCredencial(
        'taller', 'efirma', new File(['c'], 'a.cer'), new File(['k'], 'a.key'), 'x',
      ),
    borrarCredencial: () => credencialesApi.borrarCredencial('taller', 7),
  },
  'trabajosApi.ts': {
    listarTrabajos: () => trabajosApi.listarTrabajos({ cliente: 'demo', estado: 'fallido' }),
    obtenerTrabajo: () => trabajosApi.obtenerTrabajo(7),
    reintentarTrabajo: () => trabajosApi.reintentarTrabajo(7),
    cancelarTrabajo: () => trabajosApi.cancelarTrabajo(7),
    encolarDiagnostico: () => trabajosApi.encolarDiagnostico('demo', 1),
    listarAuditoria: () => trabajosApi.listarAuditoria({ cliente: 'demo', pagina: 2 }),
  },
  'satVerificacionApi.ts': {
    verificarEstatus: () => satVerificacionApi.verificarEstatus('taller', '2026-10-01', '2026-10-31'),
    riesgos69b: () => satVerificacionApi.riesgos69b('taller'),
    atenderAlerta: () => satVerificacionApi.atenderAlerta('taller', 3),
    estadoListas: () => satVerificacionApi.estadoListas(),
    historialCumplimiento: () => satVerificacionApi.historialCumplimiento('taller', 'constancia'),
    obtenerAhora: () => satVerificacionApi.obtenerAhora('taller', 'opinion'),
    subirPdfCumplimiento: () =>
      satVerificacionApi.subirPdfCumplimiento('taller', 'opinion', new File(['%PDF-'], 'o.pdf')),
    descargarPdfCumplimiento: () => satVerificacionApi.descargarPdfCumplimiento('taller', 9),
    guardarConfigCumplimiento: () =>
      satVerificacionApi.guardarConfigCumplimiento('taller', { automatico: true, dia_del_mes: 1, constancia: true }),
    semaforoCartera: () => satVerificacionApi.semaforoCartera(),
  },
  'contabilidadApi.ts': {
    listarCuentas: () => contabilidadApi.listarCuentas('taller'),
    sembrarCatalogo: () => contabilidadApi.sembrarCatalogo('taller'),
    crearCuenta: () => contabilidadApi.crearCuenta('taller', { numero: '1', nombre: 'x', codigo_agrupador: '101' }),
    editarCuenta: () => contabilidadApi.editarCuenta('taller', 3, { nombre: 'x' }),
    borrarCuenta: () => contabilidadApi.borrarCuenta('taller', 3),
    obtenerAgrupador: () => contabilidadApi.obtenerAgrupador(),
    obtenerConfigContable: () => contabilidadApi.obtenerConfigContable('taller'),
    guardarConfigContable: () => contabilidadApi.guardarConfigContable('taller', { tope_activo: '0' }),
    crearRegla: () => contabilidadApi.crearRegla('taller', { criterio: 'rfc', valor: 'X', cuenta_numero: '601.84', prioridad: 1, activa: true }),
    editarRegla: () => contabilidadApi.editarRegla('taller', 4, { activa: false }),
    borrarRegla: () => contabilidadApi.borrarRegla('taller', 4),
    generarPolizas: () => contabilidadApi.generarPolizas('taller', '2026-03-01', '2026-03-31'),
    listarPolizas: () => contabilidadApi.listarPolizas('taller', { tipo: 'diario', pagina: 2 }),
    obtenerPoliza: () => contabilidadApi.obtenerPoliza('taller', 5),
    crearPoliza: () => contabilidadApi.crearPoliza('taller', { tipo: 'diario', fecha: '2026-03-01', concepto: '', movimientos: [] }),
    editarPoliza: () => contabilidadApi.editarPoliza('taller', 5, { concepto: 'x' }),
    cancelarPoliza: () => contabilidadApi.cancelarPoliza('taller', 5, 'x'),
    listarPeriodosCerrados: () => contabilidadApi.listarPeriodosCerrados('taller'),
    cerrarPeriodo: () => contabilidadApi.cerrarPeriodo('taller', 2026, 3),
    abrirPeriodo: () => contabilidadApi.abrirPeriodo('taller', 2026, 3),
    obtenerBalanza: () => contabilidadApi.obtenerBalanza('taller', '2026-03-01', '2026-03-31', 1, 'todas'),
    obtenerAuxiliar: () => contabilidadApi.obtenerAuxiliar('taller', 6, '2026-03-01', '2026-03-31'),
    listarSaldosIniciales: () => contabilidadApi.listarSaldosIniciales('taller'),
    guardarSaldosIniciales: () => contabilidadApi.guardarSaldosIniciales('taller', []),
  },
  'conciliacionApi.ts': {
    listarBancos: () => conciliacionApi.listarBancos(),
    listarCuentasBancarias: () => conciliacionApi.listarCuentasBancarias('taller'),
    crearCuentaBancaria: () => conciliacionApi.crearCuentaBancaria('taller', { banco: '012', nombre: 'x', numero: '1', clabe: '', cuenta_contable_id: 1, ventana_dias: 3, umbral: 60 }),
    editarCuentaBancaria: () => conciliacionApi.editarCuentaBancaria('taller', 2, { nombre: 'y' }),
    borrarCuentaBancaria: () => conciliacionApi.borrarCuentaBancaria('taller', 2),
    listarPlantillas: () => conciliacionApi.listarPlantillas('taller'),
    guardarPlantilla: () => conciliacionApi.guardarPlantilla('taller', { nombre: 'p', banco: '012', formato: 'csv', mapeo: {} }),
    borrarPlantilla: () => conciliacionApi.borrarPlantilla('taller', 3),
    importarEstado: () => conciliacionApi.importarEstado('taller', 2, new File(['x'], 'e.csv')),
    listarEstados: () => conciliacionApi.listarEstados('taller', 2),
    obtenerVista: () => conciliacionApi.obtenerVista('taller', 2, '2026-03-01', '2026-03-31'),
    conciliarAutomatico: () => conciliacionApi.conciliarAutomatico('taller', 2),
    conciliarManual: () => conciliacionApi.conciliarManual('taller', 2, ['b:1'], ['p:1']),
    deshacerConciliacion: () => conciliacionApi.deshacerConciliacion('taller', 2, 4),
    sugerirCuenta: () => conciliacionApi.sugerirCuenta('taller', 2, 5),
    polizaDesdeBanco: () => conciliacionApi.polizaDesdeBanco('taller', 2, 5, [], ''),
    obtenerReporte: () => conciliacionApi.obtenerReporte('taller', 2, '2026-03-31'),
    descargarReporte: () => conciliacionApi.descargarReporte('taller', 2, '2026-03-31'),
  },
  'contabilidadElectronicaApi.ts': {
    obtenerDocumentos: () => contabilidadElectronicaApi.obtenerDocumentos(),
    validarAnexo24: () => contabilidadElectronicaApi.validarAnexo24('taller', SOLICITUD_A24),
    descargarZipAnexo24: () => contabilidadElectronicaApi.descargarZipAnexo24('taller', SOLICITUD_A24),
    enviarAnexo24: () => contabilidadElectronicaApi.enviarAnexo24('taller', SOLICITUD_A24),
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
  'cartera.ts': cartera,
  'semillaDemo.ts': semillaDemo,
  'dispositivos.ts': dispositivos,
  'cfdiNominaApi.ts': cfdiNominaApi,
  'bovedaApi.ts': bovedaApi,
  'satDescargaApi.ts': satDescargaApi,
  'credencialesApi.ts': credencialesApi,
  'trabajosApi.ts': trabajosApi,
  'satVerificacionApi.ts': satVerificacionApi,
  'contabilidadApi.ts': contabilidadApi,
  'conciliacionApi.ts': conciliacionApi,
  'contabilidadElectronicaApi.ts': contabilidadElectronicaApi,
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
  // C-02: régimen del cliente → tipo del calendario. Un switch, no pega al backend.
  'tipoCalendarioDeRegimen',
  'estaVinculado',
  'contarSinVincular',
  // C-01: le quita la plantilla al cliente antes de editarlo. No pega al backend.
  'sinEmpleados',
  // T4: la frontera de tipos del CFDI de nómina. Ninguna pega al backend.
  'esNomina',
  'facturasFiscales',
  'contarNomina',
  'faltantesParaCFDI',
  'reciboParaCFDI',
  // P0-03: arma el query string de los filtros de la bóveda. No pega al backend.
  'consultaDeFiltros',
  // P0-04: etiqueta del estado de un trabajo. Un mapeo, no pega al backend.
  'etiquetaEstado',
]);

/**
 * Exenciones **por módulo**, no por nombre: `HELPERS_PUROS` es global, y eximir ahí
 * un nombre lo eximiría en todos los módulos. Hoy no hay ninguna.
 */
const PUROS_POR_MODULO: Record<string, Set<string>> = {};

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

        it(`${nombre} manda la sesión si pega a /api/v1 (P0-02)`, async () => {
          const { path, encabezados } = await urlDe(llamar);
          if (!path.startsWith('/api/v1/')) return; // `/health` es público
          expect(
            encabezados.authorization,
            `${nombre} pide ${path} SIN Authorization: el backend responde 401. ` +
              'Usa apiFetch o encabezadoAuth de services/api.ts.',
          ).toBe('Bearer token-de-prueba');
        });
      }
    });
  }

  it('el calendario patronal pide exactamente la ruta que el backend publica', async () => {
    // El caso del 2026-09-02, anclado en el lado del front.
    const { path, metodo } = await urlDe(() =>
      despachoApi.obtenerCalendarioPatronal(2026),
    );
    expect(path).toBe('/api/v1/despacho/calendario');
    expect(metodo).toBe('GET');
  });

  it('el calendario del despacho no pide el modo empresa única (fan-out sobre la cartera)', async () => {
    const { url } = await urlDe(() => despachoApi.obtenerCalendarioPatronal(2026));
    const params = new URL(url).searchParams;
    expect(params.get('empresa_unica')).toBeNull();
    expect(params.get('anio_de_las_cuotas')).toBe('2026');
  });
});
