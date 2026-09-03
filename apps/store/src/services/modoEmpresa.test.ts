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

  it('se apaga sólo con el "0" explícito', () => {
    vi.stubEnv('VITE_MODO_EMPRESA_UNICA', '0');
    expect(modoEmpresaUnica()).toBe(false);
  });

  it('cualquier otro valor lo deja encendido', () => {
    // Que `'false'`, `''` o `'no'` NO apaguen es a propósito: apagar el pivote
    // tiene que ser deliberado. Un `.env` con la variable a medio escribir no
    // puede devolver la app del despacho por accidente.
    for (const valor of ['1', 'true', 'false', '', 'no']) {
      vi.stubEnv('VITE_MODO_EMPRESA_UNICA', valor);
      expect(modoEmpresaUnica(), `valor ${JSON.stringify(valor)}`).toBe(valor !== '0');
    }
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
