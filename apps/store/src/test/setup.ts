import { afterEach, beforeEach, vi } from 'vitest';

/**
 * Sesión de Firebase de prueba para TODA la suite (P0-02).
 *
 * Desde P0-02 cada llamada al backend pide el ID token (`encabezadoAuth` en
 * `services/api.ts`), y `services/firebase.ts` LANZA al importarse sin llaves —el CI no
 * las tiene, ver `sinLlavesDeFirebase.test.ts`—. Sin este doble, cada test de pantalla que
 * toque el backend tendría que repetir el mismo `vi.mock`. Un archivo que necesite otra
 * sesión (o ninguna) declara su propio `vi.mock('./firebase')`, que manda sobre éste; el
 * que necesite el módulo real usa `vi.unmock`.
 */
vi.mock('../services/firebase', () => ({
  auth: { currentUser: { uid: 'uid-prueba', getIdToken: async () => 'token-de-prueba' } },
  db: {},
  default: {},
}));

/**
 * Red cerrada por default.
 *
 * Ningun test debe salir a internet. El que necesite red la stubbea a proposito
 * dentro del propio test. Se reinstala en cada beforeEach porque
 * vi.unstubAllGlobals() del afterEach deja los globals limpios: stubbear una sola
 * vez al cargar el setup dejaria abiertos los tests siguientes del mismo archivo.
 */
function bloqueado(nombre: string) {
  return () => {
    throw new Error(
      `Red bloqueada en tests: se intento usar ${nombre}. ` +
        'Si la prueba necesita red, stubbeala explicitamente.',
    );
  };
}

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn(bloqueado('fetch')));
  vi.stubGlobal('XMLHttpRequest', vi.fn(bloqueado('XMLHttpRequest')));
  vi.stubGlobal('WebSocket', vi.fn(bloqueado('WebSocket')));
  if (typeof navigator !== 'undefined' && 'sendBeacon' in navigator) {
    vi.spyOn(navigator, 'sendBeacon').mockImplementation(bloqueado('navigator.sendBeacon'));
  }
});

afterEach(() => {
  vi.unstubAllGlobals();
  // Las variables de entorno stubbeadas se limpian entre tests.
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
});
