/**
 * `EmpleadosPage` resuelve el cliente activo. (R-05)
 *
 * POR QUÉ EXISTE ESTE ARCHIVO
 * ---------------------------
 * En la primera entrega, la única cobertura de esta pantalla era el caso de
 * `rutasContador.test.tsx`, que dobla `clienteId: 'demo'`. **La rama nula nunca
 * se ejercitaba**, así que cambiar la guarda por `if (false)` dejaba las 405
 * pruebas en verde — y con ella fuera, `cartera.guardarEmpleado(clienteId as
 * string, e)` se dispara con `null` casteado.
 *
 * Es la mitad del "Listo cuando" literal de R-05 ("Sin cliente activo, la
 * pantalla lo pide"), y estaba sin red. `DispositivosPage` sí la tenía; ésta no:
 * el hueco es exactamente el que deja copiar un patrón y probar sólo una copia.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { EmpleadoCartera } from '../services/carteraApi';
import { modoDespacho } from '../test/modoDespacho';

/**
 * MODO DESPACHO (O-01).
 *
 * Este archivo mide el producto de las épicas E, G y R: cartera de clientes,
 * selector de cliente activo y rutas `/app/clientes`. Desde el pivote, el modo
 * por default de la app es **empresa única**, así que el modo en el que corre
 * se declara aquí en vez de heredarse del ambiente.
 *
 * No cambia ninguna aserción: cambia el mundo en el que se evalúan, que es
 * exactamente lo que el flag hace en producción.
 */
modoDespacho();

const clienteActivo = {
  actual: {
    clienteId: 'demo' as string | null,
    cliente: { nombre: 'Cliente Demo' } as { nombre: string } | null,
    loading: false,
  },
};
const empleados = { actual: [] as EmpleadoCartera[] };

vi.mock('../context/clienteActivoStore', () => ({
  useClienteActivo: () => ({
    clientes: [],
    clienteId: clienteActivo.actual.clienteId,
    cliente: clienteActivo.actual.cliente,
    loading: clienteActivo.actual.loading,
    error: null,
    setClienteId: vi.fn(),
    recargar: vi.fn(),
  }),
}));

vi.mock('../context/carteraStore', async () => {
  const { carteraDePrueba } = await import('../test/carteraDePrueba');
  return {
    useCartera: () =>
      carteraDePrueba({
        origen: 'firestore',
        soloLectura: false,
        clientePorId: () => ({
          id: 'demo', nombre: 'Cliente Demo', giro: 'Servicios', origen: 'sintetico',
          prima_riesgo: '0.0054355', clase_riesgo: null, clave_periodicidad: '04',
          zona: 'general',
          periodo_sugerido: { inicio: '2026-08-16', fin: '2026-08-31', fecha_pago: null },
          empleados: empleados.actual,
        }),
      }),
  };
});

const { default: EmpleadosPage } = await import('./EmpleadosPage');

function pintar() {
  return render(
    <MemoryRouter>
      <EmpleadosPage />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  clienteActivo.actual = { clienteId: 'demo', cliente: { nombre: 'Cliente Demo' }, loading: false };
  empleados.actual = [];
});
afterEach(cleanup);

describe('EmpleadosPage · resuelve el cliente activo', () => {
  it('sin cliente activo PIDE uno, no cae en un default', () => {
    clienteActivo.actual = { clienteId: null, cliente: null, loading: false };
    pintar();

    expect(screen.getByText(/Elige un cliente primero/)).toBeTruthy();
    // Y NO pinta la tabla: sin cliente no hay a quién dar de alta, y el botón
    // dispararía `guardarEmpleado(null)`.
    expect(screen.queryByRole('button', { name: /Nuevo empleado/ })).toBeNull();
  });

  it('mientras el cliente activo carga, no acusa de que no hay ninguno', () => {
    // `loading` con `clienteId` todavía nulo es el estado intermedio. Enseñar
    // "elige un cliente" ahí sería el mismo aviso que aparece y se desdice que
    // ya costó un arreglo en la pantalla de dispositivos.
    clienteActivo.actual = { clienteId: null, cliente: null, loading: true };
    pintar();

    expect(screen.queryByText(/Elige un cliente primero/)).toBeNull();
  });

  it('con cliente activo enseña SU plantilla y lo nombra', () => {
    empleados.actual = [
      {
        empleado_no: 'E-01', nombre: 'ANA LOPEZ', puesto: 'Cajera',
        salario_diario: '316.00', salario_diario_integrado: '331.58', zona: 'general',
        fecha_alta: null, tipo_contrato: 'indeterminado',
        prestaciones: { dias_aguinaldo: 15, dias_vacaciones: 0, prima_vacacional: '0.25' },
        nss: '', employee_no: 'E-01', enrolamiento: 'enrolado',
      },
    ];
    pintar();

    expect(screen.getByRole('heading', { name: 'Empleados' })).toBeTruthy();
    // El nombre del cliente es lo que hace verificable que la pantalla y el
    // selector hablan del mismo.
    expect(screen.getByText(/Cliente Demo/)).toBeTruthy();
    expect(screen.getByText('ANA LOPEZ')).toBeTruthy();
  });
});
