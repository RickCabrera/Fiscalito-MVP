/**
 * Registro de rutas (E-02).
 *
 * EL HUECO QUE ESTO CIERRA: mientras el árbol de `<Routes>` vivió dentro de
 * `main.tsx`, ningún test podía comprobar que una ruta estuviera registrada
 * —ese archivo llama a `createRoot` al importarse y no monta en jsdom—. E-01
 * agregó `/app/clientes` y lo dejó declarado como no verificado.
 *
 * El modo de falla que atrapa es silencioso a medias: sin `<Route>`, no hay
 * catch-all bajo `/app`, así que el sidebar navega y el área de contenido queda
 * **en blanco**, sin error en consola.
 */

import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { UserProfile } from './context/ProfileContext';

const perfilContador: UserProfile = {
  contributorType: 'contador',
  rfc: 'XAXX010101000',
  regimen: '612',
  nombre: 'Contadora Demo',
  actividad: '',
  cp: '',
  telefono: '',
  nombreNegocio: '',
  numEmpleados: '',
  nombreDespacho: 'Despacho Demo',
  onboardingComplete: true,
};

vi.mock('./context/AuthContext', () => ({
  useAuth: () => ({
    user: { uid: 'uid-demo', email: 'demo@ejemplo.mx' },
    loading: false,
    signOut: vi.fn(),
  }),
}));

vi.mock('./context/ProfileContext', () => ({
  useProfile: () => ({
    profile: perfilContador,
    loading: false,
    isOnboardingComplete: () => true,
  }),
}));

vi.mock('./components/FiscalitoVoiceChat', () => ({ default: () => null }));
vi.mock('./components/ThemeToggle', () => ({ default: () => null }));
vi.mock('./services/firebase', () => ({ auth: {}, db: {}, default: {} }));
vi.mock('./services/declaracionesHistory', () => ({
  guardarDeclaracion: vi.fn(),
  obtenerHistorial: vi.fn(async () => []),
  obtenerEstadisticas: vi.fn(async () => null),
}));

const CLIENTES = [
  {
    id: 'demo', nombre: 'Servicios Administrativos Integrales', giro: 'Servicios', origen: 'fixtures-s04',
    num_empleados: 9, prima_riesgo: '0.0054355', clase_riesgo: null,
    clave_periodicidad: '04', zona: 'general',
  },
];

vi.mock('./services/despachoApi', async () => {
  const real = await vi.importActual<typeof import('./services/despachoApi')>('./services/despachoApi');
  return {
    ...real,
    obtenerClientes: vi.fn(async () => CLIENTES),
    obtenerCliente: vi.fn(async () => ({
      ...CLIENTES[0],
      empleados: [
        {
          empleado_no: 'E-01', nombre: 'PERSONA UNO', puesto: '',
          salario_diario: '316.00', salario_diario_integrado: '331.58', zona: 'general',
          fecha_alta: null, antiguedad_anios: null, factor: '1.0493', factor_implicito: true,
        },
      ],
      periodo_sugerido: { inicio: '2026-08-16', fin: '2026-08-31', fecha_pago: '2026-08-31' },
      fecha_referencia: '2026-09-01',
    })),
  };
});

const { default: AppRoutes } = await import('./AppRoutes');
const { ClienteActivoProvider } = await import('./context/ClienteActivoContext');

function montar(ruta: string) {
  return render(
    <MemoryRouter initialEntries={[ruta]}>
      <ClienteActivoProvider>
        <AppRoutes />
      </ClienteActivoProvider>
    </MemoryRouter>,
  );
}

afterEach(cleanup);

describe('rutas registradas', () => {
  it('/app/clientes pinta la cartera, no un hueco en blanco', async () => {
    montar('/app/clientes');
    expect(await screen.findByRole('heading', { name: 'Clientes' })).toBeTruthy();
    await waitFor(() => expect(screen.getByText('Servicios Administrativos Integrales')).toBeTruthy());
  });

  it('/app/clientes/:id pinta la ficha del cliente', async () => {
    montar('/app/clientes/demo');
    await waitFor(() =>
      expect(screen.getByRole('heading', { name: 'Servicios Administrativos Integrales' })).toBeTruthy(),
    );
    expect(screen.getByText('Plantilla')).toBeTruthy();
  });

  it('/app/profile sigue registrada', async () => {
    montar('/app/profile');
    await waitFor(() => expect(screen.getByRole('heading', { level: 1 })).toBeTruthy());
  });

  it('/login es pública y no pasa por el layout', () => {
    const { container } = montar('/login');
    expect(container.querySelector('.sidebar-full')).toBeNull();
  });
});
