/**
 * Lista de clientes del despacho (E-02).
 *
 * Cubre los tres estados que la pantalla tiene que saber pintar —cargando,
 * error, vacío— porque los tres se ven igual de mal si se dejan sin manejar: un
 * área en blanco enfrente de alguien.
 *
 * Y cubre que la lista **distinga el caso real del sintético**: enseñar los tres
 * clientes como si fueran iguales presentaría datos inventados con el mismo peso
 * que los reales.
 */

import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { ClienteResumen } from '../services/despachoApi';

const CARTERA: ClienteResumen[] = [
  { id: 'demo', nombre: 'Servicios Administrativos Integrales', giro: 'Servicios administrativos', origen: 'fixtures-s04', num_empleados: 9, prima_riesgo: '0.0054355', clase_riesgo: null, clave_periodicidad: '04', zona: 'general' },
  { id: 'cafeteria', nombre: 'Cafeteria La Estacion', giro: 'Alimentos y bebidas', origen: 'sintetico', num_empleados: 4, prima_riesgo: '0.0113065', clase_riesgo: 2, clave_periodicidad: '04', zona: 'general' },
];

const navigate = vi.fn();
const setClienteId = vi.fn();
const recargar = vi.fn();
const estado = {
  clientes: CARTERA as ClienteResumen[],
  clienteId: 'demo' as string | null,
  loading: false,
  error: null as string | null,
};

vi.mock('../context/clienteActivoStore', () => ({
  useClienteActivo: () => ({
    clientes: estado.clientes,
    clienteId: estado.clienteId,
    cliente: null,
    loading: estado.loading,
    error: estado.error,
    setClienteId,
    recargar,
  }),
}));

vi.mock('react-router-dom', async () => {
  const real = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return { ...real, useNavigate: () => navigate };
});

const { default: ClientesPage } = await import('./ClientesPage');

function montar() {
  return render(<MemoryRouter><ClientesPage /></MemoryRouter>);
}

afterEach(() => {
  estado.clientes = CARTERA;
  estado.clienteId = 'demo';
  estado.loading = false;
  estado.error = null;
  navigate.mockClear();
  setClienteId.mockClear();
  recargar.mockClear();
  cleanup();
});

describe('lista de clientes', () => {
  it('pinta la cartera con giro, empleados y prima', () => {
    montar();

    expect(screen.getByText('Servicios Administrativos Integrales')).toBeTruthy();
    expect(screen.getByText('Cafeteria La Estacion')).toBeTruthy();
    expect(screen.getByText('9')).toBeTruthy();
    expect(screen.getByText('4')).toBeTruthy();
    // La prima viaja como fracción y se muestra como porcentaje.
    expect(screen.getByText('0.54355 %')).toBeTruthy();
    expect(screen.getByText('1.13065 %')).toBeTruthy();
  });

  it('distingue el caso real anonimizado de los datos sintéticos', () => {
    montar();
    expect(screen.getByText(/Caso real anonimizado/)).toBeTruthy();
    expect(screen.getByText(/Datos sintéticos/)).toBeTruthy();
  });

  it('marca cuál es el cliente activo', () => {
    estado.clienteId = 'cafeteria';
    montar();
    expect(screen.getByText('ACTIVO')).toBeTruthy();
  });

  it('abrir un cliente lo activa y navega a su ficha', () => {
    montar();
    fireEvent.click(screen.getByText('Cafeteria La Estacion'));

    expect(setClienteId).toHaveBeenCalledWith('cafeteria');
    expect(navigate).toHaveBeenCalledWith('/app/clientes/cafeteria');
  });
});

describe('estados que no son la lista feliz', () => {
  it('mientras carga lo dice, en vez de enseñar una lista vacía', () => {
    estado.loading = true;
    estado.clientes = [];
    montar();

    expect(screen.getByText(/Cargando la cartera/)).toBeTruthy();
    expect(screen.queryByText(/La cartera está vacía/)).toBeNull();
  });

  it('con error lo enseña y ofrece reintentar', () => {
    estado.error = 'No se pudo cargar la cartera: HTTP 500';
    estado.clientes = [];
    montar();

    expect(screen.getByText(/No se pudo cargar la cartera/)).toBeTruthy();
    fireEvent.click(screen.getByText('Reintentar'));
    expect(recargar).toHaveBeenCalledTimes(1);
  });

  it('el vacío sólo aparece cuando de verdad no hay clientes ni error', () => {
    estado.clientes = [];
    montar();
    expect(screen.getByText(/La cartera está vacía/)).toBeTruthy();
  });

  it('con error no dice además que la cartera está vacía', () => {
    estado.error = 'No se pudo cargar la cartera: HTTP 500';
    estado.clientes = [];
    montar();
    expect(screen.queryByText(/La cartera está vacía/)).toBeNull();
  });
});
