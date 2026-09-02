/**
 * Navegación por perfil (E-01).
 *
 * Los dos invariantes que protege este archivo:
 *
 * 1. Un CONTADOR ve exactamente cuatro entradas y ninguna de contribuyente. La
 *    aserción es sobre la lista COMPLETA, no sobre presencia: si alguien agrega
 *    "Historial" al sidebar del despacho, esto se cae.
 * 2. Los cinco tipos de contribuyente y el perfil sin tipo siguen viendo lo
 *    mismo que antes de E-01. La tarea es aditiva o no es.
 */

import { describe, expect, it } from 'vitest';
import {
  esContador,
  esRutaDeNomina,
  getSidebarLinks,
  getTabsForProfile,
  navActivo,
  rutaInicial,
  type SidebarLink,
  type TabFiscalito,
} from './navigation';
import type { ContributorType } from './contributorProfiles';

const CONTRIBUYENTES: (ContributorType | null)[] = [
  'asalariado', 'independiente', 'arrendamiento', 'plataformas', 'pyme', null,
];

describe('getSidebarLinks', () => {
  it('el contador ve Clientes / Nómina / Calendario / Perfil, en ese orden', () => {
    expect(getSidebarLinks('contador')).toEqual([
      { id: 'clientes', to: '/app/clientes', label: 'Clientes' },
      // E-03: el enlace no conoce el id del cliente; `/app/nomina` lo resuelve
      // desde el contexto. Así `getSidebarLinks` sigue siendo pura del perfil.
      { id: 'nomina', to: '/app/nomina', label: 'Nómina' },
      { id: 'calendario', to: '/app/store/fiscalito/use?tab=calendario', label: 'Calendario' },
      { id: 'perfil', to: '/app/profile', label: 'Perfil' },
    ]);
  });

  it.each(CONTRIBUYENTES)('el perfil %s conserva el sidebar de siempre', (tipo) => {
    expect(getSidebarLinks(tipo)).toEqual([
      { id: 'dashboard', to: '/app', label: 'Dashboard', end: true },
      { id: 'fiscalito', to: '/app/store/fiscalito/use', label: 'Fiscalito' },
      { id: 'historial', to: '/app/historial', label: 'Historial' },
      { id: 'nomina', to: '/app/nomina-demo', label: 'Nómina (demo)' },
      { id: 'perfil', to: '/app/profile', label: 'Perfil' },
    ]);
  });

  it('ningún contribuyente ve la pantalla de clientes del despacho', () => {
    for (const tipo of CONTRIBUYENTES) {
      expect(getSidebarLinks(tipo).map((l) => l.id)).not.toContain('clientes');
    }
  });

  it('rutaInicial manda al contador a sus clientes y al resto al dashboard', () => {
    expect(rutaInicial('contador')).toBe('/app/clientes');
    for (const tipo of CONTRIBUYENTES) {
      expect(rutaInicial(tipo)).toBe('/app');
    }
  });

  it('esContador solo es cierto para el contador', () => {
    expect(esContador('contador')).toBe(true);
    for (const tipo of CONTRIBUYENTES) {
      expect(esContador(tipo)).toBe(false);
    }
  });
});

describe('navActivo (E-06)', () => {
  const del = (id: string): SidebarLink =>
    getSidebarLinks('contador').find((l) => l.id === id)!;

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
      '/app/nomina', '/app/profile'];
    for (const ruta of rutas) {
      const encendidas = getSidebarLinks('contador').filter((l) => navActivo(l, ruta));
      expect(encendidas.length, `ruta ${ruta}`).toBeLessThanOrEqual(1);
    }
  });

  it('el query string del destino no participa de la comparación', () => {
    // El enlace de Calendario del contador lleva `?tab=`; el tab lo resuelve la
    // pantalla, no el resaltado.
    const calendario = del('calendario');
    expect(navActivo(calendario, calendario.to.split('?')[0])).toBe(true);
  });

  it('`end` sigue significando coincidencia exacta', () => {
    const dashboard = getSidebarLinks(null).find((l) => l.id === 'dashboard')!;
    expect(navActivo(dashboard, '/app')).toBe(true);
    expect(navActivo(dashboard, '/app/historial')).toBe(false);
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

describe('getTabsForProfile', () => {
  /**
   * EL CASO QUE VALE EL ARCHIVO. Un despacho tiene régimen 612 o 626, así que
   * si la rama de contador se evaluara DESPUÉS de las de régimen, caería en la
   * de RESICO o en la de Actividad Empresarial y vería pre-declaración, DIOT y
   * retenciones. Los dos regímenes que el perfil permite están probados.
   */
  it.each(['612', '626'])('el contador con régimen %s solo ve el calendario', (regimen) => {
    expect(getTabsForProfile('contador', regimen)).toEqual(['calendario']);
  });

  it('el contador sin régimen capturado tampoco ve tabs de contribuyente', () => {
    expect(getTabsForProfile('contador', null)).toEqual(['calendario']);
    expect(getTabsForProfile('contador', '')).toEqual(['calendario']);
  });

  // Regresión: esta función sirve a FiscalitoServicePage y a DashboardPage a la
  // vez desde E-01. Un cambio aquí mueve las dos pantallas.
  const CASOS: [string | null, string | null, TabFiscalito[]][] = [
    ['asalariado', '605', ['deducciones', 'calendario']],
    ['pyme', '612', ['declaracion', 'calendario', 'comparar', 'diot', 'retenciones', 'multiperiodo', 'estado']],
    ['independiente', '626', ['declaracion', 'calendario', 'comparar', 'estado']],
    ['independiente', '612', ['declaracion', 'calendario', 'comparar', 'diot', 'retenciones', 'multiperiodo', 'estado']],
    ['arrendamiento', '606', ['declaracion', 'calendario', 'comparar', 'multiperiodo', 'estado']],
    ['plataformas', '625', ['declaracion', 'calendario', 'estado']],
    [null, null, ['declaracion', 'calendario', 'estado']],
  ];

  it.each(CASOS)('tipo=%s regimen=%s no cambia con E-01', (tipo, regimen, esperado) => {
    expect(getTabsForProfile(tipo, regimen)).toEqual(esperado);
  });
});
