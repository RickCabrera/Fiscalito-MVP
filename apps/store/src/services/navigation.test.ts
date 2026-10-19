/**
 * Navegación del despacho.
 *
 * K (2026-10-19): el sistema es solo para despachos. Lo que protege este archivo:
 *
 * 1. El sidebar es una lista EXACTA, sin Dashboard ni Historial de contribuyente.
 * 2. El resaltado del sidebar (E-06) y el alcance del selector de cliente.
 * 3. Los tabs de Fiscalito salen del régimen del CLIENTE ACTIVO.
 */

import { describe, expect, it } from 'vitest';
import {
  cuentaLista,
  esContador,
  esRutaDeNomina,
  getSidebarLinks,
  getTabsForProfile,
  navActivo,
  rutaInicial,
  rutaTieneAlcanceDeCliente,
  type SidebarLink,
} from './navigation';
import { MARCA_CORTA } from './marca';

describe('getSidebarLinks', () => {
  it('el contador ve Clientes / Empleados / Dispositivos / Bóveda / Descarga SAT / Nómina / Calendario / Fiscalito / Contabilito / Perfil, en ese orden', () => {
    expect(getSidebarLinks()).toEqual([
      { id: 'clientes', to: '/app/clientes', label: 'Clientes' },
      // R-05: entradas propias. Antes los empleados sólo se alcanzaban entrando
      // a la ficha del cliente y cambiando de pestaña, y los dispositivos no
      // existían. Las dos operan sobre el cliente activo, igual que Nómina, y
      // por eso van juntas y antes de ella: es el orden del flujo real
      // —plantilla, aparatos, y luego la nómina que sale de los dos—.
      { id: 'empleados', to: '/app/empleados', label: 'Empleados' },
      { id: 'dispositivos', to: '/app/dispositivos', label: 'Dispositivos' },
      // P0-03: la bóveda de CFDI del cliente activo, entre Dispositivos y Nómina.
      { id: 'boveda', to: '/app/boveda', label: 'Bóveda' },
      // P1-02: la descarga masiva del SAT, que llena la bóveda del cliente activo.
      { id: 'sat', to: '/app/sat', label: 'Descarga SAT' },
      // E-03: el enlace no conoce el id del cliente; `/app/nomina` lo resuelve
      // desde el contexto. Así `getSidebarLinks` sigue siendo pura del perfil.
      { id: 'nomina', to: '/app/nomina', label: 'Nómina' },
      // E-07: dejó de apuntar al tab de contribuyente. Ahora es el calendario
      // PATRONAL de sus clientes.
      { id: 'calendario', to: '/app/calendario', label: 'Calendario' },
      // T1: el servicio fiscal vuelve al sidebar del despacho, pero lo que
      // abre es el de su CLIENTE ACTIVO. La etiqueta sale de la marca, igual
      // que la del contribuyente, y por la misma razón de O-02.
      { id: 'fiscalito', to: '/app/store/fiscalito/use', label: MARCA_CORTA },
      // La segunda herramienta sobre el cliente activo. Entró porque la portada
      // ya anunciaba Contabilito en BETA y el contador no tenía puerta: la
      // pantalla de T7 existía y sólo se alcanzaba tecleando la URL. La
      // etiqueta va literal y no por `MARCA_CORTA`: Contabilito es el nombre
      // de un servicio del catálogo, no el de la marca que lo aloja, y los dos
      // coincidieron alguna vez por accidente del rebrand.
      { id: 'contabilito', to: '/app/store/contabilito/use', label: 'Contabilito' },
      { id: 'perfil', to: '/app/profile', label: 'Perfil' },
    ]);
  });

  it('no hay Dashboard ni Historial de contribuyente', () => {
    const ids: string[] = getSidebarLinks().map((l) => l.id);
    expect(ids).not.toContain('dashboard');
    expect(ids).not.toContain('historial');
  });

  it('rutaInicial manda a la cartera', () => {
    expect(rutaInicial()).toBe('/app/clientes');
  });

  it('esContador solo es cierto para el contador', () => {
    expect(esContador('contador')).toBe(true);
    for (const tipo of ['asalariado', 'independiente', 'arrendamiento', 'plataformas', 'pyme', null] as const) {
      expect(esContador(tipo)).toBe(false);
    }
  });
});

describe('cuentaLista (K)', () => {
  it('sólo una cuenta de despacho con onboarding terminado entra a la app', () => {
    expect(cuentaLista({ onboardingComplete: true, contributorType: 'contador' })).toBe(true);
    expect(cuentaLista({ onboardingComplete: false, contributorType: 'contador' })).toBe(false);
  });

  it('una cuenta vieja de contribuyente vuelve al wizard para convertirse', () => {
    for (const tipo of ['asalariado', 'independiente', 'arrendamiento', 'plataformas', 'pyme', null] as const) {
      expect(cuentaLista({ onboardingComplete: true, contributorType: tipo }), String(tipo)).toBe(false);
    }
  });
});

