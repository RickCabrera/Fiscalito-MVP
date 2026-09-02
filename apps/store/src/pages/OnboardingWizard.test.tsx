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

  /**
   * E-05: SOLO tres campos. Un despacho no declara por sí mismo en esta app,
   * así que pedirle RFC, régimen, actividad o CP era pedirle datos que nada usa
   * — y hacerle creer que la app le calcularía su propia declaración.
   */
  it('no le pide RFC, régimen, actividad ni código postal', () => {
    montar();
    elegirContador();

    expect(screen.queryByPlaceholderText('XAXX010101000')).toBeNull();
    expect(screen.queryByRole('combobox')).toBeNull();
    expect(screen.queryByText('Actividad economica')).toBeNull();
    expect(screen.queryByText(/Codigo postal/)).toBeNull();

    expect(screen.getByText('Nombre del despacho')).toBeTruthy();
    expect(screen.getByPlaceholderText('Tu nombre completo')).toBeTruthy();
    expect(screen.getByPlaceholderText('10 digitos')).toBeTruthy();
  });

  it('su wizard tiene TRES pasos, no cuatro', () => {
    montar();
    elegirContador();

    // La barra de progreso no puede anunciar un paso que nadie va a recorrer.
    // "Datos del despacho" sale dos veces —barra y encabezado del paso—, así
    // que se cuenta en vez de exigir uno solo.
    expect(screen.getAllByText('Datos del despacho').length).toBeGreaterThan(0);
    expect(screen.queryByText('Datos fiscales')).toBeNull();
    expect(screen.queryByText('Datos personales')).toBeNull();
  });

  /**
   * LA TRANSICIÓN, no el estado. Asertar sólo "deshabilitado con todo vacío"
   * pasaría por la razón equivocada: el test exige que falte exactamente el
   * nombre del despacho, y que llenarlo habilite el botón.
   */
  it('el nombre del contador y el del despacho son obligatorios; el teléfono no', () => {
    montar();
    elegirContador();

    fireEvent.change(screen.getByPlaceholderText('Tu nombre completo'), {
      target: { value: 'Contadora Demo' },
    });
    expect(botonSiguiente().disabled).toBe(true);

    fireEvent.change(screen.getByPlaceholderText('Despacho Contable Ejemplo'), {
      target: { value: 'Despacho Demo' },
    });
    expect(botonSiguiente().disabled).toBe(false);
  });

  it('llega al botón de terminar y CREA la cuenta', async () => {
    /**
     * LA REGRESIÓN QUE VALE ESTE TEST. El wizard tenía `step < 3` cableado para
     * decidir si pintaba "Siguiente" o "Comenzar". Con tres pasos el último
     * índice es 2, así que el contador se quedaba en "Confirmar" viendo
     * "Siguiente" y `handleFinish` NUNCA se ejecutaba: no se creaba la cuenta y
     * nada fallaba visiblemente.
     */
    montar();
    elegirContador();

    fireEvent.change(screen.getByPlaceholderText('Tu nombre completo'), { target: { value: 'Contadora Demo' } });
    fireEvent.change(screen.getByPlaceholderText('Despacho Contable Ejemplo'), {
      target: { value: 'Despacho Demo' },
    });
    fireEvent.change(screen.getByPlaceholderText('10 digitos'), { target: { value: '5551234567' } });
    fireEvent.click(botonSiguiente());

    // Paso 3: el resumen enseña el despacho y NO inventa un RFC en blanco.
    expect(screen.getByText('Despacho')).toBeTruthy();
    expect(screen.getByText('Despacho Demo')).toBeTruthy();
    expect(screen.queryByText('RFC')).toBeNull();
    expect(screen.queryByText('Regimen')).toBeNull();

    fireEvent.click(screen.getByRole('button', { name: /Comenzar/ }));

    await vi.waitFor(() => expect(setProfile).toHaveBeenCalledTimes(1));
    expect(setProfile.mock.calls[0][0]).toMatchObject({
      contributorType: 'contador',
      nombre: 'Contadora Demo',
      nombreDespacho: 'Despacho Demo',
      telefono: '5551234567',
      // Vacíos y presentes: el perfil tiene forma fija y `setProfile` mergea.
      rfc: '',
      regimen: '',
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
