/**
 * El interruptor del pivote (O-01).
 *
 * Es un módulo de tres líneas y aun así lleva pruebas, porque de su default
 * cuelga qué app arranca: si alguien invierte la comparación, un build de
 * producción cambia de producto y **nada más falla**. Los tests de despacho
 * siguen verdes —declaran su modo— y los de empresa única también, porque
 * stubbean. El default es justo lo que ningún otro test mide.
 *
 * **T1 invirtió el default**: era encendido (empresa única, O-01) y ahora es
 * apagado (despacho). Lo que este archivo mide no cambió de naturaleza —sigue
 * siendo "qué app arranca sin variable"— sino de valor esperado, y el motivo
 * está escrito en `modoEmpresa.ts`.
 */

import { afterEach, describe, expect, it, vi } from 'vitest';
import { ID_EMPRESA, modoEmpresaUnica } from './modoEmpresa';

describe('modoEmpresaUnica', () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it('viene APAGADO cuando la variable no está puesta: la app del despacho', () => {
    vi.stubEnv('VITE_MODO_EMPRESA_UNICA', undefined as unknown as string);
    expect(modoEmpresaUnica()).toBe(false);
  });

  /**
   * LA REGLA DE O-cierre SE CONSERVA, ESPEJADA. NO ES UN TEST AFLOJADO.
   *
   * O-cierre estableció que el flag no puede ignorar en silencio lo que le
   * escribieron: `=false` tenía que apagar de verdad, no dejar el modo como
   * estaba. T1 invierte cuál es el default, así que la misma regla ahora se
   * aplica del lado de ENCENDER: `=true` enciende igual que `1`.
   *
   * Y el argumento del valor VACÍO sigue intacto, sólo que protege al otro
   * modo: un `.env` a medio escribir no cambia de app, y la app que se queda es
   * la del despacho.
   */
  it.each(['1', 'true', 'on', 'yes', 'si', 'TRUE', ' 1 '])('%s enciende el modo', (valor) => {
    vi.stubEnv('VITE_MODO_EMPRESA_UNICA', valor);
    expect(modoEmpresaUnica()).toBe(true);
  });

  it.each(['0', 'false', 'off', 'no', '', 'x'])('%s lo deja apagado', (valor) => {
    // El vacío incluido: un `.env` a medio escribir no cambia de app.
    vi.stubEnv('VITE_MODO_EMPRESA_UNICA', valor);
    expect(modoEmpresaUnica()).toBe(false);
  });

  it('se re-evalúa en cada llamada, no se congela al importar', () => {
    // Si esto fuera una `const` de módulo, `modoDespacho()` no podría existir y
    // los ~10 archivos de prueba de las épicas E/G/R no tendrían forma de
    // declarar su modo.
    vi.stubEnv('VITE_MODO_EMPRESA_UNICA', '0');
    expect(modoEmpresaUnica()).toBe(false);
    vi.stubEnv('VITE_MODO_EMPRESA_UNICA', '1');
    expect(modoEmpresaUnica()).toBe(true);
  });

  it('el id de la empresa es el que ya usan las rutas de Firestore', () => {
    // Cambiarlo deja huérfanos los empleados guardados: viven en
    // `users/{uid}/clientes/{ID_EMPRESA}/empleados/{id}`.
    expect(ID_EMPRESA).toBe('empresa');
  });
});