describe('navActivo (E-06)', () => {
  const del = (id: string): SidebarLink =>
    getSidebarLinks().find((l) => l.id === id)!;

  /**
   * EL CASO QUE VALE EL BLOQUE. La nómina cuelga de `/app/clientes/{id}/nomina`
   * desde E-03 y el `to` de "Clientes" es prefijo de esa ruta: con la
   * coincidencia por prefijo de `NavLink`, el sidebar encendía la sección
   * equivocada en la pantalla que se proyecta en la demo.
   */
  it('en la nómina de un cliente: Nómina sí, Clientes no', () => {
    expect(navActivo(del('nomina'), '/app/clientes/taller/nomina')).toBe(true);
    expect(navActivo(del('clientes'), '/app/clientes/taller/nomina')).toBe(false);
  });

  it('en la cartera y en la ficha: Clientes sí, Nómina no', () => {
    for (const ruta of ['/app/clientes', '/app/clientes/taller']) {
      expect(navActivo(del('clientes'), ruta)).toBe(true);
      expect(navActivo(del('nomina'), ruta)).toBe(false);
    }
  });

  it('`/app/nomina` también enciende Nómina: sólo resuelve el cliente y redirige', () => {
    expect(navActivo(del('nomina'), '/app/nomina')).toBe(true);
    expect(navActivo(del('clientes'), '/app/nomina')).toBe(false);
  });

  it('nunca hay dos entradas encendidas a la vez', () => {
    const rutas = ['/app/clientes', '/app/clientes/demo', '/app/clientes/demo/nomina',
      '/app/nomina', '/app/calendario', '/app/profile'];
    for (const ruta of rutas) {
      const encendidas = getSidebarLinks().filter((l) => navActivo(l, ruta));
      expect(encendidas.length, `ruta ${ruta}`).toBeLessThanOrEqual(1);
    }
  });

  it('el query string del destino no participa de la comparación', () => {
    /**
     * Ningún enlace del sidebar lleva query desde E-07 —el de Calendario lo
     * perdió al dejar de apuntar a un tab—, así que el caso se prueba con un
     * enlace sintético en vez de con uno real: si no, este test no ejercitaría
     * nada y parecería que sí.
     */
    const conQuery: SidebarLink = { id: 'fiscalito', to: '/app/x?tab=y', label: 'X' };
    expect(navActivo(conQuery, '/app/x')).toBe(true);
    expect(navActivo(conQuery, '/app/otra')).toBe(false);
  });

  it('`end` sigue significando coincidencia exacta', () => {
    const exacto: SidebarLink = { id: 'perfil', to: '/app/x', label: 'X', end: true };
    expect(navActivo(exacto, '/app/x')).toBe(true);
    expect(navActivo(exacto, '/app/x/y')).toBe(false);
  });

  it('esRutaDeNomina reconoce las dos formas y nada más', () => {
    expect(esRutaDeNomina('/app/nomina')).toBe(true);
    expect(esRutaDeNomina('/app/clientes/demo/nomina')).toBe(true);
    expect(esRutaDeNomina('/app/clientes/demo')).toBe(false);
    expect(esRutaDeNomina('/app/clientes')).toBe(false);
    // Un cliente que se llamara "nomina" no debe confundir a nadie.
    expect(esRutaDeNomina('/app/clientes/nomina')).toBe(false);
  });
});

describe('rutaTieneAlcanceDeCliente', () => {
  it('muestra el selector en las pantallas que leen el cliente activo', () => {
    for (const ruta of ['/app/clientes', '/app/clientes/taller', '/app/clientes/taller/nomina',
      '/app/nomina', '/app/empleados', '/app/dispositivos', '/app/boveda', '/app/sat',
      '/app/store/fiscalito/use', '/app/store/contabilito/use']) {
      expect(rutaTieneAlcanceDeCliente(ruta), ruta).toBe(true);
    }
  });

  it('no lo muestra en Calendario (toda la cartera) ni en Perfil (del despacho)', () => {
    for (const ruta of ['/app/calendario', '/app/profile', '/app/store/fiscalito']) {
      expect(rutaTieneAlcanceDeCliente(ruta), ruta).toBe(false);
    }
  });
});

describe('getTabsForProfile (régimen del cliente activo)', () => {
  it('un cliente 612 ve el set completo', () => {
    expect(getTabsForProfile('612')).toEqual([
      'declaracion', 'anual', 'calendario', 'comparar', 'diot', 'retenciones', 'multiperiodo', 'estado',
    ]);
  });

  it('un cliente 626 NO ve DIOT ni Retenciones', () => {
    expect(getTabsForProfile('626')).toEqual(['declaracion', 'anual', 'calendario', 'comparar', 'estado']);
  });

  it('un cliente 612 y uno 626 no ven lo mismo', () => {
    expect(getTabsForProfile('612')).not.toEqual(getTabsForProfile('626'));
  });

  it('un cliente persona moral (601) abre en pagos provisionales PM', () => {
    expect(getTabsForProfile('601')).toEqual(['pagospm', 'calendario', 'declaracion']);
  });

  it('sin cliente elegido no hay tabs', () => {
    expect(getTabsForProfile(null)).toEqual([]);
    expect(getTabsForProfile('')).toEqual([]);
  });
});
