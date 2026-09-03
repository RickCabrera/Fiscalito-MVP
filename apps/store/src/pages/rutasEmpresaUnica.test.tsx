/**
 * Las rutas en MODO EMPRESA ÚNICA (O-01).
 *
 * DOS MODOS DE FALLA QUE NINGÚN TEST DE FUNCIÓN PURA VE
 * -----------------------------------------------------
 * 1. **`RutasDeCartera` se monta como `<RutasDeCartera />` en vez de invocarse.**
 *    `createRoutesFromChildren` de react-router sólo entiende `<Route>` y
 *    `React.Fragment` entre los hijos de `<Routes>`: un componente propio se
 *    **descarta en silencio** y las rutas dejan de existir. `/app/nomina` daría
 *    un área de contenido en blanco, sin un solo error en consola, en la
 *    pantalla principal de la app.
 * 2. **`/app/clientes` sigue montando la cartera.** El pivote se anuncia y la
 *    lista de clientes sigue ahí, alcanzable por URL, con los clientes de otra
 *    cuenta si los hubiera.
 *
 * Por eso esto monta `AppRoutes` de verdad, con el árbol completo, en vez de
 * declarar tres `<Route>` a mano: un árbol escrito en el test no puede cazar
 * una ruta que el árbol real perdió.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { UserProfile } from '../context/ProfileContext';
import { carteraDePrueba } from '../test/carteraDePrueba';
import { EMPRESA_POR_DEFECTO } from '../services/empresa';
import type { ClienteCartera } from '../services/carteraApi';

/**
 * Modo empresa única EXPLÍCITO, dentro de un `beforeEach`.
 *
 * A nivel de módulo NO sirve: el `afterEach` global de `test/setup.ts` hace
 * `vi.unstubAllEnvs()`, así que el stub sólo sobrevivía al primer test del
 * archivo y del segundo en adelante esto medía el **default**. Pasaba igual
 * —el default es encendido— y por eso no se notaba, que es justo lo que lo
 * hacía peligroso: el día que alguien invierta el default, este archivo
 * empezaría a medir el modo despacho sin fallar.
 */
beforeEach(() => {
  vi.stubEnv('VITE_MODO_EMPRESA_UNICA', '1');
});

const PERIODO = { inicio: '2026-08-16', fin: '2026-08-31', fecha_pago: '2026-08-31' };

const EMPRESA: ClienteCartera = {
  id: 'empresa',
  nombre: 'Orca Ordorica Cristal Templado',
  giro: '',
  origen: 'propio',
  rfc: 'OOC010101AAA',
  registro_patronal: 'A1234567890',
  prima_riesgo: '0.0113065',
  clase_riesgo: 3,
  clave_periodicidad: '04',
  zona: 'general',
  periodo_sugerido: PERIODO,
  empleados: [],
};

const perfil: UserProfile = {
  contributorType: 'contador',
  rfc: '', regimen: '', nombre: 'Operadora', actividad: '', cp: '',
  telefono: '', nombreNegocio: '', numEmpleados: '', nombreDespacho: '',
  onboardingComplete: true,
};

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({ user: { uid: 'uid-1', email: 'operadora@ejemplo.mx' }, loading: false }),
  AuthProvider: ({ children }: { children: React.ReactNode }) => children,
}));

vi.mock('../context/ProfileContext', () => ({
  useProfile: () => ({
    profile: perfil, loading: false, error: null,
    setProfile: vi.fn(), isOnboardingComplete: () => true,
  }),
}));

vi.mock('../context/carteraStore', async () => {
  const { carteraDePrueba: doble } = await import('../test/carteraDePrueba');
  return {
    useCartera: () =>
      doble({
        clientes: [EMPRESA],
        origen: 'firestore',
        soloLectura: false,
        clientePorId: (id: string) => (id === 'empresa' ? EMPRESA : null),
        empresa: {
          ...EMPRESA_POR_DEFECTO,
          razonSocial: EMPRESA.nombre,
          primaRiesgo: EMPRESA.prima_riesgo,
        },
      }),
    CarteraContext: { Provider: ({ children }: { children: React.ReactNode }) => children },
  };
});

vi.mock('../context/clienteActivoStore', () => ({
  useClienteActivo: () => ({
    clientes: [{ ...EMPRESA, num_empleados: 0 }],
    clienteId: 'empresa',
    cliente: { ...EMPRESA, num_empleados: 0 },
    loading: false, error: null,
    setClienteId: vi.fn(), recargar: vi.fn(),
  }),
}));

// El chat de voz sale a la red al montar y el toggle de tema necesita
// `window.matchMedia`, que jsdom no trae: ninguno de los dos tiene que ver con
// rutas. Mismo doble que usa `AppLayout.test.tsx`.
vi.mock('../components/FiscalitoVoiceChat', () => ({ default: () => null }));
vi.mock('../components/ThemeToggle', () => ({ default: () => null }));

/** El backend de la nómina: la pantalla lo llama al montar (checadas). */
vi.mock('../services/nominaDemoApi', () => ({
  obtenerEventos: vi.fn(async () => ({ eventos: [] })),
  cerrarPeriodo: vi.fn(),
  calcularNomina: vi.fn(),
  obtenerPlantillaDemo: vi.fn(),
}));

