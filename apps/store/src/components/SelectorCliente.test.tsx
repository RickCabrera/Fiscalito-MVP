/**
 * Selector de cliente activo (E-02).
 *
 * LO QUE MÁS IMPORTA AQUÍ es dónde aparece y dónde NO, contra una regla que no
 * se ha movido: entra la ruta que **lee** un cliente, no la que habla de
 * clientes. Calendario y Perfil siguen fuera —Perfil es del despacho, y el
 * calendario es el patronal de TODA la cartera desde que E-07 resolvió §D21, no
 * el de un cliente—, y T1 metió la pantalla de Fiscalito porque sí lee uno.
 */

import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import type { ClienteResumen } from '../services/despachoApi';
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

const CARTERA: ClienteResumen[] = [
  { id: 'demo', nombre: 'Servicios Administrativos Integrales', giro: 'Servicios', origen: 'fixtures-s04', num_empleados: 9, prima_riesgo: '0.0054355', clase_riesgo: null, clave_periodicidad: '04', zona: 'general' },
  { id: 'taller', nombre: 'Taller Nogal', giro: 'Reparacion', origen: 'sintetico', num_empleados: 12, prima_riesgo: '0.0259840', clase_riesgo: 3, clave_periodicidad: '04', zona: 'general' },
];

const setClienteId = vi.fn();
const estado = { clienteId: 'demo', loading: false, clientes: CARTERA, error: null as string | null };

vi.mock('../context/clienteActivoStore', () => ({
  useClienteActivo: () => ({
    clientes: estado.clientes,
    clienteId: estado.clienteId,
    cliente: estado.clientes.find((c) => c.id === estado.clienteId) ?? null,
    loading: estado.loading,
    error: estado.error,
    setClienteId,
    recargar: vi.fn(),
  }),
}));

const { default: SelectorCliente } = await import('./SelectorCliente');
const { rutaTieneAlcanceDeCliente } = await import('../services/navigation');

function montar(ruta: string) {
  return render(
    <MemoryRouter initialEntries={[ruta]}>
      <Routes>
        <Route path="/app/clientes" element={<SelectorCliente />} />
        <Route path="/app/clientes/:id" element={<SelectorCliente />} />
        <Route path="/app/nomina-demo" element={<SelectorCliente />} />
        <Route path="/app/store/fiscalito/use" element={<SelectorCliente />} />
        <Route path="/app/profile" element={<SelectorCliente />} />
      </Routes>
    </MemoryRouter>,
  );
}

afterEach(() => {
  estado.clienteId = 'demo';
  estado.loading = false;
  estado.clientes = CARTERA;
  estado.error = null;
  setClienteId.mockClear();
  cleanup();
});

