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
import { esContador, getSidebarLinks, getTabsForProfile, rutaInicial, type TabFiscalito } from './navigation';
import type { ContributorType } from './contributorProfiles';

const CONTRIBUYENTES: (ContributorType | null)[] = [
  'asalariado', 'independiente', 'arrendamiento', 'plataformas', 'pyme', null,
];

describe('getSidebarLinks', () => {
  it('el contador ve Clientes / Nómina / Calendario / Perfil, en ese orden', () => {
    expect(getSidebarLinks('contador')).toEqual([
      { id: 'clientes', to: '/app/clientes', label: 'Clientes' },
      { id: 'nomina', to: '/app/nomina-demo', label: 'Nómina' },
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
