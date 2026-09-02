/**
 * Alta de una cuenta de despacho (E-01).
 *
 * Datos sintéticos a propósito: `XAXX010101000` es el RFC genérico del SAT y
 * "Despacho Demo" no es de nadie. Ningún dato real entra a una fixture.
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

// Tipada para que `mock.calls[0][0]` sea el perfil que se guarda, no `never`.
const setProfile = vi.fn<(data: Partial<UserProfile>) => Promise<void>>(async () => {});
const navigate = vi.fn();

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({ user: { uid: 'uid-demo', email: 'demo@ejemplo.mx' }, loading: false }),
}));

vi.mock('../context/ProfileContext', () => ({
  useProfile: () => ({
    profile: perfilVacio,
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

/** Paso 0 → paso 1 eligiendo "Despacho / Contador". */
function elegirContador() {
  fireEvent.click(screen.getByText('Despacho / Contador'));
  fireEvent.click(botonSiguiente());
}

afterEach(() => {
  setProfile.mockClear();
  navigate.mockClear();
  cleanup();
});

describe('OnboardingWizard — perfil de despacho', () => {
  it('ofrece el tipo Despacho / Contador', () => {
    montar();
    expect(screen.getByText('Despacho / Contador')).toBeTruthy();
  });

  it('pide el nombre del despacho, no el del negocio', () => {
    montar();
    elegirContador();

    expect(screen.getByText('Nombre del despacho')).toBeTruthy();
    expect(screen.queryByText('Nombre del negocio')).toBeNull();
    expect(screen.queryByText('Numero de empleados')).toBeNull();
  });

  it('solo ofrece los regímenes que el despacho puede tener', () => {
    montar();
    elegirContador();

    const opciones = Array.from(screen.getAllByRole('option')).map((o) => (o as HTMLOptionElement).value);
    expect(opciones).toEqual(['', '612', '626']);
  });

  /**
   * LA TRANSICIÓN, no el estado. Asertar solo "deshabilitado con el despacho
   * vacío" pasaría por razones equivocadas (RFC corto, régimen sin elegir): el
   * test exige que el ÚNICO campo que falta sea el del despacho, y que llenarlo
   * habilite el botón.
   */
  it('el nombre del despacho es lo único que falta para avanzar', () => {
    montar();
    elegirContador();

    fireEvent.change(screen.getByPlaceholderText('XAXX010101000'), { target: { value: 'XAXX010101000' } });
    fireEvent.change(screen.getByRole('combobox'), { target: { value: '612' } });

    expect(botonSiguiente().disabled).toBe(true);

    fireEvent.change(screen.getByPlaceholderText('Despacho Contable Ejemplo'), {
      target: { value: 'Despacho Demo' },
    });

    expect(botonSiguiente().disabled).toBe(false);
  });

  it('guarda el nombre del despacho y entra a la pantalla de clientes', async () => {
    montar();
    elegirContador();

    fireEvent.change(screen.getByPlaceholderText('XAXX010101000'), { target: { value: 'XAXX010101000' } });
    fireEvent.change(screen.getByRole('combobox'), { target: { value: '612' } });
    fireEvent.change(screen.getByPlaceholderText('Despacho Contable Ejemplo'), {
      target: { value: 'Despacho Demo' },
    });
    fireEvent.click(botonSiguiente());

    fireEvent.change(screen.getByPlaceholderText('Tu nombre completo'), { target: { value: 'Contadora Demo' } });
    fireEvent.click(botonSiguiente());

    // Paso 4: el resumen enseña el despacho antes de guardar.
    expect(screen.getByText('Despacho')).toBeTruthy();
    expect(screen.getByText('Despacho Demo')).toBeTruthy();

    fireEvent.click(screen.getByRole('button', { name: /Comenzar/ }));

    await vi.waitFor(() => expect(setProfile).toHaveBeenCalledTimes(1));
    expect(setProfile.mock.calls[0][0]).toMatchObject({
      contributorType: 'contador',
      nombreDespacho: 'Despacho Demo',
      rfc: 'XAXX010101000',
      regimen: '612',
      onboardingComplete: true,
    });
    await vi.waitFor(() => expect(navigate).toHaveBeenCalledWith('/app/clientes'));
  });

  it('un contribuyente no ve el campo del despacho y sigue entrando al dashboard', async () => {
    montar();
    fireEvent.click(screen.getByText('Independiente / Freelancer'));
    fireEvent.click(botonSiguiente());

    expect(screen.queryByPlaceholderText('Despacho Contable Ejemplo')).toBeNull();

    fireEvent.change(screen.getByPlaceholderText('XAXX010101000'), { target: { value: 'XAXX010101000' } });
    fireEvent.change(screen.getByRole('combobox'), { target: { value: '626' } });
    expect(botonSiguiente().disabled).toBe(false);

    fireEvent.click(botonSiguiente());
    fireEvent.change(screen.getByPlaceholderText('Tu nombre completo'), { target: { value: 'Persona Demo' } });
    fireEvent.click(botonSiguiente());
    fireEvent.click(screen.getByRole('button', { name: /Comenzar/ }));

    await vi.waitFor(() => expect(navigate).toHaveBeenCalledWith('/app'));
  });
});
