/**
 * Sidebar por perfil (E-01) — el criterio literal de la tarea: "creo cuenta
 * como contador y veo el sidebar correcto".
 *
 * POR QUÉ EXISTE ADEMÁS DE navigation.test.ts
 * -------------------------------------------
 * `getSidebarLinks` puede estar perfecta y AppLayout ignorarla. Este archivo
 * renderiza el layout de verdad y cuenta los enlaces que salen del DOM.
 */

import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import type { UserProfile } from '../context/ProfileContext';
import type { ClienteResumen } from '../services/despachoApi';
import { MARCA_CORTA } from '../services/marca';


const perfilBase: UserProfile = {
  contributorType: null,
  rfc: 'XAXX010101000',
  regimen: '626',
  nombre: 'Persona Demo',
  actividad: '',
  cp: '',
  telefono: '',
  nombreNegocio: '',
  numEmpleados: '',
  nombreDespacho: '',
  onboardingComplete: true,
};

const perfilMock = { actual: perfilBase };

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({
    user: { uid: 'uid-demo', email: 'demo@ejemplo.mx' },
    loading: false,
    signOut: vi.fn(),
  }),
}));

vi.mock('../context/ProfileContext', () => ({
  useProfile: () => ({
    profile: perfilMock.actual,
    loading: false,
    isOnboardingComplete: () => true,
  }),
}));

// La cartera tiene sus propios tests; aquí sólo se necesita el cliente activo,
// que desde E-06 el sidebar imprime bajo la entrada "Nómina".
const TALLER: ClienteResumen = {
  id: 'taller', nombre: 'Taller Mecánico Nogal', giro: 'Reparación', origen: 'sintetico',
  num_empleados: 12, prima_riesgo: '0.0259840', clase_riesgo: 3,
  clave_periodicidad: '04', zona: 'general',
};

const clienteActivo: { actual: ClienteResumen | null } = { actual: TALLER };

vi.mock('../context/clienteActivoStore', () => ({
  useClienteActivo: () => ({
    clientes: clienteActivo.actual ? [clienteActivo.actual] : [],
    clienteId: clienteActivo.actual?.id ?? null,
    cliente: clienteActivo.actual,
    loading: false,
    error: null,
    setClienteId: vi.fn(),
    recargar: vi.fn(),
  }),
}));

// El chat de voz habla con OpenAI y el toggle necesita ThemeProvider: ninguno
// de los dos tiene que ver con qué enlaces muestra el sidebar.
vi.mock('./FiscalitoVoiceChat', () => ({ default: () => null }));
// El selector de cliente tiene sus propios tests y necesita su provider; aquí
// lo que se mide son los enlaces del sidebar.
vi.mock('./SelectorCliente', () => ({ default: () => null }));
vi.mock('./ThemeToggle', () => ({ default: () => null }));

const { default: AppLayout } = await import('./AppLayout');

