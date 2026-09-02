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
import type { ClienteCartera } from '../services/carteraApi';

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

/**
 * R-06: LOS CLIENTES SALEN DE LA CARTERA, NO DEL BACKEND.
 *
 * Este archivo doblaba `obtenerClientes()` —`GET /despacho/clientes`, los tres
 * de demostración—, que es exactamente la costura que R-06 corta: con ella, una
 * cuenta nueva veía su lista vacía y el selector de arriba mostrando clientes
 * ajenos. El doble ahora es el de la CARTERA, que es la fuente real.
 */
const PERIODO = { inicio: '2026-08-16', fin: '2026-08-31', fecha_pago: null };
const empleados = (n: number) =>
  Array.from({ length: n }, (_, i) => ({
    empleado_no: `E-${i}`, nombre: `PERSONA ${i}`, puesto: '', salario_diario: '316.00',
    salario_diario_integrado: '331.58', zona: 'general', fecha_alta: null,
    tipo_contrato: 'indeterminado' as const,
    prestaciones: { dias_aguinaldo: 15, dias_vacaciones: 0, prima_vacacional: '0.25' },
    nss: '', employee_no: `E-${i}`, enrolamiento: 'enrolado' as const,
  }));

const CARTERA: ClienteCartera[] = [
  { id: 'demo', nombre: 'Servicios Administrativos Integrales', giro: 'Servicios', origen: 'fixtures-s04', prima_riesgo: '0.0054355', clase_riesgo: null, clave_periodicidad: '04', zona: 'general', periodo_sugerido: PERIODO, empleados: empleados(9) },
  { id: 'cafeteria', nombre: 'Cafeteria La Estacion', giro: 'Alimentos', origen: 'sintetico', prima_riesgo: '0.0113065', clase_riesgo: 2, clave_periodicidad: '04', zona: 'general', periodo_sugerido: PERIODO, empleados: empleados(4) },
];

const estadoCartera = { clientes: CARTERA, loading: false, error: null as string | null };

vi.mock('./carteraStore', async () => {
  const { carteraDePrueba } = await import('../test/carteraDePrueba');
  return {
    useCartera: () =>
      carteraDePrueba({
        clientes: estadoCartera.clientes,
        loading: estadoCartera.loading,
        error: estadoCartera.error,
        origen: 'firestore',
        soloLectura: false,
      }),
  };
});

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
  estadoCartera.clientes = CARTERA;
  estadoCartera.loading = false;
  estadoCartera.error = null;
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

  it('un contribuyente no ve ningún cliente, aunque la cartera traiga datos', async () => {
    // R-06: ya no se mide "no se llamó al endpoint" —el proveedor no llama a
    // nadie, lee la cartera— sino el efecto que importaba: un contribuyente no
    // tiene despacho, así que no debe ver clientes ni con la cartera poblada.
    perfilMock.actual = { ...perfilBase, contributorType: 'independiente' };
    montar();

    await waitFor(() => expect(screen.getByTestId('loading').textContent).toBe('false'));
    expect(screen.getByTestId('total').textContent).toBe('0');
    expect(screen.getByTestId('id').textContent).toBe('sin-cliente');
  });

  it('R-06 · una cartera VACÍA deja el selector sin clientes, no con los demo', async () => {
    // El agujero que cerró R-06 y que no tenía prueba: este proveedor leía
    // `GET /despacho/clientes` por su cuenta, así que una cuenta nueva veía su
    // lista vacía y el selector de arriba mostrando los tres de demostración
    // —con `/app/nomina` llevando a `demo`—. Datos ajenos, en la barra superior
    // y en la nómina.
    estadoCartera.clientes = [];
    montar();

    await waitFor(() => expect(screen.getByTestId('loading').textContent).toBe('false'));
    expect(screen.getByTestId('total').textContent).toBe('0');
    expect(screen.getByTestId('id').textContent).toBe('sin-cliente');
    expect(screen.getByTestId('nombre').textContent).toBe('sin-nombre');
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
