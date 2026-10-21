/** Dashboard del despacho (P5-02): tarjetas con datos de varias fuentes y enlaces al detalle. */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../services/firebase', () => ({
  auth: { currentUser: { uid: 'uid-1', getIdToken: async () => 'tok' } },
  db: {},
  default: {},
}));

const { default: InicioPage } = await import('./InicioPage');

const BASE = {
  exito: true, hoy: '2026-10-19', rol: 'dueno', clientes: 2,
  vencimientos: { semana: 1, vencidas: 1, enlace: '/app/calendario', renglones: [
    { clave: 'mensual:2026-09', cliente: 'c0', cliente_nombre: 'Taller', nombre: 'Pago mensual',
      periodo: '2026-09', fecha_limite: '2026-10-19', estado: 'pendiente',
      enlace: '/app/calendario?cliente=c0' },
  ] },
  credenciales: { total: 1, vencidas: 0, enlace: '/app/calendario?tipo=credencial', renglones: [
    { cliente: 'c0', cliente_nombre: 'Taller', nombre: 'e.firma', tipo: 'efirma',
      vence: '2026-11-01', dias: 13, vencida: false, enlace: '/app/clientes/c0' },
  ] },
  alertas: { total: 3, alta: 2, media: 1, baja: 0, enlace: '/app/alertas',
    enlaces: { alta: '/app/alertas?severidad=alta', media: '/app/alertas?severidad=media',
      baja: '/app/alertas?severidad=baja' } },
  descarga_sat: { enlace: '/app/sat', resumen: { con_error: 1 }, renglones: [
    { cliente: 'c0', cliente_nombre: 'Taller', estado: 'con_error', ultima_descarga: null,
      alertas: 1, enlace: '/app/clientes/c0' },
  ] },
  opinion: { verde: 0, amarillo: 0, rojo: 1, gris: 1, enlace: '/app/clientes', renglones: [
    { cliente: 'c0', cliente_nombre: 'Taller', semaforo: 'rojo', fecha: '2026-10-16',
      resultado: 'negativa', enlace: '/app/clientes/c0' },
  ] },
  nominas: { por_cerrar: 1, por_timbrar: 0, renglones: [
    { id: 7, cliente: 'c0', cliente_nombre: 'Taller', inicio: '2026-10-01', fin: '2026-10-15',
      fecha_pago: '2026-10-15', estado: 'calculada', accion: 'cerrar',
      enlace: '/app/clientes/c0/nomina' },
  ] },
  agenda: { total: 0, atrasadas: 0, enlace: '/app/calendario?vista=agenda', renglones: [] },
  cobranza: { vencido: '5000.00', clientes: 1, enlace: '/app/cobranza', renglones: [
    { cliente: 'c0', cliente_nombre: 'Taller', vencido: '5000.00', vencido_desde: '2026-09-15',
      enlace: '/app/cobranza?cliente=c0' },
  ] },
};

let respuesta: unknown = BASE;
let urls: string[] = [];

beforeEach(() => {
  respuesta = BASE;
  urls = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    urls.push(url);
    return new Response(JSON.stringify(respuesta));
  }));
});
afterEach(cleanup);

const montar = () => render(<MemoryRouter><InicioPage /></MemoryRouter>);

function enlaceDe(nombre: string): string | null {
  return screen.getByRole('region', { name: nombre }).querySelector('a')!.getAttribute('href');
}

describe('InicioPage', () => {
  it('pinta las tarjetas con una sola llamada a /dashboard', async () => {
    montar();
    expect(await screen.findByRole('region', { name: 'Vencimientos de la semana' })).toBeTruthy();
    expect(urls).toHaveLength(1);
    expect(urls[0]).toContain('/api/v1/dashboard');
    expect(screen.getByText('Taller · Pago mensual')).toBeTruthy();
    expect(screen.getByText('Por cerrar')).toBeTruthy();
    expect(screen.getByText('Con error')).toBeTruthy();
    expect(screen.getByText(/13 días/)).toBeTruthy();
  });

  it('cada tarjeta lleva a su detalle', async () => {
    montar();
    await screen.findByRole('region', { name: 'Alertas abiertas' });
    expect(enlaceDe('Vencimientos de la semana')).toBe('/app/calendario');
    expect(enlaceDe('Alertas abiertas')).toBe('/app/alertas');
    expect(enlaceDe('Descarga SAT')).toBe('/app/sat');
    expect(enlaceDe('e.firma y CSD por vencer')).toBe('/app/calendario?tipo=credencial');
    expect(enlaceDe('Nóminas pendientes')).toBe('/app/clientes/c0/nomina');
    expect(enlaceDe('Mis pendientes')).toBe('/app/calendario?vista=agenda');
    expect(enlaceDe('Cuentas por cobrar vencidas')).toBe('/app/cobranza');
    // Y los renglones, al detalle del cliente.
    const alta = screen.getByText('Severidad alta').closest('a');
    expect(alta?.getAttribute('href')).toBe('/app/alertas?severidad=alta');
  });

  it('el auxiliar no ve la tarjeta de cobranza', async () => {
    respuesta = { ...BASE, rol: 'auxiliar', cobranza: null };
    montar();
    await screen.findByRole('region', { name: 'Alertas abiertas' });
    expect(screen.queryByRole('region', { name: 'Cuentas por cobrar vencidas' })).toBeNull();
  });

  it('un error se ve', async () => {
    vi.stubGlobal('fetch', vi.fn(async () =>
      new Response(JSON.stringify({ exito: false, error: 'Falló el servidor.' }), { status: 500 })));
    montar();
    expect(await screen.findByText(/Falló el servidor/)).toBeTruthy();
  });
});
