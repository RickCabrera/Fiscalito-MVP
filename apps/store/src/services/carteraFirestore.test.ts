/**
 * La cartera nunca deja la pantalla vacía (G-03).
 *
 * LO QUE ESTOS TESTS CUIDAN
 * -------------------------
 * Regla de Ricardo: la demo funciona en TODO momento. El modo de falla
 * peligroso NO es que Firestore truene —eso se atrapa— sino que **devuelva
 * vacío**: con unas reglas que permitan leer y nieguen escribir, la siembra
 * nunca se escribe, la lectura no lanza, y queda una app que se ve bien y no
 * tiene clientes. Cada test de abajo es uno de esos caminos.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';

const getDocs = vi.fn();
const setDoc = vi.fn();
const deleteDoc = vi.fn();
const commit = vi.fn();
const loteSet = vi.fn();
const loteDelete = vi.fn();

vi.mock('firebase/firestore', () => ({
  collection: (...args: unknown[]) => ({ path: args.slice(1).join('/') }),
  doc: (...args: unknown[]) => ({ path: args.slice(1).join('/') }),
  getDocs: (...args: unknown[]) => getDocs(...args),
  setDoc: (...args: unknown[]) => setDoc(...args),
  deleteDoc: (...args: unknown[]) => deleteDoc(...args),
  writeBatch: () => ({ set: loteSet, delete: loteDelete, commit }),
}));

vi.mock('./firebase', () => ({ db: {} }));

const obtenerClientes = vi.fn();
const obtenerCliente = vi.fn();
// O-03: el periodo sale de `GET /nomina/periodo-sugerido`, por periodicidad, y
// ya no de copiar la quincena del cliente `demo` a todos.
const obtenerPeriodoSugerido = vi.fn();
vi.mock('./despachoApi', () => ({
  obtenerClientes: () => obtenerClientes(),
  obtenerCliente: (id: string) => obtenerCliente(id),
  obtenerPeriodoSugerido: (clave: string) => obtenerPeriodoSugerido(clave),
}));

const obtenerEmpleadosSemilla = vi.fn();
vi.mock('./carteraApi', () => ({
  obtenerEmpleadosSemilla: (id: string) => obtenerEmpleadosSemilla(id),
}));

import { cargarCartera, sembrarDemo } from './carteraFirestore';

const RESUMEN = {
  id: 'demo', nombre: 'Cliente Demo', giro: 'Servicios', origen: 'fixtures-s04',
  num_empleados: 9, prima_riesgo: '0.0054355', clase_riesgo: null,
  clave_periodicidad: '04', zona: 'general',
};

const EMPLEADO = {
  empleado_no: 'E-01', nombre: 'ANA LOPEZ', puesto: '', salario_diario: '316.00',
  salario_diario_integrado: '331.58', zona: 'general', fecha_alta: null,
  tipo_contrato: 'indeterminado' as const,
  prestaciones: { dias_aguinaldo: 15, dias_vacaciones: 0, prima_vacacional: '0.25' },
  nss: '', employee_no: 'E-01', enrolamiento: 'enrolado' as const,
};

/** El periodo que el backend calcula HOY. */
const PERIODO_DE_HOY = { inicio: '2026-08-16', fin: '2026-08-31', fecha_pago: null };
/** El que quedó congelado en Firestore al sembrar, dos quincenas atrás. */
const VIEJO = { inicio: '2026-07-16', fin: '2026-07-31', fecha_pago: null };

