/**
 * Perfil del despacho (E-01).
 *
 * POR QUÉ EXISTE: quitar `nombreDespacho` del `handleSave` no rompe nada de
 * forma visible — `setProfile` hace `{...profile, ...data}`, así que el valor
 * viejo sobrevive, el formulario sigue mostrando lo que el usuario tecleó y la
 * pantalla dice "Guardado correctamente". Es una pérdida silenciosa con mensaje
 * de éxito, en la pantalla donde un contador corrige el nombre de su despacho.
 */

import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import type { UserProfile } from '../context/ProfileContext';

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

const perfilMock = { actual: perfilContador };
const setProfile = vi.fn<(data: Partial<UserProfile>) => Promise<void>>(async () => {});

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({ user: { uid: 'uid-demo', email: 'demo@ejemplo.mx' }, loading: false }),
}));

vi.mock('../context/ProfileContext', () => ({
  useProfile: () => ({ profile: perfilMock.actual, loading: false, setProfile }),
}));

const { default: ProfilePage } = await import('./ProfilePage');

afterEach(() => {
  perfilMock.actual = perfilContador;
  setProfile.mockClear();
  cleanup();
});

describe('ProfilePage — perfil de despacho', () => {
  it('muestra el nombre del despacho y no los campos de PYME', () => {
    render(<ProfilePage />);

    const input = screen.getByPlaceholderText('Despacho Contable Ejemplo') as HTMLInputElement;
    expect(input.value).toBe('Despacho Demo');
    expect(screen.queryByPlaceholderText('Mi Empresa S.A. de C.V.')).toBeNull();
  });

  it('guarda el nombre del despacho editado', async () => {
    render(<ProfilePage />);

    fireEvent.change(screen.getByPlaceholderText('Despacho Contable Ejemplo'), {
      target: { value: 'Despacho Demo y Asociados' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Guardar cambios/ }));

    await vi.waitFor(() => expect(setProfile).toHaveBeenCalledTimes(1));
    expect(setProfile.mock.calls[0][0]).toMatchObject({
      contributorType: 'contador',
      nombreDespacho: 'Despacho Demo y Asociados',
    });
  });

  it('un contribuyente no ve el campo del despacho', () => {
    perfilMock.actual = { ...perfilContador, contributorType: 'independiente', regimen: '626' };
    render(<ProfilePage />);

    expect(screen.queryByPlaceholderText('Despacho Contable Ejemplo')).toBeNull();
  });

  it('el contribuyente sigue guardando sus campos de siempre', async () => {
    perfilMock.actual = { ...perfilContador, contributorType: 'pyme', nombreNegocio: 'Negocio Demo' };
    render(<ProfilePage />);

    fireEvent.click(screen.getByRole('button', { name: /Guardar cambios/ }));

    await vi.waitFor(() => expect(setProfile).toHaveBeenCalledTimes(1));
    expect(setProfile.mock.calls[0][0]).toMatchObject({
      contributorType: 'pyme',
      nombreNegocio: 'Negocio Demo',
      rfc: 'XAXX010101000',
    });
  });
});
