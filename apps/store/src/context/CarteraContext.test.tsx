/**
 * El proveedor de la cartera: quién ve qué. (R-06)
 *
 * POR QUÉ EXISTE ESTE ARCHIVO
 * ---------------------------
 * Un revisor demostró que `esClienteDemo` era **código muerto con test encima**:
 * la función existía, se probaba, y no la llamaba nadie. Los tres clientes de
 * demostración desaparecían de una cuenta nueva por otra razón —ya no están en
 * el fallback— y no porque algo los marcara.
 *
 * La diferencia no es teórica. **Cualquier cuenta donde se haya clickeado
 * "Guardar esta cartera en mi cuenta" durante G-03 o la demo del 2026-09-02 ya
 * tiene los tres escritos en su Firestore**, y sin filtro los seguiría viendo en
 * un build de producción: en la lista, en el selector de arriba y en su nómina
 * completa. Con el salario de nueve personas del caso real.
 *
 * TODOS LOS TESTS DE PANTALLA CORREN COMO CUENTA DE DESARROLLO
 * ------------------------------------------------------------
 * En jsdom `import.meta.env.DEV` es `true`. Es cómodo —los tests de la demo
 * siguen midiendo lo suyo— y es una trampa: la rama de PRODUCCIÓN no se ejerce
 * en ningún lado salvo donde alguien escriba `vi.stubEnv('DEV', false)`. Eso es
 * lo que hace este archivo, y es lo que hizo sobrevivir a la mutación que quitó
 * el filtro.
 */

import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import type { UserProfile } from './ProfileContext';
import type { ClienteCartera } from '../services/carteraApi';
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

const perfilBase: UserProfile = {
  contributorType: 'contador', rfc: '', regimen: '612', nombre: 'Contadora',
  actividad: '', cp: '', telefono: '', nombreNegocio: '', numEmpleados: '',
  nombreDespacho: 'Despacho', onboardingComplete: true,
};

vi.mock('./ProfileContext', () => ({
  useProfile: () => ({ profile: perfilBase, loading: false }),
}));
vi.mock('./AuthContext', () => ({
  useAuth: () => ({ user: { uid: 'uid-1', email: 'contadora@ejemplo.mx' }, loading: false }),
}));

const PERIODO = { inicio: '2026-08-16', fin: '2026-08-31', fecha_pago: null };
function cli(id: string, nombre: string, origen: string): ClienteCartera {
  return {
    id, nombre, giro: 'G', origen, prima_riesgo: '0.005', clase_riesgo: null,
    clave_periodicidad: '04', zona: 'general', periodo_sugerido: PERIODO, empleados: [],
  };
}

/** Lo que hay en Firestore: los tres sembrados más uno capturado por el contador. */
const GUARDADOS = [
  cli('demo', 'Servicios Administrativos Integrales', 'fixtures-s04'),
  cli('cafeteria', 'Cafeteria La Estacion', 'sintetico'),
  cli('taller', 'Taller Mecanico Nogal', 'sintetico'),
  cli('mio', 'Cliente Que Yo Capturé', 'propio'),
];

/**
 * R-07: `CarteraContext` importa el DESPACHADOR (`services/cartera`), no
 * `carteraFirestore` directo — quién es el dueño del dato lo decide un solo
 * archivo. Doblar el módulo viejo dejaba pasar el real, que arrastra
 * `carteraBackend` -> `services/firebase` -> `getAuth()`, y eso **lanza sin las
 * llaves de Firebase**: local verde, CI rojo.
 */
vi.mock('../services/cartera', () => ({
  cargarCartera: async () => ({ clientes: GUARDADOS, origen: 'firestore', error: null }),
  guardarCliente: vi.fn(), borrarCliente: vi.fn(),
  guardarEmpleado: vi.fn(), borrarEmpleado: vi.fn(), sembrarDemo: vi.fn(),
}));

const { CarteraProvider } = await import('./CarteraContext');
const { useCartera } = await import('./carteraStore');

function Sonda() {
  const { clientes, clientePorId } = useCartera();
  return (
    <div>
      <span data-testid="nombres">{clientes.map((c) => c.id).join(',')}</span>
      <span data-testid="demo-por-id">{clientePorId('demo') ? 'sí' : 'no'}</span>
      <span data-testid="mio-por-id">{clientePorId('mio') ? 'sí' : 'no'}</span>
    </div>
  );
}

