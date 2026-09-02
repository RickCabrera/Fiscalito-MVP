/**
 * Cliente activo (E-02) — el estado que hace verdadero "cambio de cliente y
 * todo lo demás cambia con él".
 *
 * Los tres modos de falla que cubre:
 *
 * 1. Un id guardado en `localStorage` que ya no existe en la cartera deja la
 *    app apuntando a un cliente fantasma: la ficha pide un id que da 404 y el
 *    selector se queda en blanco.
 * 2. Cargar la cartera para un CONTRIBUYENTE sería un fetch inútil en cada
 *    arranque de sesión a un endpoint que no le sirve.
 * 3. `localStorage` puede lanzar (modo privado, storage bloqueado). Que no se
 *    pueda recordar la preferencia no es motivo para tumbar la app.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, render, screen, waitFor } from '@testing-library/react';
import type { UserProfile } from './ProfileContext';
import type { ClienteResumen } from '../services/despachoApi';

const perfilBase: UserProfile = {
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

const perfilMock = { actual: perfilBase };

vi.mock('./ProfileContext', () => ({
  useProfile: () => ({ profile: perfilMock.actual, loading: false }),
}));

const CARTERA: ClienteResumen[] = [
  { id: 'demo', nombre: 'Servicios Administrativos Integrales', giro: 'Servicios', origen: 'fixtures-s04', num_empleados: 9, prima_riesgo: '0.0054355', clase_riesgo: null, clave_periodicidad: '04', zona: 'general' },
  { id: 'cafeteria', nombre: 'Cafeteria La Estacion', giro: 'Alimentos', origen: 'sintetico', num_empleados: 4, prima_riesgo: '0.0113065', clase_riesgo: 2, clave_periodicidad: '04', zona: 'general' },
];

const obtenerClientes = vi.fn(async () => CARTERA);
vi.mock('../services/despachoApi', () => ({
  obtenerClientes: () => obtenerClientes(),
}));

const { ClienteActivoProvider } = await import('./ClienteActivoContext');
const { useClienteActivo } = await import('./clienteActivoStore');

function Sonda() {
  const { clienteId, cliente, clientes, loading } = useClienteActivo();
  return (
    <div>
      <span data-testid="id">{clienteId ?? 'sin-cliente'}</span>
      <span data-testid="nombre">{cliente?.nombre ?? 'sin-nombre'}</span>
      <span data-testid="total">{clientes.length}</span>
      <span data-testid="loading">{String(loading)}</span>
    </div>
  );
}

function montar() {
  return render(
    <ClienteActivoProvider>
      <Sonda />
    </ClienteActivoProvider>,
  );
}

beforeEach(() => {
  perfilMock.actual = perfilBase;
  obtenerClientes.mockClear();
  localStorage.clear();
});

afterEach(cleanup);

describe('ClienteActivoContext', () => {
  it('carga la cartera y activa el primer cliente', async () => {
    montar();
    await waitFor(() => expect(screen.getByTestId('id').textContent).toBe('demo'));
    expect(screen.getByTestId('nombre').textContent).toBe('Servicios Administrativos Integrales');
    expect(screen.getByTestId('total').textContent).toBe('2');
  });

  it('respeta el cliente que quedó guardado de la sesión anterior', async () => {
    localStorage.setItem('fiscalito_cliente_activo', 'cafeteria');
    montar();
    await waitFor(() => expect(screen.getByTestId('nombre').textContent).toBe('Cafeteria La Estacion'));
  });

  it('cae al primero si el cliente guardado ya no está en la cartera', async () => {
    localStorage.setItem('fiscalito_cliente_activo', 'cliente-que-ya-no-existe');
    montar();

    await waitFor(() => expect(screen.getByTestId('id').textContent).toBe('demo'));
    // Y corrige lo guardado, para que el fantasma no vuelva en la próxima sesión.
    expect(localStorage.getItem('fiscalito_cliente_activo')).toBe('demo');
  });

  it('no pide la cartera si el perfil no es de contador', async () => {
    perfilMock.actual = { ...perfilBase, contributorType: 'independiente' };
    montar();

    await waitFor(() => expect(screen.getByTestId('loading').textContent).toBe('false'));
    expect(obtenerClientes).not.toHaveBeenCalled();
    expect(screen.getByTestId('total').textContent).toBe('0');
  });

  it('sobrevive a un localStorage que lanza', async () => {
    const setItem = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('storage bloqueado');
    });
    const getItem = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('storage bloqueado');
    });

    montar();
    await waitFor(() => expect(screen.getByTestId('id').textContent).toBe('demo'));

    setItem.mockRestore();
    getItem.mockRestore();
  });

  it('cambiar de cliente cambia lo que leen las pantallas', async () => {
    function Cambiador() {
      const { setClienteId } = useClienteActivo();
      return <button onClick={() => setClienteId('cafeteria')}>cambiar</button>;
    }
    render(
      <ClienteActivoProvider>
        <Sonda />
        <Cambiador />
      </ClienteActivoProvider>,
    );

    await waitFor(() => expect(screen.getByTestId('nombre').textContent).toBe('Servicios Administrativos Integrales'));
    act(() => screen.getByText('cambiar').click());

    expect(screen.getByTestId('nombre').textContent).toBe('Cafeteria La Estacion');
    expect(localStorage.getItem('fiscalito_cliente_activo')).toBe('cafeteria');
  });
});
