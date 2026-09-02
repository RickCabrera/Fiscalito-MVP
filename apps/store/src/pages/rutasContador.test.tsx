/**
 * Rutas del despacho (E-01).
 *
 * Dos modos de falla concretos, los dos invisibles para un test de la función
 * pura de navegación:
 *
 * 1. `/app/clientes` sin `<Route>` deja el área de contenido EN BLANCO (no hay
 *    catch-all bajo `/app`), y "Clientes" es el primer enlace del contador.
 * 2. `/app` sigue siendo la ruta índice: sin el redirect, un despacho que
 *    teclee la URL o vuelva del onboarding aterriza en el dashboard de
 *    contribuyente, con stats de declaraciones que no son suyas.
 */

import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
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
  useAuth: () => ({ user: { uid: 'uid-demo', email: 'demo@ejemplo.mx' }, loading: false }),
}));

vi.mock('../context/ProfileContext', () => ({
  useProfile: () => ({ profile: perfilMock.actual, loading: false, isOnboardingComplete: () => true }),
}));

// El dashboard lee Firestore al montar; aquí solo importa a dónde navega.
vi.mock('../services/declaracionesHistory', () => ({
  obtenerEstadisticas: vi.fn(async () => ({})),
  obtenerHistorial: vi.fn(async () => []),
}));

const { default: DashboardPage } = await import('./DashboardPage');
const { default: ClientesPage } = await import('./ClientesPage');

function montar(ruta: string) {
  return render(
    <MemoryRouter initialEntries={[ruta]}>
      <Routes>
        <Route path="/app" element={<DashboardPage />} />
        <Route path="/app/clientes" element={<ClientesPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

afterEach(() => {
  perfilMock.actual = perfilBase;
  cleanup();
});

describe('rutas del contador', () => {
  it('/app manda al contador a su lista de clientes', () => {
    perfilMock.actual = { ...perfilBase, contributorType: 'contador', regimen: '612', nombreDespacho: 'Despacho Demo' };
    montar('/app');

    expect(screen.getByRole('heading', { name: 'Clientes' })).toBeTruthy();
    // Y no aparece el saludo del dashboard de contribuyente.
    expect(screen.queryByText(/Bienvenido/)).toBeNull();
  });

  it('/app/clientes resuelve y pinta la pantalla, no un hueco en blanco', () => {
    perfilMock.actual = { ...perfilBase, contributorType: 'contador', regimen: '612', nombreDespacho: 'Despacho Demo' };
    const { container } = montar('/app/clientes');

    expect(screen.getByRole('heading', { name: 'Clientes' })).toBeTruthy();
    expect(screen.getByText('Cartera de Despacho Demo')).toBeTruthy();
    expect(container.querySelector('.page-container')).toBeTruthy();
  });

  it('el contribuyente sigue viendo su dashboard en /app', () => {
    perfilMock.actual = { ...perfilBase, contributorType: 'independiente' };
    montar('/app');

    expect(screen.getByText(/Bienvenido/)).toBeTruthy();
  });
});
