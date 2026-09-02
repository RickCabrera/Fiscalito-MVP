/**
 * Quién ve los datos de demostración. (R-06)
 *
 * LO QUE ESTE ARCHIVO PROTEGE
 * ---------------------------
 * Que el default sea **no**. Una regresión aquí no se ve en pantalla como un
 * error: se ve como una app que funciona y que además trae tres clientes — uno
 * de ellos con el salario real de nueve personas.
 */

import { afterEach, describe, expect, it, vi } from 'vitest';
import { esClienteDemo, esCuentaDeDesarrollo } from './entorno';

afterEach(() => { vi.unstubAllEnvs(); });

describe('esClienteDemo', () => {
  it('los TRES clientes de demostración lo son, no sólo los sintéticos', () => {
    // Una versión anterior de R-06 filtraba sólo `sintetico` —Cafetería y
    // Taller, los dos INVENTADOS— y dejaba en pantalla `fixtures-s04`, que es
    // el caso real con montos reales de alguien. Estaba al revés, y este test
    // existe para que no vuelva a estarlo.
    expect(esClienteDemo('sintetico')).toBe(true);
    expect(esClienteDemo('fixtures-s04')).toBe(true);
  });

  it('un cliente capturado por el contador NO es de demostración', () => {
    expect(esClienteDemo('propio')).toBe(false);
    expect(esClienteDemo('')).toBe(false);
  });
});

describe('esCuentaDeDesarrollo', () => {
  it('en el servidor de desarrollo, sí', () => {
    // `import.meta.env.DEV` es `true` en jsdom, que es lo que hace que los
    // tests de pantalla de la demo sigan midiendo lo que medían.
    expect(esCuentaDeDesarrollo('quien@sea.mx')).toBe(true);
  });

  it('en un build de producción el default es NO', () => {
    vi.stubEnv('DEV', false);
    expect(esCuentaDeDesarrollo('quien@sea.mx')).toBe(false);
    expect(esCuentaDeDesarrollo(null)).toBe(false);
    expect(esCuentaDeDesarrollo(undefined)).toBe(false);
  });

  it('VITE_MOSTRAR_DEMO=1 la abre, para ensayar desde un build', () => {
    vi.stubEnv('DEV', false);
    vi.stubEnv('VITE_MOSTRAR_DEMO', '1');
    expect(esCuentaDeDesarrollo(null)).toBe(true);
  });

  it('una cuenta en VITE_CUENTAS_DEMO la ve; las demás no', () => {
    vi.stubEnv('DEV', false);
    vi.stubEnv('VITE_CUENTAS_DEMO', 'ricardo@ejemplo.mx, otra@ejemplo.mx');

    expect(esCuentaDeDesarrollo('ricardo@ejemplo.mx')).toBe(true);
    // Sin distinguir mayúsculas: un correo no cambia por cómo se teclee.
    expect(esCuentaDeDesarrollo('Ricardo@Ejemplo.MX')).toBe(true);
    expect(esCuentaDeDesarrollo('ajeno@ejemplo.mx')).toBe(false);
  });

  it('una lista vacía o con basura no abre la puerta a nadie', () => {
    // El modo de falla que importa: una variable mal puesta (`,,,` o vacía) NO
    // puede terminar dejando pasar a todo el mundo.
    vi.stubEnv('DEV', false);
    for (const lista of ['', '   ', ',,,', ' , ']) {
      vi.stubEnv('VITE_CUENTAS_DEMO', lista);
      expect(esCuentaDeDesarrollo('quien@sea.mx'), `con "${lista}"`).toBe(false);
    }
  });
});
