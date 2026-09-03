/**
 * La navegación en MODO EMPRESA ÚNICA (O-01).
 *
 * Vive en un archivo aparte de `navigation.test.ts` porque aquél declara
 * `modoDespacho()` a nivel de archivo: son dos mundos y cada uno se mide en el
 * suyo, en vez de stubbear ida y vuelta dentro de los mismos casos.
 *
 * QUÉ SE MIDE AQUÍ QUE NO SE MIDE EN NINGÚN OTRO LADO
 * ---------------------------------------------------
 * Que "Clientes" **no está** y que el selector de cliente **no se pinta**. Las
 * dos son afirmaciones negativas, y una afirmación negativa que nadie prueba es
 * la que vuelve por la puerta de atrás: bastaría con que alguien devolviera
 * `LINKS_CONTADOR` en los dos modos para que el pivote desapareciera sin que
 * fallara un solo test del repo.
 */

import { describe, expect, it, vi } from 'vitest';
import {
  getSidebarLinks,
  navActivo,
  rutaInicial,
  rutaTieneAlcanceDeCliente,
  etiquetaDelPerfilOperador,
} from './navigation';

/**
 * Modo empresa única EXPLÍCITO, aunque sea el default.
 *
 * Si mañana alguien invierte el default, este archivo tiene que seguir midiendo
 * el modo empresa única —y `modoEmpresa.test.ts` es quien caza el cambio de
 * default—. Un archivo que dependa del ambiente para saber qué está probando no
 * prueba nada en concreto.
 */
function modoEmpresa() {
  vi.stubEnv('VITE_MODO_EMPRESA_UNICA', '1');
}

describe('sidebar en modo empresa única', () => {
  it('NO tiene Clientes, y sí las cuatro entradas que operan sobre la empresa', () => {
    modoEmpresa();
    const links = getSidebarLinks('contador');
    expect(links.map((l) => l.label)).toEqual([
      'Empleados',
      'Dispositivos',
      'Nómina',
      'Calendario',
      'Perfil',
    ]);
    expect(links.some((l) => l.id === 'clientes')).toBe(false);
    expect(links.some((l) => l.to.startsWith('/app/clientes'))).toBe(false);
  });

  it('un contribuyente ve EXACTAMENTE lo de siempre: el pivote no lo toca', () => {
    modoEmpresa();
    expect(getSidebarLinks('asalariado').map((l) => l.id)).toEqual([
      'dashboard',
      'fiscalito',
      'historial',
      'nomina',
      'perfil',
    ]);
  });

  it('la entrada es la nómina, no una cartera que ya no existe', () => {
    modoEmpresa();
    expect(rutaInicial('contador')).toBe('/app/nomina');
    // Y el contribuyente sigue entrando a su dashboard.
    expect(rutaInicial('asalariado')).toBe('/app');
  });

  it('`/app/nomina` enciende Nómina, que aquí ES la pantalla y no una redirección', () => {
    modoEmpresa();
    const nomina = getSidebarLinks('contador').find((l) => l.id === 'nomina')!;
    expect(navActivo(nomina, '/app/nomina')).toBe(true);
  });

  it('ninguna ruta tiene alcance de cliente: no hay selector que pintar', () => {
    modoEmpresa();
    for (const ruta of [
      '/app/clientes',
      '/app/clientes/demo',
      '/app/clientes/demo/nomina',
      '/app/empleados',
      '/app/dispositivos',
      '/app/nomina',
      '/app/calendario',
      '/app/profile',
    ]) {
      expect(rutaTieneAlcanceDeCliente(ruta), ruta).toBe(false);
    }
  });

  it('el perfil operador se llama Empresa, no Despacho', () => {
    modoEmpresa();
    expect(etiquetaDelPerfilOperador()).toBe('Empresa');
    vi.stubEnv('VITE_MODO_EMPRESA_UNICA', '0');
    expect(etiquetaDelPerfilOperador()).toBe('Despacho / Contador');
  });
});
