/**
 * Planes y suscripción (P5-08): el plan es del backend. La pantalla se suscribe, cambia de
 * plan y cancela por la API, y pinta los bloqueos con el motivo que el backend escribe.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../services/firebase', () => ({
  auth: { currentUser: { uid: 'uid-1', getIdToken: async () => 'tok' } },
  db: {},
  default: {},
}));
const setProfile = vi.fn(async () => {});
vi.mock('../context/ProfileContext', () => ({
  useProfile: () => ({ profile: { plan: 'contador' }, loading: false, setProfile }),
}));

const { default: PlanesPage } = await import('./PlanesPage');

const PLANES = [
  { id: 'contador', nombre: 'Contador', max_usuarios: 1, max_clientes: 25, modulos: [],
    precio_mensual: null, moneda: 'MXN', bloquearia: [] },
  { id: 'despacho', nombre: 'Despacho', max_usuarios: 10, max_clientes: 200,
    modulos: [{ id: 'dispersion', nombre: 'Dispersión bancaria de la nómina' }],
    precio_mensual: '1500.00', moneda: 'MXN', bloquearia: [] },
];

function resumen(extra: Record<string, unknown> = {}, susc: Record<string, unknown> = {}) {
  return {
    exito: true, puede_gestionar: true, proveedor: 'falso',
    suscripcion: {
      plan: 'contador', plan_nombre: 'Contador', estado: 'prueba', vigente: true,
      solo_lectura: false, aviso: 'Estás en periodo de prueba hasta el 2026-11-02.',
      inicio_periodo: '2026-10-19T00:00:00+00:00', fin_periodo: '2026-11-02T00:00:00+00:00',
      acceso_hasta: '2026-11-02T00:00:00+00:00', plan_pendiente: null, con_cobro: false, ...susc,
    },
    uso: { clientes: 25, usuarios: 1, invitaciones_pendientes: 0 },
    bloqueos: [
      { tipo: 'clientes', motivo: 'El plan Contador llega hasta 25 clientes. No puedes dar de alta más.' },
      { tipo: 'modulo:dispersion', motivo: 'El plan Contador no incluye Dispersión bancaria de la nómina.' },
    ],
    planes: PLANES, pagos: [], ...extra,
  };
}

let llamadas: { url: string; metodo: string; cuerpo: unknown }[] = [];
let actual: unknown;
let respuestas: Record<string, unknown> = {};

beforeEach(() => {
  llamadas = [];
  actual = resumen();
  respuestas = {};
  setProfile.mockClear();
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    const metodo = init?.method ?? 'GET';
    llamadas.push({ url, metodo, cuerpo: init?.body ? JSON.parse(String(init.body)) : null });
    const clave = `${metodo} ${url.split('/api/v1')[1]}`;
    if (clave in respuestas) return new Response(JSON.stringify(respuestas[clave]));
    return new Response(JSON.stringify(metodo === 'GET' ? actual : { exito: true }));
  }));
});
afterEach(cleanup);

const montar = () => render(<MemoryRouter><PlanesPage /></MemoryRouter>);
const escrituras = () => llamadas.filter((l) => l.metodo !== 'GET');

describe('PlanesPage (P5-08)', () => {
  it('pinta estado, precio configurable y los bloqueos con su motivo', async () => {
    montar();
    expect(await screen.findByTestId('estado-suscripcion')).toHaveProperty('textContent', 'En prueba');
    expect(screen.getByText('Precio por definir')).toBeTruthy();
    expect(screen.getByText('$1,500.00 MXN / mes')).toBeTruthy();
    const lista = screen.getByRole('list', { name: 'Bloqueos del plan' });
    expect(within(lista).getByText(/llega hasta 25 clientes/)).toBeTruthy();
    expect(within(lista).getByText(/no incluye Dispersión bancaria/)).toBeTruthy();
  });

  it('se suscribe por la API y recarga el estado', async () => {
    montar();
    const tarjeta = await screen.findByLabelText('Plan Despacho');
    respuestas['POST /suscripcion'] = { exito: true, estado: 'activa', plan: 'despacho',
      plan_pendiente: null, url_pago: null };
    fireEvent.click(within(tarjeta).getByRole('button', { name: 'Suscribirme' }));
    await waitFor(() => expect(escrituras()).toHaveLength(1));
    expect(escrituras()[0]).toMatchObject({ metodo: 'POST', cuerpo: { plan: 'despacho' } });
    expect(await screen.findByText(/Te suscribiste al plan Despacho/)).toBeTruthy();
  });

  it('con cobro activo ofrece cambiar de plan, avisa lo que bloquearía y cancela', async () => {
    actual = resumen({
      planes: [{ ...PLANES[0], bloquearia: [{ tipo: 'clientes', motivo: 'El plan Contador llega hasta 25 clientes. Llevas 30: los conservas todos.' }] }, PLANES[1]],
      bloqueos: [],
    }, { plan: 'despacho', plan_nombre: 'Despacho', estado: 'activa', con_cobro: true, aviso: '' });
    montar();
    const chica = await screen.findByLabelText('Plan Contador');
    expect(within(chica).getByText(/Llevas 30: los conservas todos/)).toBeTruthy();
    expect(within(screen.getByLabelText('Plan Despacho')).queryByRole('button', { name: /Cambiar/ })).toBeNull();
    fireEvent.click(within(chica).getByRole('button', { name: 'Cambiar a este plan' }));
    await waitFor(() => expect(escrituras()).toHaveLength(1));
    expect(escrituras()[0]).toMatchObject({ metodo: 'PUT', cuerpo: { plan: 'contador' } });
    expect(escrituras()[0].url).toMatch(/\/suscripcion\/plan$/);

    respuestas['POST /suscripcion/cancelar'] = { exito: true, estado: 'cancelada',
      acceso_hasta: '2026-11-19T00:00:00+00:00' };
    fireEvent.click(await screen.findByRole('button', { name: 'Cancelar suscripción' }));
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Sí, cancelar' }));
    await waitFor(() => expect(escrituras()).toHaveLength(2));
    expect(escrituras()[1].url).toMatch(/\/suscripcion\/cancelar$/);
    expect(await screen.findByText(/Conservas el acceso hasta el/)).toBeTruthy();
  });

  it('en solo lectura lo dice arriba y permite volver a suscribirse', async () => {
    actual = resumen({ bloqueos: [{ tipo: 'solo_lectura', motivo: 'x' }] }, {
      estado: 'vencida', vigente: false, solo_lectura: true,
      aviso: 'Tu periodo de prueba terminó. La cuenta está en modo solo lectura.' });
    montar();
    expect((await screen.findByRole('alert')).textContent).toMatch(/modo solo lectura/);
    expect(screen.queryByRole('button', { name: 'Cancelar suscripción' })).toBeNull();
    expect(within(screen.getByLabelText('Plan Contador')).getByRole('button', { name: 'Suscribirme' })).toBeTruthy();
  });

  it('un usuario que no es dueño sólo ve, y el plan del backend se espeja al perfil', async () => {
    actual = resumen({ puede_gestionar: false }, { plan: 'despacho', plan_nombre: 'Despacho' });
    montar();
    expect(await screen.findByText(/Sólo el dueño del despacho/)).toBeTruthy();
    expect(screen.queryByRole('button', { name: /Suscribirme|Cambiar a este plan/ })).toBeNull();
    await waitFor(() => expect(setProfile).toHaveBeenCalledWith({ plan: 'despacho' }));
  });

  it('muestra el error del backend', async () => {
    montar();
    const tarjeta = await screen.findByLabelText('Plan Despacho');
    vi.stubGlobal('fetch', vi.fn(async () => new Response(
      JSON.stringify({ exito: false, error: 'Falta configurar el precio del plan Despacho.' }),
      { status: 503 })));
    fireEvent.click(within(tarjeta).getByRole('button', { name: 'Suscribirme' }));
    expect((await screen.findByRole('alert')).textContent).toMatch(/Falta configurar el precio/);
  });
});
