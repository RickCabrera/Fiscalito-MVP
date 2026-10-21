/** Aceptar invitación (P5-01): sin sesión pide iniciarla; con sesión manda el token. */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../services/firebase', () => ({
  auth: { currentUser: { uid: 'uid-1', getIdToken: async () => 'tok' } },
  db: {},
  default: {},
}));
const authMock = { actual: { user: null as null | { email: string }, loading: false } };
vi.mock('../context/AuthContext', () => ({ useAuth: () => authMock.actual }));

const { default: AceptarInvitacionPage } = await import('./AceptarInvitacionPage');

let cuerpos: unknown[] = [];

beforeEach(() => {
  cuerpos = [];
  authMock.actual = { user: null, loading: false };
  vi.stubGlobal('fetch', vi.fn(async (_url: string, init?: RequestInit) => {
    cuerpos.push(JSON.parse(String(init?.body)));
    return new Response(JSON.stringify({ exito: true, despacho_id: 'd', rol: 'auxiliar' }));
  }));
});
afterEach(cleanup);

const montar = (q = '?token=tok-123') =>
  render(<MemoryRouter initialEntries={[`/aceptar-invitacion${q}`]}><AceptarInvitacionPage /></MemoryRouter>);

describe('AceptarInvitacionPage', () => {
  it('sin sesión manda a iniciarla y a volver aquí', () => {
    montar();
    const enlace = screen.getByRole('button', { name: 'Iniciar sesión' }).closest('a')!;
    expect(decodeURIComponent(enlace.getAttribute('href')!))
      .toBe('/login?volver=/aceptar-invitacion?token=tok-123');
  });

  it('con sesión acepta con el token', async () => {
    authMock.actual = { user: { email: 'beto@d.mx' }, loading: false };
    montar();
    fireEvent.click(screen.getByRole('button', { name: 'Aceptar invitación' }));
    expect(await screen.findByText(/como Auxiliar/)).toBeTruthy();
    expect(cuerpos[0]).toEqual({ token: 'tok-123', nombre: '' });
  });

  it('sin token lo dice', () => {
    montar('');
    expect(screen.getByText(/no trae invitación/)).toBeTruthy();
  });
});