const montar = () => render(<CarteraProvider><Sonda /></CarteraProvider>);

/** Sonda que da de alta un cliente SIN periodo, para ver qué hereda. */
function Alta() {
  const { guardarCliente, loading } = useCartera();
  return (
    <div>
      <span data-testid="listo">{loading ? 'no' : 'sí'}</span>
      <button
        onClick={() =>
          void guardarCliente({
            id: 'nuevo', nombre: 'Nuevo', giro: 'G', origen: 'propio',
            prima_riesgo: '0.005', clase_riesgo: null, clave_periodicidad: '04',
            zona: 'general',
            periodo_sugerido: { inicio: '', fin: '', fecha_pago: null },
          })
        }
      >
        alta
      </button>
    </div>
  );
}

/**
 * La limpieza de env vars vive ahora en `src/test/setup.ts` (O-01).
 *
 * Este archivo tenía la suya —`beforeEach` + `afterEach` con
 * `vi.unstubAllEnvs()`— para que el `DEV=false` de un test no se filtrara al
 * siguiente. Sigue haciendo falta y sigue pasando, pero **desde el `afterEach`
 * global**, que cubre a todos los archivos y no sólo a éste.
 *
 * Tuvo que salir de aquí: el `beforeEach` local corría DESPUÉS del de
 * `modoDespacho()` —el orden es el de registro— y le borraba la declaración de
 * modo, así que este archivo volvía a medirse en modo empresa única y sus cinco
 * casos fallaban. Dejarlo y mover la declaración más abajo habría "funcionado"
 * por orden de líneas, que es la clase de arreglo que se rompe al reordenar
 * imports.
 */
afterEach(cleanup);

describe('CarteraProvider · el periodo del cliente nuevo', () => {
  it('hereda el periodo de un cliente ya visible, no de uno oculto', async () => {
    /**
     * Un cliente nuevo no trae `periodo_sugerido` y lo hereda del primero de la
     * cartera. Tiene que heredarlo de uno **visible**: en una cuenta normal los
     * de demostración están ocultos, y tomar el periodo de uno que el contador
     * no ve sería explicar con qué fechas se va a calcular apuntando a un
     * cliente que no existe para él.
     *
     * La mutación que esto mata —quitar la herencia entera— dejaba al primer
     * cliente de toda cuenta nueva sin periodo, que es el hueco de E4.
     */
    vi.stubEnv('DEV', false);
    const { guardarCliente } = await import('../services/cartera');
    render(<CarteraProvider><Alta /></CarteraProvider>);

    await waitFor(() => expect(screen.getByTestId('listo').textContent).toBe('sí'));
    screen.getByRole('button', { name: 'alta' }).click();

    await waitFor(() => expect(guardarCliente).toHaveBeenCalled());
    const guardado = vi.mocked(guardarCliente).mock.calls[0][1];
    // El único visible en una cuenta normal es `mio`, y su periodo es PERIODO.
    expect(guardado.periodo_sugerido.inicio).toBe('2026-08-16');
  });
});

describe('CarteraProvider · quién ve los clientes de demostración', () => {
  it('una cuenta de desarrollo los ve todos', async () => {
    montar();
    await waitFor(() =>
      expect(screen.getByTestId('nombres').textContent).toBe('demo,cafeteria,taller,mio'),
    );
  });

  it('una cuenta NORMAL no ve ninguno, aunque estén en su Firestore', async () => {
    // El caso que importa: la siembra ya escrita de G-03 o de la demo.
    vi.stubEnv('DEV', false);
    montar();

    await waitFor(() => expect(screen.getByTestId('nombres').textContent).toBe('mio'));
  });

  it('y tampoco por URL: `clientePorId` los oculta igual', async () => {
    // Si la ficha resolviera un cliente que la lista oculta, se podría entrar a
    // su nómina tecleando la URL y el filtro sería decorativo.
    vi.stubEnv('DEV', false);
    montar();

    await waitFor(() => expect(screen.getByTestId('mio-por-id').textContent).toBe('sí'));
    expect(screen.getByTestId('demo-por-id').textContent).toBe('no');
  });

  it('el cliente propio del contador NUNCA se filtra', async () => {
    // La mitad simétrica: un filtro demasiado ancho le escondería su cartera.
    vi.stubEnv('DEV', false);
    montar();
    await waitFor(() => expect(screen.getByTestId('nombres').textContent).toContain('mio'));
  });
});
