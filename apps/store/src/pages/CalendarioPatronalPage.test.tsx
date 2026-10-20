/**
 * Calendario de la cartera y agenda (P3-10). Ruta `/app/calendario`.
 *
 * Las fechas (prórroga por sexto dígito, día 17 inhábil, reglas del IMSS) las calcula el
 * backend; aquí se mide que la semana muestre cada vencimiento de cada cliente en su día, que
 * los filtros viajen en la consulta, que se pueda marcar presentada, crear tareas y generar
 * tareas desde los vencimientos. `hoy` SE INYECTA: nada depende del reloj.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ClienteActivoContext, type ClienteActivoContextType } from '../context/clienteActivoStore';
import type { ObligacionCartera } from '../services/agendaApi';

const { default: CalendarioPatronalPage } = await import('./CalendarioPatronalPage');

/** Lunes 19 de octubre de 2026. */
const HOY = new Date(2026, 9, 19);

function obligacion(over: Partial<ObligacionCartera> = {}): ObligacionCartera {
  return {
    clave: 'mensual:2026-09', cliente: 'pm', cliente_nombre: 'Moral Patrón', tipo: 'fiscal',
    nombre: 'Declaración mensual ISR e IVA de septiembre 2026', periodo: '2026-09',
    fecha_limite: '2026-10-19', fundamento: 'Arts. 14/106 LISR', condicional: false, nota: '',
    estado: 'pendiente', origen_estado: '', fecha_presentacion: null, responsable_uid: '',
    ...over,
  };
}

const CALENDARIO = {
  exito: true,
  obligaciones: [
    obligacion(),
    obligacion({ cliente: 'pf', cliente_nombre: 'Persona Física', fecha_limite: '2026-10-23',
      nota: 'Incluye 5 día(s) hábil(es) de prórroga por el sexto dígito del RFC.' }),
    obligacion({ clave: 'patronal:imss_mensual:septiembre 2026', tipo: 'patronal',
      nombre: 'Cuotas IMSS de septiembre 2026', fecha_limite: '2026-10-19', estado: 'presentada' }),
  ],
  tareas: [{ id: 7, titulo: 'Pedir estados de cuenta', descripcion: '', cliente: 'pm',
    cliente_nombre: 'Moral Patrón', responsable_uid: 'uid-a', fecha: '2026-10-21',
    estado: 'pendiente', origen: 'manual', obligacion_clave: null }],
};

const ACTIVO: ClienteActivoContextType = {
  clientes: [
    { id: 'pm', nombre: 'Moral Patrón' }, { id: 'pf', nombre: 'Persona Física' },
  ] as ClienteActivoContextType['clientes'],
  clienteId: 'pm', cliente: null, loading: false, error: null,
  setClienteId: () => {}, recargar: () => {},
};

let peticiones: { url: string; method: string; body?: string }[] = [];

beforeEach(() => {
  peticiones = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string, init: RequestInit = {}) => {
    const method = init.method ?? 'GET';
    peticiones.push({ url, method, body: init.body as string | undefined });
    if (url.includes('/calendario/cartera')) return Response.json(CALENDARIO);
    if (url.endsWith('/agenda/usuarios')) {
      return Response.json({ usuarios: [{ uid: 'uid-a', nombre: 'Contadora', rol: 'dueno' }] });
    }
    if (url.includes('/obligaciones/estado')) return Response.json({ exito: true, estado: 'presentada' });
    if (url.endsWith('/agenda/tareas') && method === 'POST') return Response.json({ exito: true, tarea: {} });
    if (url.endsWith('/agenda/tareas/desde-obligaciones')) return Response.json({ exito: true, creadas: 2 });
    if (url.includes('/agenda/tareas/7')) return Response.json({ exito: true, tarea: {} });
    return Response.json({ exito: false, error: `no stubbeado: ${url}` }, { status: 500 });
  }));
});

afterEach(() => cleanup());

function montar() {
  return render(
    <MemoryRouter>
      <ClienteActivoContext.Provider value={ACTIVO}>
        <CalendarioPatronalPage hoy={HOY} />
      </ClienteActivoContext.Provider>
    </MemoryRouter>,
  );
}

