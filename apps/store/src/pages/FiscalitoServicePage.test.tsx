/**
 * La única pantalla de Fiscalito que ve un despacho (E-01).
 *
 * Cubre dos cosas que `navigation.test.ts` no puede ver:
 *
 * 1. Que la pantalla USE el filtro — incluido el deep-link `?tab=declaracion`,
 *    que un contador puede recibir de un enlace viejo o del propio agente.
 * 2. El copy y el back-link. Sin esto, la única pantalla de Fiscalito que ve el
 *    contador puede anunciarle "Calcula tus pre-declaraciones ISR/IVA" y
 *    devolverlo al marketplace de contribuyente.
 */

import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { UserProfile } from '../context/ProfileContext';

const perfilBase: UserProfile = {
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

const perfilMock = { actual: perfilBase };

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({ user: { uid: 'uid-demo', email: 'demo@ejemplo.mx' }, loading: false }),
}));

vi.mock('../context/ProfileContext', () => ({
  useProfile: () => ({ profile: perfilMock.actual, loading: false }),
}));

vi.mock('../services/firebase', () => ({ auth: {}, db: {}, default: {} }));
vi.mock('../services/declaracionesHistory', () => ({
  guardarDeclaracion: vi.fn(),
  obtenerHistorial: vi.fn(async () => []),
  obtenerEstadisticas: vi.fn(),
}));

// El tab de calendario pega a la API al montar; aquí solo importa qué tabs se
// pintan. El resto del módulo (tipoParaCalendario incluido) queda real.
vi.mock('../services/fiscalAgentApi', async () => {
  const real = await vi.importActual<typeof import('../services/fiscalAgentApi')>('../services/fiscalAgentApi');
  return { ...real, obtenerCalendario: vi.fn(async () => ({ obligaciones: [] })) };
});

const { default: FiscalitoServicePage } = await import('./FiscalitoServicePage');
// El tab de pre-declaracion (el del contribuyente) usa useAgent.
const { AgentProvider } = await import('../agent/AgentContext');

function montar(ruta = '/app/store/fiscalito/use') {
  return render(
    <MemoryRouter initialEntries={[ruta]}>
      <AgentProvider>
        <FiscalitoServicePage />
      </AgentProvider>
    </MemoryRouter>,
  );
}

afterEach(() => {
  perfilMock.actual = perfilBase;
  cleanup();
});

describe('FiscalitoServicePage — cuenta de despacho', () => {
  it('solo pinta el tab de calendario', () => {
    montar();

    expect(screen.getByText('Calendario fiscal')).toBeTruthy();
    for (const oculto of ['Pre-declaración', 'DIOT', 'Retenciones', 'Comparar regímenes', 'Estado de cuenta', 'Multi-periodo']) {
      expect(screen.queryByText(oculto)).toBeNull();
    }
  });

  // Un enlace viejo, o el propio agente, pueden mandar al contador a un tab que
  // su perfil no permite: tiene que degradar al calendario, no pintarlo.
  it('un deep-link a pre-declaración degrada al calendario', () => {
    montar('/app/store/fiscalito/use?tab=declaracion');

    expect(screen.queryByText('Pre-declaración')).toBeNull();
    expect(screen.getByText('Calendario fiscal')).toBeTruthy();
  });

  it('el encabezado habla del despacho, no de pre-declaraciones', () => {
    montar();

    expect(screen.getByText('Las obligaciones fiscales de tu despacho')).toBeTruthy();
    expect(screen.queryByText('Calcula tus pre-declaraciones ISR/IVA')).toBeNull();
  });

  it('el back-link devuelve a Clientes, no al marketplace de contribuyente', () => {
    montar();

    const volver = screen.getByRole('link', { name: /Clientes/ });
    expect(volver.getAttribute('href')).toBe('/app/clientes');
  });

  it('el contribuyente conserva sus tabs y su back-link', () => {
    perfilMock.actual = { ...perfilBase, contributorType: 'independiente', regimen: '626' };
    montar();

    expect(screen.getByText('Pre-declaración')).toBeTruthy();
    expect(screen.getByText('Calcula tus pre-declaraciones ISR/IVA')).toBeTruthy();
    expect(screen.getByRole('link', { name: /Información/ }).getAttribute('href')).toBe('/app/store/fiscalito');
  });
});
