/**
 * `/app/nomina` y la redirección de `/app/nomina-demo` (E-03).
 *
 * El enlace "Nómina" del sidebar del contador no conoce el id del cliente:
 * `getSidebarLinks` es función pura del perfil. Esta pantalla lo resuelve.
 *
 * **Lo que más importa: que NO caiga en `demo` cuando no hay cliente activo.**
 * Un default silencioso ahí sería el bloqueante de E-02 otra vez — el sidebar
 * llevaría a una nómina que no es la de nadie en particular.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

const estado = {
  clienteId: 'taller' as string | null,
  loading: false,
  error: null as string | null,
};

vi.mock('../context/clienteActivoStore', () => ({
  useClienteActivo: () => ({
    clientes: [], cliente: null,
    clienteId: estado.clienteId,
    loading: estado.loading,
    error: estado.error,
    setClienteId: vi.fn(), recargar: vi.fn(),
  }),
}));

const { default: NominaDelClienteActivo } = await import('./NominaDelClienteActivo');

/** Marcador en lugar de la pantalla real: aquí sólo importa a dónde se llega. */
function Destino() {
  return <div>nómina del cliente</div>;
}

function montar(ruta = '/app/nomina') {
  return render(
    <MemoryRouter initialEntries={[ruta]}>
      <Routes>
        <Route path="/app/nomina" element={<NominaDelClienteActivo />} />
        <Route
          path="/app/nomina-demo"
          element={<NominaDelClienteActivo />}
        />
        <Route path="/app/clientes/:id/nomina" element={<Destino />} />
        <Route path="/app/clientes" element={<div>cartera</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  estado.clienteId = 'taller';
  estado.loading = false;
  estado.error = null;
});

afterEach(cleanup);

describe('/app/nomina', () => {
  it('lleva a la nómina del cliente activo', async () => {
    montar();
    await waitFor(() => expect(screen.getByText('nómina del cliente')).toBeTruthy());
  });

  it('sin cliente activo NO cae en demo: manda a elegir', () => {
    // El default silencioso sería el bloqueante de E-02 por otra puerta.
    estado.clienteId = null;
    montar();

    expect(screen.getByText('Elige un cliente primero')).toBeTruthy();
    expect(screen.queryByText('nómina del cliente')).toBeNull();
    expect(screen.getByText('Ver la cartera')).toBeTruthy();
  });

  it('mientras carga la cartera no dice que no hay cliente', () => {
    estado.clienteId = null;
    estado.loading = true;
    montar();

    expect(screen.getByText(/Buscando el cliente activo/)).toBeTruthy();
    expect(screen.queryByText('Elige un cliente primero')).toBeNull();
  });

  it('si la cartera falló lo dice, en vez de invitar a elegir de una lista vacía', () => {
    estado.clienteId = null;
    estado.error = 'No se pudo cargar la cartera: HTTP 500';
    montar();

    expect(screen.getByText(/No se pudo cargar la cartera/)).toBeTruthy();
    expect(screen.queryByText('Elige un cliente primero')).toBeNull();
  });
});