function backendResponde() {
  obtenerClientes.mockResolvedValue([RESUMEN]);
  obtenerCliente.mockResolvedValue({
    ...RESUMEN,
    empleados: [],
    periodo_sugerido: PERIODO_DE_HOY,
    fecha_referencia: '2026-09-01',
  });
  obtenerPeriodoSugerido.mockResolvedValue({
    clave_periodicidad: '04',
    periodo: PERIODO_DE_HOY,
    dias_naturales: 16,
  });
  obtenerEmpleadosSemilla.mockResolvedValue({
    cliente_id: 'demo', origen: 'fixtures-s04', total: 1, sin_vincular: 0,
    empleados: [EMPLEADO],
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  backendResponde();
});

describe('cargarCartera', () => {
  /**
   * R-06 INVIRTIÓ LA PREMISA DE ESTE BLOQUE, Y HAY QUE DECIRLO.
   *
   * Hasta G-03, TODO camino que no terminara en "la cartera del usuario"
   * devolvía el catálogo de demostración del backend: vacía, error, timeout y
   * sin sesión. Era deliberado —que la demo no se rompiera nunca— y este
   * archivo lo probaba caso por caso.
   *
   * El costo lo declaraba el propio `carteraFirestore.ts`: **dos cuentas
   * distintas veían los mismos tres clientes**, o sea el criterio de G-03 sin
   * cumplir. Ahora cada caso devuelve una verdad sobre ESTA cuenta, y ninguno
   * devuelve los clientes de otra persona.
   *
   * Los casos no se borran: cambian de aserción. Las cotas de tiempo siguen
   * probadas, porque el modo de falla que evitan —Firestore colgado deja
   * `loading` en `true` para siempre— no lo tocó R-06.
   */
  it('sin sesión devuelve una cartera vacía, no el catálogo', async () => {
    const r = await cargarCartera(null);
    expect(r.clientes).toEqual([]);
    expect(r.error).toBeNull();
    // `origen` decide `soloLectura` en `CarteraContext`, así que también aquí:
    // devolver `backend` en un camino que no trae datos del backend dejaría la
    // cartera de sólo lectura por una razón que no existe.
    expect(r.origen).toBe('firestore');
    // Y NO se pide el catálogo: pedirlo sería trabajo para enseñar datos ajenos.
    expect(obtenerClientes).not.toHaveBeenCalled();
  });

  it('con datos en Firestore usa los del usuario', async () => {
    getDocs
      .mockResolvedValueOnce({ docs: [{ id: 'mio', data: () => ({ nombre: 'Mi Cliente' }) }] })
      .mockResolvedValueOnce({ docs: [{ data: () => EMPLEADO }] });

    const r = await cargarCartera('uid-1');
    expect(r.origen).toBe('firestore');
    expect(r.clientes[0].id).toBe('mio');
    expect(r.clientes[0].empleados).toHaveLength(1);
    expect(r.error).toBeNull();
    expect(obtenerClientes).not.toHaveBeenCalled();
  });

  it('UNA CARTERA VACÍA es una cartera vacía, y es ESCRIBIBLE', async () => {
    // El caso que le da la vuelta a G-03. Antes se trataba igual que un error y
    // se caía al catálogo, con lo que una cuenta nueva NUNCA podía verse a sí
    // misma vacía ni crear su primer cliente.
    //
    // `origen: 'firestore'` no es cosmético: `CarteraContext` deriva
    // `soloLectura` de ahí, así que con `'backend'` el botón "crea tu primer
    // cliente" rebota con "esta cartera es el catálogo de demostración". Es una
    // palabra y es la tarea entera.
    getDocs.mockResolvedValue({ docs: [] });

    const r = await cargarCartera('uid-1');
    expect(r.clientes).toEqual([]);
    expect(r.origen).toBe('firestore');
    expect(r.error).toBeNull();
    expect(obtenerClientes).not.toHaveBeenCalled();
  });

  it('si Firestore lanza, lo DICE y no enseña datos de otra persona', async () => {
    getDocs.mockRejectedValue(new Error('Missing or insufficient permissions.'));

    const r = await cargarCartera('uid-1');
    expect(r.error).toContain('insufficient permissions');
    expect(r.clientes).toEqual([]);
    // Y la cartera sigue siendo SUYA: tras un fallo transitorio, reintentar y
    // crear un cliente tiene que seguir siendo posible. Con `backend` aquí, el
    // contador quedaba en sólo lectura hasta recargar la página.
    expect(r.origen).toBe('firestore');
    // La aserción que mata la regresión: ni un cliente del catálogo en pantalla.
    expect(obtenerClientes).not.toHaveBeenCalled();
  });

  it('si Firestore se cuelga, el timeout la rescata', async () => {
    // La cota sigue siendo obligatoria y por la misma razón que antes: una
    // promesa que nunca resuelve deja `loading` en `true` para siempre, y la
    // pantalla no llega ni a poder decir que algo salió mal.
    vi.useFakeTimers();
    getDocs.mockReturnValue(new Promise(() => {}));

    const promesa = cargarCartera('uid-1');
    await vi.advanceTimersByTimeAsync(3000);
    const r = await promesa;

    expect(r.error).toContain('tardó');
    expect(r.clientes).toEqual([]);
    expect(r.origen).toBe('firestore');
    vi.useRealTimers();
  });
});

describe('conPeriodoAlDia · el periodo sugerido no envejece', () => {
  /**
   * Lo que hay en Firestore es un **snapshot** del momento de sembrar, no
   * `quincena(hoy)` reevaluado: el backend lo recalcula en cada request y
   * Firestore no. Dos semanas después, cada cliente arrancaría con una quincena
   * vencida, el panel saldría vacío y la pantalla pediría confirmación por una
   * razón que nadie entendería.
   */
  it('reemplaza el periodo guardado por el que el backend calcula hoy', async () => {
    getDocs
      .mockResolvedValueOnce({
        docs: [{ id: 'mio', data: () => ({ nombre: 'Mi Cliente', periodo_sugerido: VIEJO }) }],
      })
      .mockResolvedValueOnce({ docs: [] });

    const r = await cargarCartera('uid-1');
    expect(r.origen).toBe('firestore');
    expect(r.clientes[0].periodo_sugerido).toEqual(PERIODO_DE_HOY);
  });

  it('si el backend falla, conserva el snapshot y NO cambia de origen', async () => {
    // Quedarse con una quincena vieja es peor que estar al día, y mucho mejor
    // que quedarse sin cartera.
    getDocs
      .mockResolvedValueOnce({
        docs: [{ id: 'mio', data: () => ({ nombre: 'Mi Cliente', periodo_sugerido: VIEJO }) }],
      })
      .mockResolvedValueOnce({ docs: [] });
    obtenerPeriodoSugerido.mockRejectedValue(new Error('API caída'));

    const r = await cargarCartera('uid-1');
    expect(r.origen).toBe('firestore');
    expect(r.clientes[0].periodo_sugerido).toEqual(VIEJO);
  });

  it('si el backend se CUELGA, la carga no se cuelga con él', async () => {
    // El agujero real: un `await` sin cota aquí dejaba `cargarCartera` sin
    // resolver nunca — spinner eterno en la lista y, peor, `deLaCartera` en
    // `null` para siempre, que rompe la auto-sanación del error de carga.
    vi.useFakeTimers();
    getDocs
      .mockResolvedValueOnce({
        docs: [{ id: 'mio', data: () => ({ nombre: 'Mi Cliente', periodo_sugerido: VIEJO }) }],
      })
      .mockResolvedValueOnce({ docs: [] });
    obtenerPeriodoSugerido.mockReturnValue(new Promise(() => {}));

    const promesa = cargarCartera('uid-1');
    await vi.advanceTimersByTimeAsync(3000);
    const r = await promesa;

    expect(r.origen).toBe('firestore');
    expect(r.clientes[0].periodo_sugerido).toEqual(VIEJO);
    vi.useRealTimers();
  });
});

describe('sembrarDemo', () => {
  it('no hace nada si el usuario ya tiene cartera', async () => {
    // Idempotente: sembrar dos veces no duplica ni pisa lo que el contador editó.
    getDocs.mockResolvedValue({ empty: false, docs: [] });

    expect(await sembrarDemo('uid-1')).toBe(false);
    expect(commit).not.toHaveBeenCalled();
  });

  it('escribe los clientes y sus empleados en un solo lote', async () => {
    getDocs.mockResolvedValue({ empty: true, docs: [] });

    expect(await sembrarDemo('uid-1')).toBe(true);
    expect(commit).toHaveBeenCalledTimes(1);
    // Un documento de cliente + un documento de empleado.
    expect(loteSet).toHaveBeenCalledTimes(2);
  });

  it('el cliente que escribe NO lleva el arreglo de empleados dentro', async () => {
    // Los empleados son una subcolección. Guardarlos también embebidos daría
    // dos verdades sobre la plantilla, y la de adentro nunca se actualizaría.
    getDocs.mockResolvedValue({ empty: true, docs: [] });
    await sembrarDemo('uid-1');

    const datosDelCliente = loteSet.mock.calls[0][1];
    expect(datosDelCliente).not.toHaveProperty('empleados');
    expect(datosDelCliente.nombre).toBe('Cliente Demo');
  });
});

describe('O-03 · el periodo sigue a la PERIODICIDAD de cada cliente', () => {
  /**
   * EL CALLEJÓN QUE ESTO CIERRA.
   *
   * Hasta O-03 esta función copiaba la quincena del cliente `demo` a **todos**,
   * sin mirar su clave — su propio docstring lo advertía: *"el día que se abran
   * las otras claves ésta es la puerta que queda abierta"*.
   *
   * O-03 abre semanal y mensual y sube al motor la guarda de duración. Con la
   * versión vieja, una empresa mensual recibía una quincena propuesta y el
   * motor rechazaba el cálculo: **el selector rompía la app en dos de sus tres
   * opciones**, y la culpa parecía del motor.
   */
  it('a un cliente mensual le propone un MES, no una quincena', async () => {
    const MES = { inicio: '2026-08-01', fin: '2026-08-31', fecha_pago: '2026-08-31' };
    obtenerPeriodoSugerido.mockImplementation(async (clave: string) => ({
      clave_periodicidad: clave,
      periodo: clave === '05' ? MES : PERIODO_DE_HOY,
      dias_naturales: clave === '05' ? 31 : 16,
    }));
    getDocs
      .mockResolvedValueOnce({
        docs: [
          {
            id: 'mensual',
            data: () => ({
              nombre: 'Mensual', clave_periodicidad: '05', periodo_sugerido: VIEJO,
            }),
          },
        ],
      })
      .mockResolvedValueOnce({ docs: [] });

    const r = await cargarCartera('uid-1');

    expect(obtenerPeriodoSugerido).toHaveBeenCalledWith('05');
    expect(r.clientes[0].periodo_sugerido).toEqual(MES);
  });

  it('pide UNA vez por clave, no una por cliente', async () => {
    // Los clientes que comparten periodicidad comparten periodo. En modo
    // empresa única esto es una sola llamada.
    getDocs
      .mockResolvedValueOnce({
        docs: [
          { id: 'a', data: () => ({ nombre: 'A', clave_periodicidad: '04' }) },
          { id: 'b', data: () => ({ nombre: 'B', clave_periodicidad: '04' }) },
          { id: 'c', data: () => ({ nombre: 'C', clave_periodicidad: '05' }) },
        ],
      })
      .mockResolvedValue({ docs: [] });

    await cargarCartera('uid-1');

    expect(obtenerPeriodoSugerido).toHaveBeenCalledTimes(2);
  });

  it('una clave sin tarifa deja a ESE cliente con su snapshot, no con otro periodo', async () => {
    /**
     * Una clave sin tarifa publicada (§D10) responde 422. Darle entonces el
     * periodo de otra periodicidad sería exactamente el bug que esto cierra:
     * mejor un snapshot viejo —que la pantalla deja corregir a mano— que un
     * periodo que no le corresponde.
     */
    obtenerPeriodoSugerido.mockRejectedValue(new Error('422 sin tarifa'));
    getDocs
      .mockResolvedValueOnce({
        docs: [
          {
            id: 'catorcenal',
            data: () => ({
              nombre: 'Catorcenal', clave_periodicidad: '03', periodo_sugerido: VIEJO,
            }),
          },
        ],
      })
      .mockResolvedValueOnce({ docs: [] });

    const r = await cargarCartera('uid-1');
    expect(r.clientes[0].periodo_sugerido).toEqual(VIEJO);
  });
});
