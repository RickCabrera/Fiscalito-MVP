/** Equipo del despacho (P5-01): invitar, roles, asignar clientes y vista de sólo lectura. */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../services/firebase', () => ({
  auth: { currentUser: { uid: 'uid-1', getIdToken: async () => 'tok' } },
  db: {},
  default: {},
}));
vi.mock('../context/clienteActivoStore', () => ({
  useClienteActivo: () => ({ clientes: [{ id: 'taller', nombre: 'Taller' }, { id: 'tienda', nombre: 'Tienda' }] }),
}));

const { default: EquipoPage } = await import('./EquipoPage');

const EQUIPO = {
  exito: true, yo: { uid: 'uid-1', rol: 'dueno', despacho_id: 'uid-1' }, puede_gestionar: true,
  plan: { id: 'despacho', nombre: 'Despacho', max_usuarios: 10, max_clientes: 200,
    usuarios_activos: 2, invitaciones_pendientes: 1, clientes: 2 },
  usuarios: [
    { uid: 'uid-1', nombre: 'Ana', email: 'ana@d.mx', rol: 'dueno', activo: true, clientes: [] },
    { uid: 'uid-2', nombre: 'Beto', email: 'beto@d.mx', rol: 'auxiliar', activo: true, clientes: ['taller'] },
  ],
  invitaciones: [{ id: 5, correo: 'caro@d.mx', rol: 'contador', expira_en: '2026-10-26T00:00:00Z', creado_por: 'uid-1' }],
};

let llamadas: { url: string; metodo: string; cuerpo: unknown }[] = [];
let equipo: unknown = EQUIPO;

beforeEach(() => {
  llamadas = [];
  equipo = EQUIPO;
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    llamadas.push({ url, metodo: init?.method ?? 'GET', cuerpo: init?.body ? JSON.parse(String(init.body)) : null });
    return new Response(JSON.stringify(url.endsWith('/equipo') ? equipo : { exito: true }));
  }));
});
afterEach(cleanup);

const montar = () => render(<MemoryRouter><EquipoPage /></MemoryRouter>);
const escrituras = () => llamadas.filter((l) => l.metodo !== 'GET');

describe('EquipoPage', () => {
  it('lista usuarios, plan e invitaciones pendientes', async () => {
    montar();
    expect(await screen.findByText('Ana (tú)')).toBeTruthy();
    expect(screen.getByText(/2 de 10 usuarios/)).toBeTruthy();
    expect(screen.getByText(/caro@d.mx/)).toBeTruthy();
    expect(screen.getByText(/: taller/)).toBeTruthy();
  });

  it('invita con correo y rol', async () => {
    montar();
    await screen.findByText('Ana (tú)');
    fireEvent.change(screen.getByLabelText('Correo'), { target: { value: 'nuevo@d.mx' } });
    fireEvent.change(screen.getByLabelText('Rol de la invitación'), { target: { value: 'contador' } });
    fireEvent.click(screen.getByRole('button', { name: /Invitar/ }));
    await waitFor(() => expect(escrituras()).toHaveLength(1));
    expect(escrituras()[0]).toMatchObject({ metodo: 'POST', cuerpo: { correo: 'nuevo@d.mx', rol: 'contador' } });
    expect(escrituras()[0].url).toContain('/api/v1/equipo/invitaciones');
  });

  it('cambia el rol y asigna clientes al auxiliar', async () => {
    montar();
    await screen.findByText('Ana (tú)');
    fireEvent.change(screen.getByLabelText('Rol de Beto'), { target: { value: 'contador' } });
    await waitFor(() => expect(escrituras()).toHaveLength(1));
    expect(escrituras()[0]).toMatchObject({ metodo: 'PUT', cuerpo: { rol: 'contador' } });
    fireEvent.click(screen.getByRole('button', { name: 'Asignar clientes' }));
    fireEvent.click(screen.getByLabelText('Tienda'));
    await waitFor(() => expect(escrituras()).toHaveLength(2));
    expect(escrituras()[1].metodo).toBe('POST');
    expect(escrituras()[1].url).toContain('/equipo/usuarios/uid-2/clientes/tienda');
  });

  it('quien no es dueño ve el equipo sin controles', async () => {
    equipo = { ...EQUIPO, puede_gestionar: false, yo: { uid: 'uid-2', rol: 'auxiliar', despacho_id: 'uid-1' }, invitaciones: [] };
    montar();
    expect(await screen.findByText('Beto (tú)')).toBeTruthy();
    expect(screen.queryByRole('button', { name: /Invitar/ })).toBeNull();
    expect(screen.queryByLabelText('Rol de Ana')).toBeNull();
    expect(screen.queryByRole('button', { name: 'Desactivar' })).toBeNull();
  });

  it('al tope del plan no deja invitar y dice por qué', async () => {
    equipo = { ...EQUIPO, plan: { ...EQUIPO.plan, nombre: 'Contador', max_usuarios: 1, usuarios_activos: 1, invitaciones_pendientes: 0 } };
    montar();
    await screen.findByText('Ana (tú)');
    expect((screen.getByRole('button', { name: /Invitar/ }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByText(/llega hasta 1 usuario\b/)).toBeTruthy();
  });
});