const { default: AppRoutes } = await import('../AppRoutes');

function montar(ruta: string) {
  return render(
    <MemoryRouter initialEntries={[ruta]}>
      <AppRoutes />
    </MemoryRouter>,
  );
}

afterEach(cleanup);

describe('rutas en modo empresa única', () => {
  it('`/app/nomina` PINTA la nómina, no un área en blanco', async () => {
    montar('/app/nomina');
    // Los cuatro pasos de E-06: si la ruta se hubiera descartado en silencio,
    // aquí no habría absolutamente nada.
    // El título del paso lleva su número en el mismo nodo ("1. Checadas
    // recibidas"), así que se busca por expresión regular y no por igualdad.
    await waitFor(() => expect(screen.getByText(/Checadas recibidas/)).toBeTruthy());
    expect(screen.getAllByText(/Cerrar quincena/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Calcular nómina/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Exportar/).length).toBeGreaterThan(0);
  });

  it('la nómina que pinta es la de la EMPRESA, sin que la ruta lleve un id', async () => {
    montar('/app/nomina');
    await waitFor(() =>
      expect(screen.getAllByText(/Orca Ordorica/).length).toBeGreaterThan(0),
    );
  });

  it('`/app/clientes` redirige a la nómina: la cartera no es alcanzable', async () => {
    montar('/app/clientes');
    await waitFor(() => expect(screen.getByText(/Checadas recibidas/)).toBeTruthy());
    // Y no queda ni rastro de la cartera: ni la pantalla, ni la migaja del
    // encabezado, que apuntaba a `/app/clientes` — una ruta que aquí redirige.
    expect(screen.queryByText('Clientes')).toBeNull();
    expect(screen.queryByRole('navigation', { name: 'Ruta' })).toBeNull();
  });

  it('`/app/clientes/:id` y su nómina también redirigen', async () => {
    for (const ruta of ['/app/clientes/demo', '/app/clientes/demo/nomina']) {
      montar(ruta);
      await waitFor(() => expect(screen.getByText(/Checadas recibidas/)).toBeTruthy());
      cleanup();
    }
  });

  it('la ruta vieja de la demo (`/app/nomina-demo`) no cae en el cliente `demo`', async () => {
    // Sin esto, el enlace del runbook mandaría a `/app/clientes/demo/nomina`,
    // que en este modo redirige otra vez: dos saltos para llegar al mismo sitio,
    // y con un id de un cliente que ya no existe en el camino.
    montar('/app/nomina-demo');
    await waitFor(() => expect(screen.getByText(/Checadas recibidas/)).toBeTruthy());
  });

  it('el sidebar no ofrece Clientes', async () => {
    montar('/app/nomina');
    await waitFor(() => expect(screen.getByText(/Checadas recibidas/)).toBeTruthy());
    expect(screen.queryByRole('link', { name: /Clientes/ })).toBeNull();
    expect(screen.getAllByRole('link', { name: /Empleados/ }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole('link', { name: /Nómina/ }).length).toBeGreaterThan(0);
  });

  it('no se pinta el selector de cliente activo', async () => {
    montar('/app/empleados');
    await waitFor(() => expect(screen.getAllByText(/Empleados/).length).toBeGreaterThan(0));
    // El selector es un `<select>` con etiqueta "Cliente" (E-02).
    expect(screen.queryByRole('combobox', { name: /Cliente/i })).toBeNull();
  });

  it('el carrete de la cartera SIGUE en el árbol: apagar no es borrar', async () => {
    // El módulo se importa igual en los dos modos. Si alguien borrara
    // `ClientesPage`, este import fallaría — y el modo despacho, que es lo que
    // Ricardo pidió conservar, se habría perdido sin que nadie lo notara.
    const { default: ClientesPage } = await import('./ClientesPage');
    expect(typeof ClientesPage).toBe('function');
  });
});

describe('la nómina se bloquea si falta configurar la empresa', () => {
  it('sin prima de riesgo lo dice, en vez de dejar que el backend responda 422', async () => {
    vi.doMock('../context/carteraStore', async () => {
      const sinConfigurar: ClienteCartera = { ...EMPRESA, nombre: '', prima_riesgo: '' };
      return {
        useCartera: () =>
          carteraDePrueba({
            clientes: [sinConfigurar],
            origen: 'firestore',
            soloLectura: false,
            clientePorId: (id: string) => (id === 'empresa' ? sinConfigurar : null),
          }),
      };
    });
    vi.resetModules();
    const { default: Rutas } = await import('../AppRoutes');
    render(
      <MemoryRouter initialEntries={['/app/nomina']}>
        <Rutas />
      </MemoryRouter>,
    );

    await waitFor(() =>
      expect(screen.getAllByText(/Configuración de empresa/).length).toBeGreaterThan(0),
    );
    // Y el botón de cerrar quincena está apagado: no es sólo un letrero.
    const boton = screen.getByRole('button', { name: /Cerrar quincena/ });
    expect((boton as HTMLButtonElement).disabled).toBe(true);
    vi.doUnmock('../context/carteraStore');
  });
});
