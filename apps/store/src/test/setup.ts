import { afterEach, beforeEach, vi } from 'vitest';

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
  /**
   * O-01: las variables de entorno también se limpian entre tests.
   *
   * `modoEmpresaUnica()` se lee de `import.meta.env` en cada llamada, y desde el
   * pivote hay ~15 archivos que stubbean el modo. Un archivo que stubbee y no
   * limpie dejaría a los siguientes midiendo un modo que no eligieron —y como
   * muchas aserciones son verdaderas en los dos modos, pasarían **por la razón
   * equivocada**, que es peor que fallar.
   *
   * Es red de seguridad, no el mecanismo: `modoDespacho()` trae su propio
   * `afterEach`. Los dos son idempotentes.
   */
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
});
