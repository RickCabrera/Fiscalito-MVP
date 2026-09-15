/**
 * Navegación por perfil (E-01).
 *
 * Los dos invariantes que protege este archivo:
 *
 * 1. Un CONTADOR ve una lista EXACTA y ninguna entrada de contribuyente. La
 *    aserción es sobre la lista COMPLETA, no sobre presencia: si alguien agrega
 *    "Historial" al sidebar del despacho, esto se cae. La lista lleva **siete**
 *    entradas: las cuatro de E-01, más Empleados y Dispositivos (R-05), más
 *    Fiscalito —el del cliente activo— que sumó T1. "Historial" y "Dashboard"
 *    siguen siendo las que no pueden aparecer, porque ésas sí serían suyas.
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
import { modoDespacho } from '../test/modoDespacho';
import { MARCA_CORTA } from './marca';

/**
 * MODO DESPACHO (O-01).
 *
 * Este archivo mide el producto de las épicas E, G y R: cartera de clientes,
 * selector de cliente activo y rutas `/app/clientes`. Desde el pivote, el modo
 * por default de la app es **empresa única**, así que el modo en el que corre
 * se declara aquí en vez de heredarse del ambiente.
 *
 * No cambia ninguna aserción: cambia el mundo en el que se evalúan, que es
 * exactamente lo que el flag hace en producción.
 */
modoDespacho();

const CONTRIBUYENTES: (ContributorType | null)[] = [
  'asalariado', 'independiente', 'arrendamiento', 'plataformas', 'pyme', null,
];

describe('getSidebarLinks', () => {
  it('el contador ve Clientes / Empleados / Dispositivos / Nómina / Calendario / Fiscalito / Perfil, en ese orden', () => {
    expect(getSidebarLinks('contador')).toEqual([
      { id: 'clientes', to: '/app/clientes', label: 'Clientes' },
      // R-05: entradas propias. Antes los empleados sólo se alcanzaban entrando
      // a la ficha del cliente y cambiando de pestaña, y los dispositivos no
      // existían. Las dos operan sobre el cliente activo, igual que Nómina, y
      // por eso van juntas y antes de ella: es el orden del flujo real
      // —plantilla, aparatos, y luego la nómina que sale de los dos—.
      { id: 'empleados', to: '/app/empleados', label: 'Empleados' },
      { id: 'dispositivos', to: '/app/dispositivos', label: 'Dispositivos' },
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
      { id: 'perfil', to: '/app/profile', label: 'Perfil' },
    ]);
  });

  it('el contador NO ve Dashboard ni Historial: ésos sí serían suyos', () => {
    // La otra mitad del invariante 1. Fiscalito entró en T1 porque lo que abre
    // es de su cliente; un dashboard de contribuyente y un historial de
    // declaraciones propias no tienen sujeto en una cuenta de despacho.
    const ids = getSidebarLinks('contador').map((l) => l.id);
    expect(ids).not.toContain('dashboard');
    expect(ids).not.toContain('historial');
  });

  it('ningún contribuyente ve las entradas del despacho', () => {
    // La simétrica de la de arriba, extendida a lo que R-05 agrega: las tres
    // pantallas del despacho leen la CARTERA, que un contribuyente no tiene.
    for (const tipo of CONTRIBUYENTES) {
      const ids = getSidebarLinks(tipo).map((l) => l.id);
      expect(ids).not.toContain('empleados');
      expect(ids).not.toContain('dispositivos');
    }
  });

  it.each(CONTRIBUYENTES)('el perfil %s conserva el sidebar de siempre', (tipo) => {
    expect(getSidebarLinks(tipo)).toEqual([
      { id: 'dashboard', to: '/app', label: 'Dashboard', end: true },
      // O-02: la ruta es interna y no cambia; la etiqueta sale de la marca.
      { id: 'fiscalito', to: '/app/store/fiscalito/use', label: MARCA_CORTA },
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
      '/app/nomina', '/app/calendario', '/app/profile'];
    for (const ruta of rutas) {
      const encendidas = getSidebarLinks('contador').filter((l) => navActivo(l, ruta));
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
   * EL CASO QUE VALE EL ARCHIVO, REESCRITO EN T1.
   *
   * Lo que se mide sigue siendo lo mismo —qué ve un despacho en Fiscalito— pero
   * cambió el SUJETO: hasta E-07 el `regimen` que llegaba aquí con
   * `contributorType: 'contador'` era el del despacho (y desde E-05 venía
   * vacío, así que el tab que le quedaba estaba muerto). Desde T1 es el del
   * CLIENTE ACTIVO, que sí existe y sí se captura en el alta.
   *
   * El caso que decide la tarea es el par 612 / 626, con el corte que E-01 ya
   * traía y que §D30 deja pendiente de confirmar con la contadora. Lo que se
   * fija aquí no es la regla fiscal —esa puede moverse— sino que el régimen del
   * cliente **se aplique**: si alguien colapsara las dos ramas al set completo,
   * los dos clientes verían lo mismo y la pantalla se vería perfectamente bien.
   */
  it('el contador con un cliente 612 ve el set completo', () => {
    expect(getTabsForProfile('contador', '612')).toEqual([
      'declaracion', 'calendario', 'comparar', 'diot', 'retenciones', 'multiperiodo', 'estado',
    ]);
  });

  it('el contador con un cliente 626 NO ve DIOT ni Retenciones', () => {
    const tabs = getTabsForProfile('contador', '626');
    expect(tabs).toEqual(['declaracion', 'calendario', 'comparar', 'estado']);
    expect(tabs).not.toContain('diot');
    expect(tabs).not.toContain('retenciones');
  });

  it('el contador con un cliente 612 y uno 626 no ve lo mismo', () => {
    // La aserción que no se puede satisfacer por accidente: dos listas iguales
    // pasarían los dos tests de arriba sólo si además fueran las esperadas,
    // pero ésta se cae en cuanto el filtro por régimen deje de aplicarse.
    expect(getTabsForProfile('contador', '612')).not.toEqual(getTabsForProfile('contador', '626'));
  });

  it('el contador SIN cliente elegido no ve ningún tab', () => {
    // No es el caso de E-07 con otro nombre: aquí el vacío significa "falta el
    // dato", y `FiscalitoServicePage` pinta el estado con el selector en vez de
    // una tira de tabs sobre un cliente inexistente.
    expect(getTabsForProfile('contador', null)).toEqual([]);
    expect(getTabsForProfile('contador', '')).toEqual([]);
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
