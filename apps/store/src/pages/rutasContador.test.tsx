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

// G-03: las pantallas piden la cartera. El doble viene vacío, así que
// `useNominaCliente` cae a los empleados de la ficha del backend — el mismo
// camino que estas pruebas medían antes de G-01.
vi.mock('../context/carteraStore', async () => {
  const { carteraDePrueba } = await import('../test/carteraDePrueba');
  // La LISTA de clientes sale de la cartera (G-03), así que el doble trae
  // clientes: con el vacío por default, `/app/clientes` pinta el estado "cartera
  // vacía" y la prueba dejaría de medir lo que dice medir.
  const CLIENTES = [
    {
      id: 'demo', nombre: 'Cliente Demo',
      giro: 'Servicios', origen: 'sintetico',
      prima_riesgo: '0.0054355', clase_riesgo: null, clave_periodicidad: '04',
      zona: 'general',
      periodo_sugerido: { inicio: '2026-08-16', fin: '2026-08-31', fecha_pago: null },
      empleados: [],
    },
  ];
  return {
    useCartera: () =>
      carteraDePrueba({
        clientes: CLIENTES,
        origen: 'firestore',
        soloLectura: false,
        clientePorId: (id: string) => CLIENTES.find((c) => c.id === id) ?? null,
      }),
  };
});


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
// Un DashboardStats en ceros, no `{}`: si la promesa resolviera antes de la
// aserción, `getStatsForType` leería campos de undefined y el test moriría por
// una razón que no tiene nada que ver con rutas.
// La cartera tiene sus propios tests; aquí sólo importa que la ruta resuelva.
vi.mock('../context/clienteActivoStore', () => ({
  useClienteActivo: () => ({
    clientes: [{ id: 'demo', nombre: 'Cliente Demo', giro: 'Servicios', origen: 'sintetico', num_empleados: 3, prima_riesgo: '0.0054355', clase_riesgo: null, clave_periodicidad: '04', zona: 'general' }],
    clienteId: 'demo',
    cliente: null,
    loading: false,
    error: null,
    setClienteId: vi.fn(),
    recargar: vi.fn(),
  }),
}));

vi.mock('../services/declaracionesHistory', () => ({
  obtenerEstadisticas: vi.fn(async () => ({
    totalDeclaraciones: 0,
    declaracionesEsteMes: 0,
    ultimoISR: 0,
    ultimoIVA: 0,
    ultimoTotal: 0,
    saldoFavorAcumulado: 0,
    promedioMensual: 0,
  })),
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
    expect(screen.getByText('Cliente Demo')).toBeTruthy();
    expect(container.querySelector('.page-container')).toBeTruthy();
  });

  it('el contribuyente sigue viendo su dashboard en /app', () => {
    perfilMock.actual = { ...perfilBase, contributorType: 'independiente' };
    montar('/app');

    expect(screen.getByText(/Bienvenido/)).toBeTruthy();
  });
});
