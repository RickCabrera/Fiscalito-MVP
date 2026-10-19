/**
 * La pantalla de Descarga SAT (P1-02), medida por lo que resuelve: pide la
 * config, el calendario y las solicitudes del CLIENTE ACTIVO, pinta un estado
 * por día, guarda la configuración, encola "descargar ahora" e histórica, y
 * avisa con enlace a la ficha cuando falta la e.firma. `fetch` stubbeado.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { DiaBitacora, SolicitudSat } from '../services/satDescargaApi';

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

const { default: DescargaSatPage } = await import('./DescargaSatPage');

function dias(anio: number, mes: number): DiaBitacora[] {
  const n = new Date(anio, mes, 0).getDate();
  const estados = ['completo', 'en_proceso', 'fallido', 'sin_movimientos'] as const;
  return Array.from({ length: n }, (_, i) => ({
    fecha: `${anio}-${String(mes).padStart(2, '0')}-${String(i + 1).padStart(2, '0')}`,
    estado: i < 4 ? estados[i] : 'no_solicitado',
    solicitudes: i < 4 ? 1 : 0, emitidos: i === 0 ? 3 : 0, recibidos: 0, metadata: 0,
    cancelados: 0, mensaje: i === 2 ? 'La e.firma está revocada o caduca (304).' : '',
  }));
}

const solicitud: SolicitudSat = {
  id: 1, direccion: 'emitidos', tipo: 'cfdi', estado_comprobante: 'todos',
  fecha_inicial: '2026-09-01T00:00:00', fecha_final: '2026-09-30T23:59:59', origen: 'manual',
  id_solicitud: 'abc', estado: 'terminada', codigo: '5000',
  mensaje: 'Terminada: 120 XML nuevos en la bóveda, 3 ya existían.', paquetes: 1,
  paquetes_procesados: 1, xml_importados: 120, duplicados: 3, metadata_registros: 0,
  proxima_verificacion: null, creado_en: null,
};

let peticiones: { url: string; method: string; body?: string }[] = [];
let efirmaVigente = true;

beforeEach(() => {
  cleanup();
  peticiones = [];
  activo.clienteId = 'taller';
  efirmaVigente = true;
  vi.stubGlobal('fetch', vi.fn(async (url: string, init: RequestInit = {}) => {
    const method = init.method ?? 'GET';
    peticiones.push({ url, method, body: typeof init.body === 'string' ? init.body : undefined });
    const u = new URL(url);
    if (u.pathname.endsWith('/config')) {
      return Response.json({
        exito: true,
        config: { activa: false, emitidos: true, recibidos: true, metadata: true, cancelados: true,
          desde: null, hora: '02:00', pausada_por: efirmaVigente ? null : 'efirma',
          ultimo_dia_encolado: null },
        efirma: efirmaVigente
          ? { vigente: true, valido_hasta: '2030-01-01T00:00:00+00:00', mensaje: '' }
          : { vigente: false, valido_hasta: null, mensaje: 'El cliente no tiene e.firma (FIEL) cargada.' },
        alertas: [],
      });
    }
    if (u.pathname.endsWith('/bitacora')) {
      const anio = Number(u.searchParams.get('anio'));
      const mes = Number(u.searchParams.get('mes'));
      return Response.json({ exito: true, anio, mes, dias: dias(anio, mes) });
    }
    if (u.pathname.endsWith('/solicitudes')) {
      return Response.json({ exito: true, total: 1, pagina: 1, por_pagina: 20, solicitudes: [solicitud] });
    }
    if (u.pathname.endsWith('/descargar') || u.pathname.endsWith('/historica')) {
      return Response.json({ exito: true, encolados: [
        { trabajo_id: 1, inicio: '2026-09-01', fin: '2026-09-30' },
        { trabajo_id: 2, inicio: '2026-10-01', fin: '2026-10-05' },
      ] });
    }
    return new Response('{}', { status: 404 });
  }));
});

function montar() {
  return render(<MemoryRouter><DescargaSatPage /></MemoryRouter>);
}

describe('DescargaSatPage', () => {
  it('sin cliente activo pide elegir uno y no llama al backend', () => {
    activo.clienteId = null;
    montar();
    expect(screen.getByText('Elige un cliente primero')).toBeTruthy();
    expect(peticiones).toHaveLength(0);
  });

  it('pide todo del cliente activo y marca cada día con su estado', async () => {
    const { container } = montar();
    await screen.findByText('Solicitudes al SAT');
    const rutas = peticiones.map((p) => new URL(p.url).pathname);
    expect(rutas.every((r) => r.startsWith('/api/v1/sat/clientes/taller/'))).toBe(true);
    const celdas = container.querySelectorAll('[role="gridcell"]');
    expect(celdas.length).toBeGreaterThanOrEqual(28);
    expect(celdas[0].getAttribute('data-estado')).toBe('completo');
    expect(celdas[1].getAttribute('data-estado')).toBe('en_proceso');
    expect(celdas[2].getAttribute('data-estado')).toBe('fallido');
    expect(celdas[2].getAttribute('aria-label')).toContain('revocada');
    expect(celdas[3].getAttribute('data-estado')).toBe('sin_movimientos');
    expect(screen.getByText(/120 XML nuevos/)).toBeTruthy();
  });

  it('cambiar de mes pide la bitácora de ese mes', async () => {
    montar();
    await screen.findByText('Solicitudes al SAT');
    fireEvent.click(screen.getByLabelText('Mes anterior'));
    await waitFor(() => {
      const bit = peticiones.filter((p) => p.url.includes('/bitacora'));
      const ultima = new URL(bit[bit.length - 1].url);
      const hoy = new Date();
      const esperado = hoy.getMonth() === 0 ? 12 : hoy.getMonth();
      expect(ultima.searchParams.get('mes')).toBe(String(esperado));
    });
  });

  it('guarda la configuración con lo que se cambió', async () => {
    montar();
    await screen.findByText('Guardar configuración');
    fireEvent.click(screen.getByLabelText(/Descargar del SAT todos los días/));
    fireEvent.click(screen.getByText('Guardar configuración'));
    await waitFor(() => expect(peticiones.some((p) => p.method === 'PUT')).toBe(true));
    await screen.findByText(/Configuración guardada\./);
    const put = peticiones.find((p) => p.method === 'PUT');
    expect(JSON.parse(put!.body!)).toMatchObject({ activa: true, hora: '02:00', emitidos: true });
  });

  it('descargar ahora encola el rango y lo dice', async () => {
    montar();
    const boton = await screen.findByRole('button', { name: /Descargar ahora/ });
    fireEvent.change(screen.getByLabelText('Descargar desde'), { target: { value: '2026-09-01' } });
    fireEvent.change(screen.getByLabelText('Descargar hasta'), { target: { value: '2026-10-05' } });
    fireEvent.click(boton);
    await screen.findByText(/Se pidieron 2 mes\(es\) al SAT/);
    const post = peticiones.find((p) => p.url.endsWith('/descargar'));
    expect(JSON.parse(post!.body!)).toMatchObject({ desde: '2026-09-01', hasta: '2026-10-05' });
  });

  it('la histórica pide desde la fecha elegida', async () => {
    montar();
    const boton = await screen.findByRole('button', { name: /Descarga histórica/ });
    fireEvent.change(screen.getByLabelText('Histórica desde'), { target: { value: '2024-01-01' } });
    fireEvent.click(boton);
    await screen.findByText(/Se pidieron 2 mes/);
    const post = peticiones.find((p) => p.url.endsWith('/historica'));
    expect(JSON.parse(post!.body!)).toMatchObject({ desde: '2024-01-01' });
  });

  it('sin e.firma avisa con enlace a la ficha y no deja descargar', async () => {
    efirmaVigente = false;
    montar();
    const alerta = await screen.findByRole('alert');
    expect(within(alerta).getByText(/no tiene e.firma/)).toBeTruthy();
    const enlace = within(alerta).getByRole('link', { name: /ficha del cliente/ });
    expect(enlace.getAttribute('href')).toBe('/app/clientes/taller');
    expect((screen.getByRole('button', { name: /Descargar ahora/ }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByText(/En pausa: falta una e.firma vigente/)).toBeTruthy();
  });

  it('un error del backend se ve y se puede reintentar', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => Response.json({ exito: false, error: 'Se cayó el SAT' }, { status: 502 })));
    montar();
    await screen.findByText(/Se cayó el SAT/);
    expect(screen.getByRole('button', { name: 'Reintentar' })).toBeTruthy();
  });
});
