/** Alertas fiscales (P3-09): campana con contador, lista con "Resuelta" y página con filtros. */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ClienteActivoContext, type ClienteActivoContextType } from '../../context/clienteActivoStore';
import CampanaAlertas from './CampanaAlertas';
import AlertasCliente from './AlertasCliente';

const { default: AlertasPage } = await import('../../pages/AlertasPage');

const ALERTA = {
  id: 3, cliente: 'taller', cliente_nombre: 'Taller', tipo: 'credencial', severidad: 'alta',
  titulo: 'La e.firma vence en 5 días', detalle: 'Certificado 0001.', fecha: '2026-10-24',
  enlace: '/app/clientes/taller', resuelta: false, resuelta_por: '', resuelta_en: null,
};

let urls: { url: string; method: string }[] = [];

beforeEach(() => {
  urls = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string, init: RequestInit = {}) => {
    urls.push({ url, method: init.method ?? 'GET' });
    if (url.endsWith('/alertas/conteo')) {
      return Response.json({ total: 4, alta: 1, por_cliente: { taller: { total: 4, alta: 1, media: 3, baja: 0 } } });
    }
    if (url.includes('/resolver')) return Response.json({ alerta: { ...ALERTA, resuelta: true } });
    if (url.includes('/alertas/evaluar')) return Response.json({ exito: true });
    return Response.json({ alertas: [ALERTA] });
  }));
});

afterEach(() => cleanup());

const ACTIVO = {
  clientes: [{ id: 'taller', nombre: 'Taller' }], clienteId: 'taller', cliente: null,
  loading: false, error: null, setClienteId: () => {}, recargar: () => {},
} as unknown as ClienteActivoContextType;

describe('Alertas fiscales', () => {
  it('la campana pinta el número de alertas abiertas y lleva a la página', async () => {
    render(<MemoryRouter><CampanaAlertas /></MemoryRouter>);
    expect((await screen.findByTestId('contador-alertas')).textContent).toBe('4');
    expect(screen.getByRole('link', { name: /Alertas fiscales: 4 abiertas/ }).getAttribute('href'))
      .toBe('/app/alertas');
  });

  it('sin backend la campana queda sin número, sin romper', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => { throw new Error('caído'); }));
    render(<MemoryRouter><CampanaAlertas /></MemoryRouter>);
    await waitFor(() => expect(screen.getByRole('link', { name: 'Alertas fiscales' })).toBeTruthy());
    expect(screen.queryByTestId('contador-alertas')).toBeNull();
  });

  it('la ficha del cliente lista sus alertas y las marca resueltas', async () => {
    render(<MemoryRouter><AlertasCliente clave="taller" /></MemoryRouter>);
    expect(await screen.findByText('La e.firma vence en 5 días')).toBeTruthy();
    expect(urls[0].url).toContain('/alertas?cliente=taller');
    fireEvent.click(screen.getByRole('button', { name: /Resuelta/ }));
    await waitFor(() => expect(screen.queryByText('La e.firma vence en 5 días')).toBeNull());
    expect(urls.some((u) => u.url.endsWith('/alertas/3/resolver') && u.method === 'POST')).toBe(true);
    expect(screen.getByText('Sin alertas abiertas.')).toBeTruthy();
  });

  it('la página filtra por severidad y "Revisar ahora" corre las reglas', async () => {
    render(
      <MemoryRouter>
        <ClienteActivoContext.Provider value={ACTIVO}><AlertasPage /></ClienteActivoContext.Provider>
      </MemoryRouter>,
    );
    expect(await screen.findByText('La e.firma vence en 5 días')).toBeTruthy();
    fireEvent.change(screen.getByLabelText('Severidad'), { target: { value: 'alta' } });
    await waitFor(() => expect(urls.some((u) => u.url.includes('severidad=alta'))).toBe(true));
    fireEvent.click(screen.getByRole('button', { name: /Revisar ahora/ }));
    await waitFor(() => expect(urls.some((u) => u.url.includes('/alertas/evaluar') && u.method === 'POST')).toBe(true));
  });
});