function montar(ruta = '/app') {
  return render(
    <MemoryRouter initialEntries={[ruta]}>
      <Routes>
        <Route path="/app" element={<AppLayout />}>
          <Route index element={<div>contenido</div>} />
          <Route path="historial" element={<div>historial</div>} />
          <Route path="clientes" element={<div>clientes</div>} />
          <Route path="clientes/:id" element={<div>ficha</div>} />
          <Route path="clientes/:id/nomina" element={<div>nomina</div>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

/** El enlace del sidebar de escritorio cuyo texto empieza con `etiqueta`. */
function enlace(container: HTMLElement, etiqueta: string): HTMLElement {
  const aside = container.querySelector('.sidebar-full') as HTMLElement;
  const encontrado = within(aside)
    .getAllByRole('link')
    .find((a) => (a.textContent ?? '').startsWith(etiqueta));
  if (!encontrado) throw new Error(`no hay enlace "${etiqueta}" en el sidebar`);
  return encontrado;
}

/**
 * Etiquetas de los enlaces del sidebar de escritorio (el mini va con
 * `display:none`).
 *
 * Descuenta el renglón del cliente activo que E-06 imprime bajo "Nómina": lo
 * que este helper mide es **qué entradas hay y en qué orden**, no qué dice cada
 * una de su cliente. El nombre del cliente se asserta aparte, más abajo.
 */
function enlacesDelSidebar(container: HTMLElement): string[] {
  // P3-09: la campana de alertas vive en la cabecera del sidebar, fuera del `<nav>`; los
  // enlaces de navegación son los del `<nav>`.
  const aside = container.querySelector('.sidebar-full nav');
  if (!aside) throw new Error('no se renderizó el sidebar');
  return within(aside as HTMLElement).getAllByRole('link').map((a) => {
    const soloEtiqueta = a.cloneNode(true) as HTMLElement;
    soloEtiqueta.querySelectorAll('[data-cliente]').forEach((n) => n.remove());
    return soloEtiqueta.textContent?.trim() ?? '';
  });
}

afterEach(() => {
  perfilMock.actual = perfilBase;
  clienteActivo.actual = TALLER;
  cleanup();
});

/**
 * E-06 — en qué cliente estoy y qué sección estoy viendo.
 *
 * EL BUG QUE ESTO FIJA: la nómina vive en `/app/clientes/{id}/nomina` desde
 * E-03, y el `to` del enlace "Clientes" es prefijo de esa ruta. Con el
 * `isActive` de `NavLink`, el sidebar encendía **Clientes** y dejaba **Nómina**
 * apagada, justo en la pantalla que se proyecta en la demo.
 */
describe('resaltado del sidebar en la nómina de un cliente', () => {
  function montarContadorEn(ruta: string) {
    perfilMock.actual = { ...perfilBase, contributorType: 'contador', regimen: '612' };
    return montar(ruta);
  }

  it('en la nómina de un cliente se resalta Nómina, no Clientes', () => {
    const { container } = montarContadorEn('/app/clientes/taller/nomina');

    expect(enlace(container, 'Nómina').className).toContain('nav-item-active');
    expect(enlace(container, 'Clientes').className).not.toContain('nav-item-active');
  });

  it('el aria-current también se mueve, no sólo el color', () => {
    /**
     * Pisar el estilo de `NavLink` habría dejado el resaltado correcto a la
     * vista y el `aria-current` diciendo "Clientes": un lector de pantalla
     * seguiría anunciando la sección equivocada.
     */
    const { container } = montarContadorEn('/app/clientes/taller/nomina');

    expect(enlace(container, 'Nómina').getAttribute('aria-current')).toBe('page');
    expect(enlace(container, 'Clientes').getAttribute('aria-current')).toBeNull();
  });

  it('en la ficha del cliente sí se resalta Clientes', () => {
    const { container } = montarContadorEn('/app/clientes/taller');

    expect(enlace(container, 'Clientes').className).toContain('nav-item-active');
    expect(enlace(container, 'Nómina').className).not.toContain('nav-item-active');
  });

  it('el sidebar dice de qué cliente es esa nómina', () => {
    const { container } = montarContadorEn('/app/clientes/taller/nomina');

    expect(enlace(container, 'Nómina').textContent).toContain('Taller Mecánico Nogal');
  });

  it('sin cliente activo la entrada Nómina no inventa un nombre', () => {
    clienteActivo.actual = null;
    const { container } = montarContadorEn('/app/clientes');

    expect(enlace(container, 'Nómina').textContent?.trim()).toBe('Nómina');
  });

});

describe('sidebar de AppLayout', () => {
  it('el contador ve exactamente sus nueve enlaces', () => {
    perfilMock.actual = { ...perfilBase, contributorType: 'contador', regimen: '612' };
    const { container } = montar();

    // Lista completa y en orden: si alguien agrega un enlace de contribuyente
    // al sidebar del despacho, esto se cae. R-05 sumó Empleados y Dispositivos;
    // T1 sumó el servicio fiscal, que abre el del CLIENTE ACTIVO —no el del
    // despacho, que es lo que E-07 quitó y sigue sin existir. Contabilito entró
    // después: la portada ya lo anunciaba en BETA y su pantalla (T7) sólo se
    // alcanzaba tecleando la URL. P0-03 sumó la Bóveda de CFDI del cliente activo
    // y P1-02 la Descarga SAT, que la llena.
    expect(enlacesDelSidebar(container)).toEqual([
      'Inicio', 'Clientes', 'Empleados', 'Dispositivos', 'Bóveda', 'Descarga SAT', 'Nómina',
      'Calendario', MARCA_CORTA, 'Contabilito', 'Calculadoras', 'Cobranza', 'Perfil',
    ]);
  });

  it('cada enlace del sidebar lleva su icono', () => {
    // NO se cuenta cuántos enlaces hay: eso ya lo afirma `navigation.test.ts`,
    // y contar seis no prueba nada de este archivo.
    //
    // El riesgo REAL de `AppLayout` es el mapa `ICONOS`, que se indexa por
    // `NavId`: una clave faltante renderiza **nada** y la etiqueta del enlace
    // sale igual, así que el sidebar se ve casi bien y nadie lo nota. Con
    // `NavId` creciendo de 7 a 9 en R-05, es el error probable.
    perfilMock.actual = { ...perfilBase, contributorType: 'contador', regimen: '612' };
    const { container } = montar();

    const enlaces = Array.from(
      container.querySelectorAll('.sidebar-full nav a'),
    ) as HTMLElement[];
    expect(enlaces.length).toBeGreaterThan(0);
    for (const enlace of enlaces) {
      expect(
        enlace.querySelector('svg'),
        `el enlace "${enlace.textContent}" no tiene icono: falta su clave en ICONOS`,
      ).not.toBeNull();
    }
  });

  it('el contador no ve Dashboard ni Historial, y el servicio fiscal sí (T1)', () => {
    /**
     * Cambió en T1, y el criterio de por qué cambió está en el enlace mismo:
     * Dashboard e Historial son del CONTRIBUYENTE —sus stats, sus declaraciones
     * guardadas— y en una cuenta de despacho no tienen sujeto. El servicio
     * fiscal sí lo tiene desde T1: el del cliente activo.
     */
    perfilMock.actual = { ...perfilBase, contributorType: 'contador', regimen: '612' };
    montar();

    expect(screen.queryByRole('link', { name: 'Dashboard' })).toBeNull();
    expect(screen.queryByRole('link', { name: 'Historial' })).toBeNull();
    expect(screen.getByRole('link', { name: MARCA_CORTA }).getAttribute('href'))
      .toBe('/app/store/fiscalito/use');
  });

});