describe('Calendario de la cartera (P3-10)', () => {
  it('la semana muestra cada vencimiento de cada cliente en su día', async () => {
    montar();
    expect(await screen.findByRole('heading', { name: /Calendario de la cartera/ })).toBeTruthy();
    const lunes = await screen.findByRole('region', { name: 'Día 2026-10-19' });
    expect(within(lunes).getAllByText('Moral Patrón', { selector: 'span' })).toHaveLength(2);
    expect(within(lunes).getByText(/Cuotas IMSS de septiembre/)).toBeTruthy();
    const viernes = screen.getByRole('region', { name: 'Día 2026-10-23' });
    expect(within(viernes).getByText('Persona Física')).toBeTruthy();
    const miercoles = screen.getByRole('region', { name: 'Día 2026-10-21' });
    expect(within(miercoles).getByText(/Pedir estados de cuenta/)).toBeTruthy();
    const pedida = peticiones.find((p) => p.url.includes('/calendario/cartera'))!;
    expect(pedida.url).toContain('desde=2026-10-19');
    expect(pedida.url).toContain('hasta=2026-10-25');
    expect(screen.getByText(/1 presentadas/)).toBeTruthy();
  });

  it('los filtros de cliente, tipo y responsable viajan en la consulta', async () => {
    montar();
    await screen.findByRole('region', { name: 'Día 2026-10-19' });
    fireEvent.change(screen.getByLabelText('Filtrar por cliente'), { target: { value: 'pf' } });
    fireEvent.change(screen.getByLabelText('Filtrar por tipo'), { target: { value: 'patronal' } });
    await waitFor(() => expect(screen.getAllByRole('option', { name: 'Contadora' }).length).toBeGreaterThan(0));
    fireEvent.change(screen.getByLabelText('Filtrar por responsable'), { target: { value: 'uid-a' } });
    await waitFor(() => {
      const ultima = peticiones.filter((p) => p.url.includes('/calendario/cartera')).slice(-1)[0]!;
      expect(ultima.url).toContain('cliente=pf');
      expect(ultima.url).toContain('tipo=patronal');
      expect(ultima.url).toContain('responsable=uid-a');
    });
  });

  it('marca presentada una obligación pendiente', async () => {
    montar();
    fireEvent.click(await screen.findByRole('button', {
      name: /Marcar presentada: Declaración mensual ISR e IVA de septiembre 2026 de Moral Patrón/ }));
    await waitFor(() => expect(peticiones.some((p) => p.method === 'PUT')).toBe(true));
    const put = peticiones.find((p) => p.method === 'PUT')!;
    expect(put.url).toContain('/clientes/pm/obligaciones/estado');
    expect(JSON.parse(put.body!)).toEqual({ clave: 'mensual:2026-09', estado: 'presentada' });
  });

  it('crea tareas a mano y desde los vencimientos de la semana', async () => {
    montar();
    await screen.findByRole('region', { name: 'Día 2026-10-19' });
    fireEvent.change(screen.getByLabelText('Título de la tarea'), { target: { value: 'Llamar al cliente' } });
    fireEvent.change(screen.getByLabelText('Cliente de la tarea'), { target: { value: 'pf' } });
    fireEvent.click(screen.getByRole('button', { name: /Agregar/ }));
    await waitFor(() => expect(peticiones.some((p) => p.url.endsWith('/agenda/tareas') && p.method === 'POST')).toBe(true));
    const alta = peticiones.find((p) => p.url.endsWith('/agenda/tareas') && p.method === 'POST')!;
    expect(JSON.parse(alta.body!)).toMatchObject({ titulo: 'Llamar al cliente', cliente: 'pf', fecha: '2026-10-19' });

    fireEvent.click(screen.getByRole('button', { name: /Tareas desde vencimientos/ }));
    await waitFor(() => expect(peticiones.some((p) => p.url.endsWith('/desde-obligaciones'))).toBe(true));
    const gen = peticiones.find((p) => p.url.endsWith('/desde-obligaciones'))!;
    expect(JSON.parse(gen.body!)).toMatchObject({ desde: '2026-10-19', hasta: '2026-10-25' });
  });

  it('la vista de mes y la agenda piden su rango', async () => {
    montar();
    await screen.findByRole('region', { name: 'Día 2026-10-19' });
    fireEvent.click(screen.getByRole('button', { name: 'mes' }));
    await waitFor(() => expect(peticiones.slice(-1)[0]!.url).toContain('desde=2026-09-28'));
    expect(peticiones.filter((p) => p.url.includes('/calendario/cartera')).slice(-1)[0]!.url).toContain('hasta=2026-11-01');
    fireEvent.click(screen.getByRole('button', { name: 'agenda' }));
    await waitFor(() => {
      const u = peticiones.filter((p) => p.url.includes('/calendario/cartera')).slice(-1)[0]!.url;
      expect(u).toContain('desde=2026-10-01');
      expect(u).toContain('hasta=2026-10-31');
    });
    expect(await screen.findByRole('heading', { name: /Lun 19\/10\/2026/ })).toBeTruthy();
  });

  it('un error del backend se ve, no deja la pantalla en blanco', async () => {
    vi.stubGlobal('fetch', vi.fn(async () =>
      Response.json({ exito: false, error: 'El rango del calendario va de 1 día a 400 días.' }, { status: 422 })));
    montar();
    expect(await screen.findByText(/El rango del calendario va de 1 día a 400 días/)).toBeTruthy();
  });
});
