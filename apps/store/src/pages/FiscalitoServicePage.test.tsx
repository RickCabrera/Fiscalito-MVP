/**
 * Fiscalito y las cuentas de despacho (E-01, reescrito en E-07).
 *
 * E-01 le dejaba al contador UN tab: el calendario de sus propias obligaciones
 * como persona física (§D21, provisional). E-05 deja de pedirle RFC y régimen
 * —y quita del perfil el único lugar donde capturarlos—, y `CalendarioTab`
 * corta en seco sin esos dos campos: el tab quedaba muerto.
 *
 * E-07 lo resuelve de frente en vez de dejar un callejón con letrero: **un
 * despacho no tiene ninguna pantalla de Fiscalito**, y la que pedía por URL lo
 * manda a `/app/calendario`, que es el calendario PATRONAL de sus clientes.
 *
 * Lo que este archivo protege es que el redirect exista y que el contribuyente
 * no haya perdido nada.
 */

import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
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
        <Routes>
          <Route path="/app/store/fiscalito/use" element={<FiscalitoServicePage />} />
          <Route path="/app/calendario" element={<div>calendario patronal</div>} />
        </Routes>
      </AgentProvider>
    </MemoryRouter>,
  );
}

afterEach(() => {
  perfilMock.actual = perfilBase;
  cleanup();
});

describe('FiscalitoServicePage — cuenta de despacho', () => {
  it('un despacho no ve este servicio: va a su calendario patronal', () => {
    montar();

    expect(screen.getByText('calendario patronal')).toBeTruthy();
  });

  it('tampoco por deep-link a un tab concreto', () => {
    /**
     * Un enlace viejo —o el propio agente— puede mandar al contador a
     * `?tab=declaracion`. Antes degradaba al calendario de contribuyente; ahora
     * ese calendario no le aplica y el redirect tiene que ganarle al deep-link.
     */
    montar('/app/store/fiscalito/use?tab=declaracion');

    expect(screen.getByText('calendario patronal')).toBeTruthy();
    expect(screen.queryByText('Pre-declaración')).toBeNull();
  });

  it('no se le pinta ni un tab de contribuyente antes de redirigir', () => {
    montar();

    for (const oculto of ['Pre-declaración', 'DIOT', 'Retenciones', 'Comparar regímenes',
      'Estado de cuenta', 'Multi-periodo', 'Calendario fiscal']) {
      expect(screen.queryByText(oculto)).toBeNull();
    }
  });

  it('el contribuyente conserva sus tabs y su back-link', () => {
    perfilMock.actual = { ...perfilBase, contributorType: 'independiente', regimen: '626' };
    montar();

    expect(screen.getByText('Pre-declaración')).toBeTruthy();
    expect(screen.getByText('Calcula tus pre-declaraciones ISR/IVA')).toBeTruthy();
    expect(screen.getByRole('link', { name: /Información/ }).getAttribute('href')).toBe('/app/store/fiscalito');
  });
});
