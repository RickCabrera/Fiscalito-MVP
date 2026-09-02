/**
 * El interruptor de dueño del dato. (R-07)
 *
 * LO QUE ESTE ARCHIVO PROTEGE
 * ---------------------------
 * Que el default sea Firestore. Encender el backend sin credenciales da **503
 * en todo el CRUD**, y una regresión aquí no se ve como un error de
 * configuración: se ve como una app que dejó de guardar clientes.
 *
 * Y que las dos implementaciones tengan **la misma forma**. El despachador las
 * intercambia sin que ninguna pantalla se entere, así que una firma que no
 * cuadre no se detecta al compilar —`export const x = activa.x` acepta
 * cualquier cosa— sino en producción, cuando alguien encienda el flag.
 */

import { describe, expect, it, vi } from 'vitest';

/**
 * `services/firebase.ts` llama a `getAuth()` **al importarse**, y sin las llaves
 * de Firebase eso lanza `auth/invalid-api-key`. En local hay `.env` y no se
 * nota; en CI no hay secretos y el archivo entero revienta antes del primer
 * test. Lo descubrió el CI de R-07, y es el mismo modo de falla que la entrada
 * de X-01 documenta: **el bug sólo aparece porque el test corre en un entorno
 * distinto al local**.
 *
 * Es el patrón que ya usan `carteraFirestore.test.ts`, `agentLoop.test.ts`,
 * `tools.test.ts` y `FiscalitoServicePage.test.tsx`.
 */
vi.mock('./firebase', () => ({ auth: {}, db: {}, default: {} }));

import * as despachador from './cartera';
import * as firestore from './carteraFirestore';
import * as backend from './carteraBackend';

/** Las operaciones que una pantalla puede pedirle a la cartera. */
const OPERACIONES = [
  'cargarCartera',
  'guardarCliente',
  'borrarCliente',
  'guardarEmpleado',
  'borrarEmpleado',
  'sembrarDemo',
] as const;

describe('el dueño del dato', () => {
  it('el default es Firestore, no el backend', () => {
    // Sin `VITE_CARTERA_BACKEND=1` el backend no manda. Es lo que impide
    // entregar una app que responde 503 a todo por falta de credenciales.
    expect(despachador.BACKEND_ES_DUENO).toBe(false);
  });

  it('con el default, las operaciones son las de Firestore', () => {
    // Identidad de función, no "algo definido": un despachador que exportara
    // envolturas propias pasaría una comprobación más floja y podría estar
    // llamando a la implementación equivocada.
    for (const op of OPERACIONES) {
      expect(despachador[op], op).toBe(firestore[op]);
    }
  });
});

describe('las dos implementaciones son intercambiables', () => {
  it('el backend expone TODAS las operaciones que expone Firestore', () => {
    // El despachador hace `activa.x` sin que TypeScript compare las dos formas,
    // así que una operación faltante en el backend sería `undefined` en tiempo
    // de ejecución — y sólo el día que alguien encienda el flag.
    for (const op of OPERACIONES) {
      expect(typeof backend[op], `al backend le falta ${op}`).toBe('function');
      expect(typeof firestore[op], `a Firestore le falta ${op}`).toBe('function');
    }
  });

  it('reciben el mismo número de argumentos', () => {
    // `guardarEmpleado(uid, clienteId, empleado)` en los dos. Si una tomara los
    // argumentos en otro orden o le sobrara uno, el `.length` lo delata antes
    // de que un contador pierda un empleado.
    for (const op of OPERACIONES) {
      expect(backend[op].length, `${op}: aridad distinta`).toBe(firestore[op].length);
    }
  });
});

describe('la siembra con el backend como dueño', () => {
  it('no existe, y lo dice en vez de fallar raro', async () => {
    // Darle al backend un endpoint que copia salarios de terceros a la cuenta
    // de quien llame sería regalar la escalada que R-06 vino a cerrar.
    await expect(backend.sembrarDemo('uid-1')).rejects.toThrow(/no está disponible/);
  });
});
