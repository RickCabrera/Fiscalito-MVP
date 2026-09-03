/**
 * Declarar que un test corre en MODO DESPACHO (corrida O).
 *
 * `modoEmpresaUnica()` viene encendido por default, así que las pruebas de las
 * épicas E, G y R —cartera, selector de cliente, rutas `/app/clientes`— tienen
 * que decir en qué modo miden. Antes ese modo era ambiente implícito; ahora es
 * una línea visible al principio del archivo.
 *
 * **No afloja nada.** No cambia una sola aserción: cambia el mundo en el que se
 * evalúan, que es lo que el flag hace en producción. Un test de despacho que se
 * quedara sin esta llamada empezaría a medir el modo empresa única y fallaría —
 * que es exactamente lo que debe pasar.
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