describe('dónde se muestra el selector', () => {
  it.each(['/app/clientes', '/app/clientes/taller'])(
    'aparece en %s, que depende del cliente',
    (ruta) => {
      montar(ruta);
      expect(screen.getByLabelText('Cliente activo')).toBeTruthy();
    },
  );

  it('NO aparece en /app/profile, que es del despacho y no de un cliente', () => {
    montar('/app/profile');
    expect(screen.queryByLabelText('Cliente activo')).toBeNull();
  });

  /**
   * CAMBIÓ EN T1, Y EL CRITERIO NO SE RELAJÓ PARA MOVERLA.
   *
   * Hasta E-07, Fiscalito era el servicio fiscal DEL DESPACHO —sus propias
   * declaraciones como persona física— y un selector de cliente encima le
   * habría mentido sobre lo que veía. Desde T1 la pantalla lee el cliente
   * activo y filtra sus tabs con el régimen de ESE cliente, así que cumple la
   * regla de admisión de `RUTAS_CON_CLIENTE` tal como estaba escrita: entra la
   * ruta que LEE un cliente, no la que habla de clientes. Y sin el selector, el
   * contador no podría cambiar de cliente sin salirse de la pantalla.
   */
  it('SÍ aparece en /app/store/fiscalito/use, que desde T1 lee el cliente activo', () => {
    montar('/app/store/fiscalito/use');
    expect(screen.getByLabelText('Cliente activo')).toBeTruthy();
  });

  /**
   * La pantalla de nómina todavía NO lee el cliente activo: cae en los defaults
   * de `nominaDemoApi`, que son los del cliente `demo`. Un selector encima
   * afirmaría "Taller Nogal" sobre los nueve empleados del caso real y su PDF.
   * **E-03 la cablea y entonces sí entra.**
   */
  it('NO aparece en /app/nomina-demo, que todavía no lee el cliente activo', () => {
    montar('/app/nomina-demo');
    expect(screen.queryByLabelText('Cliente activo')).toBeNull();
  });

  /**
   * R-05. `navigation.ts` promete, en el comentario de `RUTAS_CON_CLIENTE`, que
   * "esta constante se mueve con ella o el selector desaparece justo donde más
   * se necesita". La promesa estaba escrita y la prueba no: quitar
   * `/app/empleados` y `/app/dispositivos` de la constante dejaba las 405
   * pruebas en verde y apagaba el selector en las dos pantallas nuevas — o sea
   * el mecanismo entero de R-05, en silencio. Un revisor lo demostró.
   */
  it('las pantallas de empleados y dispositivos llevan selector de cliente', () => {
    expect(rutaTieneAlcanceDeCliente('/app/empleados')).toBe(true);
    expect(rutaTieneAlcanceDeCliente('/app/dispositivos')).toBe(true);
  });

  it('la regla de alcance es explícita y no un prefijo suelto', () => {
    expect(rutaTieneAlcanceDeCliente('/app/clientes')).toBe(true);
    expect(rutaTieneAlcanceDeCliente('/app/clientes/taller')).toBe(true);
    // T1: Fiscalito entró porque LEE el cliente activo y filtra sus tabs con el
    // régimen de ese cliente. La ficha de catálogo del servicio no lo lee y se
    // queda fuera: la regla de admisión no se relajó para meterla.
    expect(rutaTieneAlcanceDeCliente('/app/store/fiscalito/use')).toBe(true);
    expect(rutaTieneAlcanceDeCliente('/app/store/fiscalito')).toBe(false);
    expect(rutaTieneAlcanceDeCliente('/app/nomina-demo')).toBe(false);
    expect(rutaTieneAlcanceDeCliente('/app/profile')).toBe(false);
    expect(rutaTieneAlcanceDeCliente('/app')).toBe(false);
    // Un prefijo que sólo comparte texto no cuenta.
    expect(rutaTieneAlcanceDeCliente('/app/clientes-otros')).toBe(false);
  });
});

describe('comportamiento del selector', () => {
  it('lista la cartera con su número de empleados', () => {
    montar('/app/clientes');
    const opciones = screen.getAllByRole('option').map((o) => o.textContent);
    expect(opciones).toEqual([
      'Servicios Administrativos Integrales · 9 empleados',
      'Taller Nogal · 12 empleados',
    ]);
  });

  it('marca el cliente activo como seleccionado', () => {
    estado.clienteId = 'taller';
    montar('/app/clientes');
    expect((screen.getByLabelText('Cliente activo') as HTMLSelectElement).value).toBe('taller');
  });

  it('cambiar de opción cambia el cliente activo', () => {
    montar('/app/clientes');
    fireEvent.change(screen.getByLabelText('Cliente activo'), { target: { value: 'taller' } });
    expect(setClienteId).toHaveBeenCalledWith('taller');
  });

  it('no se pinta si no hay cartera, en vez de sugerir que está vacía', () => {
    // Es lo que ve un contribuyente que entra por URL: no tiene cartera, y una
    // barra que diga "Sin clientes" afirmaría que el despacho no tiene ninguno.
    estado.clientes = [];
    montar('/app/clientes');
    expect(screen.queryByLabelText('Cliente activo')).toBeNull();
  });

  it('una API caída no se ve igual que una cartera vacía', () => {
    estado.clientes = [];
    estado.error = 'No se pudo cargar la cartera: HTTP 500';
    montar('/app/clientes');

    expect(screen.getByText('No se pudo cargar la cartera')).toBeTruthy();
    expect(screen.queryByLabelText('Cliente activo')).toBeNull();
  });

  it('mientras carga no enseña un selector vacío', () => {
    estado.loading = true;
    montar('/app/clientes');
    expect(screen.queryByLabelText('Cliente activo')).toBeNull();
  });
});
