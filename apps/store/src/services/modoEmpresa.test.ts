/**
 * El interruptor del pivote (O-01).
 *
 * Es un módulo de tres líneas y aun así lleva pruebas, porque de su default
 * cuelga qué app arranca: si alguien invierte la comparación, un build de
 * producción vuelve al modo despacho y **nada más falla**. Los tests de
 * despacho seguirían verdes —declaran su modo— y los de empresa única también,
 * porque stubbean. El default es justo lo que ningún otro test mide.
 */

import { afterEach, describe, expect, it, vi } from 'vitest';
import { ID_EMPRESA, modoEmpresaUnica } from './modoEmpresa';

describe('modoEmpresaUnica', () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it('viene ENCENDIDO cuando la variable no está puesta', () => {
    vi.stubEnv('VITE_MODO_EMPRESA_UNICA', undefined as unknown as string);
    expect(modoEmpresaUnica()).toBe(true);
  });

  /**
   * LA REGLA CAMBIÓ EN O-cierre, Y NO ES UN TEST AFLOJADO.
   *
   * Antes apagaba **sólo** el literal `'0'`, con este argumento: apagar el
   * pivote tiene que ser deliberado, y un `.env` a medio escribir no puede
   * devolver la app del despacho por accidente. El argumento sigue en pie para
   * el valor VACÍO, y por eso `''` sigue encendiendo.
   *
   * Lo que no se sostiene es que `VITE_MODO_EMPRESA_UNICA=false` —la forma que
   * cualquiera escribiría— dejara el modo encendido **sin decir nada**. Eso no
   * protege de un dedazo: es un flag que ignora en silencio lo que le
   * escribieron, y quien lo puso cree que trabaja en modo despacho. Lo señaló
   * el revisor de cierre.
   *
   * La regla nueva: apagan los valores que **no pueden significar otra cosa**;
   * lo ambiguo o vacío deja el pivote encendido.
   */
  it.each(['0', 'false', 'off', 'no', 'FALSE', ' 0 '])('%s apaga el modo', (valor) => {
    vi.stubEnv('VITE_MODO_EMPRESA_UNICA', valor);
    expect(modoEmpresaUnica()).toBe(false);
  });

  it.each(['1', 'true', '', 'si', 'yes', 'x'])('%s lo deja encendido', (valor) => {
    // El vacío incluido: un `.env` a medio escribir no cambia de app.
    vi.stubEnv('VITE_MODO_EMPRESA_UNICA', valor);
    expect(modoEmpresaUnica()).toBe(true);
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
