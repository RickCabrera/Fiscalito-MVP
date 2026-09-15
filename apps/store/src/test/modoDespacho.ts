/**
 * Declarar que un test corre en MODO DESPACHO (corrida O).
 *
 * Nació en O-01, cuando `modoEmpresaUnica()` venía ENCENDIDO por default y las
 * pruebas de las épicas E, G y R —cartera, selector de cliente, rutas
 * `/app/clientes`— tenían que decir en qué modo miden o medían el otro producto.
 *
 * **T1 invirtió el default** (ver `services/modoEmpresa.ts`): hoy la app arranca
 * en modo despacho, así que esta llamada ya no es lo que hace pasar a esos
 * archivos. **Se queda, y no por inercia:** deja escrito en qué mundo mide cada
 * archivo en vez de heredarlo del ambiente, que es justo lo que O-01 vino a
 * arreglar. Si el default volviera a moverse, estas pruebas no se enteran.
 *
 * **No afloja nada.** No cambia una sola aserción: fija el mundo en el que se
 * evalúan, que es lo que el flag hace en producción.
 *
 * Uso:
 *
 *     import { modoDespacho } from '../test/modoDespacho';
 *     describe('...', () => {
 *       modoDespacho();
 *       ...
 *     });
 */

import { afterEach, beforeEach, vi } from 'vitest';

/** Apaga el modo empresa única mientras dure el bloque que la llama. */
export function modoDespacho(): void {
  beforeEach(() => {
    vi.stubEnv('VITE_MODO_EMPRESA_UNICA', '0');
  });
  afterEach(() => {
    vi.unstubAllEnvs();
  });
}

/**
 * La gemela: enciende el modo empresa única mientras dure el bloque.
 *
 * **T1 la hizo necesaria.** Al invertirse el default, los bloques que medían el
 * modo empresa única SIN declararlo pasaron a medir el despacho, y ocho de ellos
 * —en `agent/modoEmpresaUnicaEnElAsistente.test.ts`— se cayeron diciendo
 * exactamente eso. Los que ya stubbeaban `'1'` a mano no se enteraron, que es
 * la prueba de que el problema era la herencia del ambiente y no el valor.
 *
 * Se llama `modoEmpresa` y no `modoEmpresaUnica` para no chocar con la función
 * de producción del mismo nombre, que algún archivo importa junto con ésta.
 */
export function modoEmpresa(): void {
  beforeEach(() => {
    vi.stubEnv('VITE_MODO_EMPRESA_UNICA', '1');
  });
  afterEach(() => {
    vi.unstubAllEnvs();
  });
}
