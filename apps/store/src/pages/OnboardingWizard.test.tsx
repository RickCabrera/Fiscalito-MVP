/**
 * Alta de una cuenta de despacho.
 *
 * K (2026-10-19): el sistema es solo para despachos. El wizard no ofrece tipo de
 * cuenta: toda cuenta queda como `contador`, y una cuenta vieja de contribuyente
 * que cae aquí sale convertida.
 *
 * Datos sintéticos a propósito: "Despacho Demo" no es de nadie.
 */

import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { UserProfile } from '../context/ProfileContext';

const perfilVacio: UserProfile = {
  contributorType: null,
  rfc: '',
  regimen: '',
  nombre: '',
  actividad: '',
  cp: '',
  telefono: '',
  nombreNegocio: '',
  numEmpleados: '',
  nombreDespacho: '',
  onboardingComplete: false,
};

const perfilMock: { actual: UserProfile } = { actual: perfilVacio };

// Tipada para que `mock.calls[0][0]` sea el perfil que se guarda, no `never`.
const setProfile = vi.fn<(data: Partial<UserProfile>) => Promise<void>>(async () => {});
const navigate = vi.fn();

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({ user: { uid: 'uid-demo', email: 'demo@ejemplo.mx' }, loading: false }),
}));

vi.mock('../context/ProfileContext', () => ({
  useProfile: () => ({
    profile: perfilMock.actual,
    loading: false,
    setProfile,
    isOnboardingComplete: () => false,
  }),
}));

vi.mock('react-router-dom', async () => {
  const real = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return { ...real, useNavigate: () => navigate };
});

const { default: OnboardingWizard } = await import('./OnboardingWizard');

function montar() {
  return render(<MemoryRouter><OnboardingWizard /></MemoryRouter>);
}

function botonSiguiente() {
  return screen.getByRole('button', { name: /Siguiente/ }) as HTMLButtonElement;
}

function llenarDespacho() {
  fireEvent.change(screen.getByPlaceholderText('Tu nombre completo'), { target: { value: 'Ana Pérez' } });
  fireEvent.change(screen.getByPlaceholderText('Despacho Contable Ejemplo'), { target: { value: 'Despacho Demo' } });
}

afterEach(() => {
  perfilMock.actual = perfilVacio;
  setProfile.mockClear();
  navigate.mockClear();
  cleanup();
});

describe('OnboardingWizard (solo despacho)', () => {
  it('abre directo en los datos del despacho, sin ofrecer tipos de contribuyente', () => {
    montar();

    expect(screen.getByRole('heading', { name: 'Datos del despacho' })).toBeTruthy();
    for (const tipo of ['Asalariado', 'Independiente / Freelancer', 'Arrendamiento', 'Plataformas digitales', 'Negocio / PYME']) {
      expect(screen.queryByText(tipo)).toBeNull();
    }
    // Ni RFC, ni régimen, ni código postal: son de cada cliente.
    expect(screen.queryByPlaceholderText('XAXX010101000')).toBeNull();
    expect(screen.queryByText(/Regimen fiscal/i)).toBeNull();
  });

  it('no avanza sin nombre del contador y nombre del despacho', () => {
    montar();
    expect(botonSiguiente().disabled).toBe(true);

    fireEvent.change(screen.getByPlaceholderText('Tu nombre completo'), { target: { value: 'Ana Pérez' } });
    expect(botonSiguiente().disabled).toBe(true);

    fireEvent.change(screen.getByPlaceholderText('Despacho Contable Ejemplo'), { target: { value: 'Despacho Demo' } });
    expect(botonSiguiente().disabled).toBe(false);
  });

  it('al terminar guarda la cuenta como contador y entra al dashboard (P5-02)', async () => {
    montar();
    llenarDespacho();
    fireEvent.click(botonSiguiente());

    expect(screen.getByText('Despacho Demo')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: /Comenzar a usar/ }));
    await vi.waitFor(() => expect(navigate).toHaveBeenCalledWith('/app/inicio'));

    const guardado = setProfile.mock.calls[0][0];
    expect(guardado).toMatchObject({
      contributorType: 'contador',
      nombre: 'Ana Pérez',
      nombreDespacho: 'Despacho Demo',
      onboardingComplete: true,
    });
  });

  it('una cuenta vieja de contribuyente ve el aviso y sale convertida, sin su RFC propio', async () => {
    perfilMock.actual = {
      ...perfilVacio,
      contributorType: 'pyme', rfc: 'XAXX010101000', regimen: '612',
      nombre: 'Ana Pérez', onboardingComplete: true,
    };
    montar();

    expect(screen.getByText(/ahora es solo para despachos y contadores/i)).toBeTruthy();
    // Lo que ya se sabía se precarga.
    expect((screen.getByPlaceholderText('Tu nombre completo') as HTMLInputElement).value).toBe('Ana Pérez');

    fireEvent.change(screen.getByPlaceholderText('Despacho Contable Ejemplo'), { target: { value: 'Despacho Demo' } });
    fireEvent.click(botonSiguiente());
    fireEvent.click(screen.getByRole('button', { name: /Comenzar a usar/ }));
    await vi.waitFor(() => expect(setProfile).toHaveBeenCalled());

    expect(setProfile.mock.calls[0][0]).toMatchObject({
      contributorType: 'contador', rfc: '', regimen: '',
    });
  });

  it('una cuenta nueva no ve el aviso de conversión', () => {
    montar();
    expect(screen.queryByText(/ahora es solo para despachos/i)).toBeNull();
  });
});
