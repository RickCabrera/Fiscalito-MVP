/**
 * La pantalla de la bóveda (P0-03), medida por lo que resuelve: pide la bóveda
 * del CLIENTE ACTIVO, sube y enseña el reporte, filtra, pagina y descarga.
 * `fetch` stubbeado; la autenticación es un doble.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { ComprobanteBoveda } from '../services/bovedaApi';

vi.mock('../services/firebase', () => ({
  auth: { currentUser: { uid: 'uid-1', getIdToken: async () => 'tk' } },
  db: {},
  default: {},
}));

const activo = { clienteId: 'taller' as string | null };
vi.mock('../context/clienteActivoStore', () => ({
  useClienteActivo: () => ({
    clientes: [], clienteId: activo.clienteId,
    cliente: activo.clienteId ? { nombre: 'Taller Sintético' } : null,
    loading: false, error: null, setClienteId: () => undefined, recargar: () => undefined,
  }),
}));

const { default: BovedaPage } = await import('./BovedaPage');

function comprobante(n: number, direccion: 'emitido' | 'recibido' = 'emitido'): ComprobanteBoveda {
  return {
    uuid: `UUID-${n}`, version: '4.0', tipo: 'I', fecha: '2026-03-10T10:00:00', serie: 'A',
    folio: String(n), rfc_emisor: 'XEXX010101AB1', nombre_emisor: 'TALLER',
    rfc_receptor: 'COM010101BB2', nombre_receptor: 'COMPRADOR SINTÉTICO', direccion,
    subtotal: '1000.00', descuento: '0.00', total: '1160.00', moneda: 'MXN', metodo_pago: 'PUE',
    forma_pago: '03', uso_cfdi: 'G03', iva_trasladado: '160.00', iva_retenido: '0.00',
    isr_retenido: '0.00', ieps: '0.00', estatus_sat: 'desconocido', origen: 'manual',
  };
}

let peticiones: { url: string; method: string; body?: BodyInit | null }[] = [];
let comprobantes: ComprobanteBoveda[] = [];
let total = 0;

beforeEach(() => {
  cleanup();
  peticiones = [];
  activo.clienteId = 'taller';
  comprobantes = [comprobante(1)];
  total = 1;
  vi.stubGlobal('fetch', vi.fn(async (url: string, init: RequestInit = {}) => {
    const method = init.method ?? 'GET';
    peticiones.push({ url, method, body: init.body });
    if (method === 'POST') {
      return Response.json({
        exito: true, rfc_cliente: 'XEXX010101AB1', rfc_deducido: false, importados: 3,
        duplicados: 2, rechazados: [{ archivo: 'lote.zip/notas.txt', razon: 'No es XML.' }],
        importados_detalle: [], duplicados_detalle: [],
      });
    }
    if (url.includes('/xml')) return new Response('<a/>', { headers: { 'Content-Type': 'application/xml' } });
    const pagina = Number(new URL(url).searchParams.get('pagina') ?? '1');
    return Response.json({ exito: true, total, pagina, por_pagina: 50, comprobantes });
  }));
});

function montar() {
  return render(<MemoryRouter><BovedaPage /></MemoryRouter>);
}

const listados = () => peticiones.filter((p) => p.method === 'GET' && p.url.includes('/cfdi?'));
const ultimo = () => {
  const l = listados();
  return l[l.length - 1];
};

describe('BovedaPage', () => {
  it('sin cliente activo pide elegir uno y no llama al backend', () => {
    activo.clienteId = null;
    montar();
    expect(screen.getByText('Elige un cliente primero')).toBeTruthy();
    expect(peticiones).toHaveLength(0);
  });

  it('pide la bóveda del cliente activo y pinta la contraparte', async () => {
    montar();
    expect(await screen.findByText('COMPRADOR SINTÉTICO')).toBeTruthy();
    expect(new URL(listados()[0].url).pathname).toBe('/api/v1/boveda/clientes/taller/cfdi');
    expect(screen.getByText(/1 comprobante · página 1 de 1/)).toBeTruthy();
  });

  it('sube los archivos, enseña el reporte y recarga la tabla', async () => {
    montar();
    await screen.findByText('COMPRADOR SINTÉTICO');
    const antes = listados().length;
    const entrada = screen.getByTestId('entrada-boveda') as HTMLInputElement;
    const zip = new File(['PK'], 'lote.zip', { type: 'application/zip' });
    fireEvent.change(entrada, { target: { files: [zip] } });
    const reporte = await screen.findByRole('region', { name: 'Reporte de la carga' });
    expect(reporte.textContent).toContain('importados');
    expect(reporte.textContent).toContain('ya existían');
    expect(screen.getByText(/No es XML\./)).toBeTruthy();
    const post = peticiones.find((p) => p.method === 'POST');
    expect((post?.body as FormData).getAll('archivos')).toHaveLength(1);
    await waitFor(() => expect(listados().length).toBeGreaterThan(antes));
  });

  it('filtrar por recibidos manda el filtro y vuelve a la página 1', async () => {
    montar();
    await screen.findByText('COMPRADOR SINTÉTICO');
    fireEvent.change(screen.getByLabelText('Dirección'), { target: { value: 'recibido' } });
    await waitFor(() => {
      const u = new URL(ultimo().url);
      expect(u.searchParams.get('direccion')).toBe('recibido');
      expect(u.searchParams.get('pagina')).toBe('1');
    });
  });

  it('pagina hacia adelante', async () => {
    total = 120;
    montar();
    await screen.findByText(/página 1 de 3/);
    fireEvent.click(screen.getByRole('button', { name: 'Siguiente' }));
    await waitFor(() => expect(new URL(ultimo().url).searchParams.get('pagina')).toBe('2'));
  });

  it('descarga el XML del renglón', async () => {
    const crear = vi.fn(() => 'blob:x');
    vi.stubGlobal('URL', Object.assign(URL, { createObjectURL: crear, revokeObjectURL: vi.fn() }));
    const clic = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined);
    montar();
    fireEvent.click(await screen.findByRole('button', { name: 'Descargar XML UUID-1' }));
    await waitFor(() => expect(clic).toHaveBeenCalled());
    expect(peticiones.some((p) => p.url.endsWith('/boveda/clientes/taller/cfdi/UUID-1/xml'))).toBe(true);
  });

  it('si la API falla muestra el error y permite reintentar', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => Response.json({ exito: false, error: 'Se cayó la base.' }, { status: 500 })));
    montar();
    expect(await screen.findByText(/Se cayó la base/)).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Reintentar' })).toBeTruthy();
  });

  it('una bóveda vacía lo dice', async () => {
    comprobantes = [];
    total = 0;
    montar();
    expect(await screen.findByText('No hay comprobantes con estos filtros.')).toBeTruthy();
  });
});
