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
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

/** Enlaces visibles del sidebar de escritorio (el mini va con display:none). */
function enlacesDelSidebar(container: HTMLElement): string[] {
  const aside = container.querySelector('.sidebar-full');
  if (!aside) throw new Error('no se renderizó el sidebar');
  return within(aside as HTMLElement).getAllByRole('link').map((a) => a.textContent?.trim() ?? '');
}

afterEach(() => {
  perfilMock.actual = perfilBase;
  cleanup();
});

describe('sidebar de AppLayout', () => {
  it('el contador ve exactamente sus cuatro enlaces', () => {
    perfilMock.actual = { ...perfilBase, contributorType: 'contador', regimen: '612' };
    const { container } = montar();

    // Lista completa y en orden: si alguien agrega un enlace de contribuyente
    // al sidebar del despacho, esto se cae.
    expect(enlacesDelSidebar(container)).toEqual(['Clientes', 'Nómina', 'Calendario', 'Perfil']);
  });

  it('el contador no ve Dashboard, Fiscalito ni Historial', () => {
    perfilMock.actual = { ...perfilBase, contributorType: 'contador', regimen: '612' };
    montar();

    expect(screen.queryByRole('link', { name: 'Dashboard' })).toBeNull();
    expect(screen.queryByRole('link', { name: 'Fiscalito' })).toBeNull();
    expect(screen.queryByRole('link', { name: 'Historial' })).toBeNull();
  });

  it('el contribuyente conserva sus cinco enlaces de siempre', () => {
    perfilMock.actual = { ...perfilBase, contributorType: 'independiente' };
    const { container } = montar();

    expect(enlacesDelSidebar(container)).toEqual([
      'Dashboard', 'Fiscalito', 'Historial', 'Nómina (demo)', 'Perfil',
    ]);
    expect(screen.queryByRole('link', { name: 'Clientes' })).toBeNull();
  });

  it('un perfil sin tipo ve el sidebar de contribuyente', () => {
    const { container } = montar();
    expect(enlacesDelSidebar(container)).toHaveLength(5);
  });

  /**
   * `end: true` del enlace Dashboard es fácil de perder al mover los links a
   * `navigation.ts`, y sin él "/app" queda marcado como activo en TODAS las
   * subrutas: el sidebar señalaría dos secciones a la vez en la demo.
   */
  it('Dashboard no queda marcado activo estando en otra sección', () => {
    perfilMock.actual = { ...perfilBase, contributorType: 'independiente' };
    const { container } = montar('/app/historial');
    const aside = container.querySelector('.sidebar-full') as HTMLElement;

    const dashboard = within(aside).getByRole('link', { name: 'Dashboard' });
    const historial = within(aside).getByRole('link', { name: 'Historial' });

    expect(dashboard.className).not.toContain('nav-item-active');
    expect(historial.className).toContain('nav-item-active');
  });
});
