/**
 * Los dos motivos NUEVOS por los que el paso 2 se bloquea. (R-06)
 *
 * POR QUÉ ESTE ARCHIVO EXISTE, Y ES INCÓMODO DECIRLO
 * --------------------------------------------------
 * El bloqueo que un revisor levantó contra R-06 no era "falta un aviso": era
 * que **el código afirmaba una mitigación que no existía** — `CarteraContext`
 * decía "la pantalla de nómina avisa cuando el periodo llega vacío" y la
 * pantalla no avisaba.
 *
 * Se construyó el aviso, y `CarteraContext` volvió a apoyarse en él por
 * escrito. Sin estos tests, dos mutaciones de una palabra
 * —quitar `&& !sinPeriodo` o `&& !n.ajenoALaCartera` de `estadoPaso2`— dejaban
 * esa afirmación falsa otra vez, con las 451 pruebas en verde. Es exactamente
 * la misma forma del defecto, un ciclo más tarde.
 *
 * LO QUE SE PRUEBA ES LA PANTALLA, NO EL HOOK
 * -------------------------------------------
 * `useNominaCliente.guardas.test.ts` ya fija que los HANDLERS no cierran ni
 * calculan para un cliente ajeno — la protección fiscal. Esto es lo otro: que
 * el operador vea POR QUÉ, en vez de un botón muerto y ni una palabra.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import type { ClienteCartera } from '../services/carteraApi';

const PERIODO = { inicio: '2026-08-16', fin: '2026-08-31', fecha_pago: '2026-08-31' };

function cliente(over: Partial<ClienteCartera> = {}): ClienteCartera {
  return {
    id: 'mio', nombre: 'Cliente Propio', giro: 'G', origen: 'propio',
    prima_riesgo: '0.005', clase_riesgo: null, clave_periodicidad: '04', zona: 'general',
    periodo_sugerido: PERIODO,
    empleados: [{
      empleado_no: 'E-01', nombre: 'PERSONA UNA', puesto: '', salario_diario: '520.00',
      salario_diario_integrado: '548.50', zona: 'general', fecha_alta: null,
      tipo_contrato: 'indeterminado',
      prestaciones: { dias_aguinaldo: 15, dias_vacaciones: 0, prima_vacacional: '0.25' },
      nss: '', employee_no: 'E-01', enrolamiento: 'enrolado',
    }],
    ...over,
  };
}

const enCartera = { actual: null as ClienteCartera | null };

vi.mock('../context/carteraStore', async () => {
  const { carteraDePrueba } = await import('../test/carteraDePrueba');
  return {
    useCartera: () =>
      carteraDePrueba({
        clientes: enCartera.actual ? [enCartera.actual] : [],
        origen: 'firestore',
        soloLectura: false,
        clientePorId: (id: string) =>
          enCartera.actual && enCartera.actual.id === id ? enCartera.actual : null,
      }),
  };
});

vi.mock('../context/clienteActivoStore', () => ({
  useClienteActivo: () => ({
    clientes: [], clienteId: 'mio', cliente: null, loading: false, error: null,
    setClienteId: vi.fn(), recargar: vi.fn(),
  }),
}));

const { default: NominaClientePage } = await import('./NominaClientePage');

/**
 * La ficha del backend responde 404: es el caso REAL de un cliente capturado
 * por el contador, que `GET /despacho/clientes/{id}` no conoce. Así el periodo
 * sale de la cartera —o no sale— y es lo que se quiere medir.
 */
function stubApi(periodoDelBackend: boolean) {
  vi.stubGlobal('fetch', vi.fn((url: string) => {
    const responder = (cuerpo: unknown) =>
      Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(cuerpo) });
    if (url.includes('despacho/clientes')) {
      if (!periodoDelBackend) {
        return Promise.resolve({
          ok: false, status: 404,
          json: () => Promise.resolve({ exito: false, error: 'no está en la cartera de la demo' }),
        });
      }
      return responder({ ...cliente(), num_empleados: 1, fecha_referencia: '2026-09-01', empleados: [] });
    }
    return responder({ eventos: [] });
  }));
}

function pintar(id = 'mio') {
  return render(
    <MemoryRouter initialEntries={[`/app/clientes/${id}/nomina`]}>
      <Routes>
        <Route path="/app/clientes/:id/nomina" element={<NominaClientePage />} />
      </Routes>
    </MemoryRouter>,
  );
}

const botonCerrar = () => screen.getByRole('button', { name: /Cerrar quincena/ }) as HTMLButtonElement;

beforeEach(() => { enCartera.actual = cliente(); });
afterEach(() => { vi.unstubAllGlobals(); cleanup(); });

describe('paso 2 · el cliente no es de esta cuenta', () => {
  it('lo DICE, en vez de dejar un botón encendido que no hace nada', async () => {
    // El defecto que esto cierra es el que este mismo archivo critica de la
    // corrida G: el botón quedaba en color, se podía clickear, y no pasaba nada.
    enCartera.actual = null;
    stubApi(true);
    pintar('demo');

    // PRIMERO se espera a que la ficha del backend haya cargado. Sin esto el
    // test pasaba por la razón equivocada: con `cliente` todavía en `null` el
    // paso está bloqueado de todos modos, y quitar la guarda de
    // `estadoPaso2` no lo rompía. El caso que importa es justo el contrario —
    // el cliente `demo` SÍ existe en el backend, así que su ficha carga y el
    // paso se vería "disponible" si nada más lo bloqueara.
    await waitFor(() => expect(screen.getByText(/Nómina de/)).toBeTruthy());

    expect(screen.getByText(/no está en la cartera de tu cuenta/)).toBeTruthy();
    expect(botonCerrar().disabled).toBe(true);
  });

  it('con el cliente EN la cartera, el paso 2 está disponible', async () => {
    // La mitad simétrica: sin ella, un bloqueo permanente pasaría el test de
    // arriba y dejaría la nómina inservible para todos.
    stubApi(true);
    pintar();

    await waitFor(() => expect(botonCerrar().disabled).toBe(false));
    expect(screen.queryByText(/no está en la cartera de tu cuenta/)).toBeNull();
  });
});

describe('paso 2 · el cliente todavía no tiene periodo sugerido', () => {
  it('pide capturar las fechas, en vez de dejar dos campos vacíos sin motivo', async () => {
    /**
     * Le pasa al PRIMER cliente de una cuenta nueva cuando el backend no
     * respondió al leer la cartera. Antes de R-06 este camino era inalcanzable
     * —el fallback garantizaba que siempre hubiera un cliente del que heredar—
     * y ahora es el default de toda cuenta que empieza.
     */
    enCartera.actual = cliente({ periodo_sugerido: { inicio: '', fin: '', fecha_pago: null } });
    stubApi(false); // el backend no conoce a este cliente: 404
    pintar();

    await waitFor(() =>
      expect(screen.getByText(/todavía no tiene un periodo sugerido/)).toBeTruthy(),
    );
    expect(botonCerrar().disabled).toBe(true);
  });

  it('y NO esconde los campos de fecha: el operador tiene que poder llenarlos', async () => {
    // `PasoNomina` renderiza `{children}` sin condición, así que bloquear el
    // paso no encierra al operador. Es lo que hace que el aviso sea accionable
    // en vez de un callejón, y por eso se fija.
    enCartera.actual = cliente({ periodo_sugerido: { inicio: '', fin: '', fecha_pago: null } });
    stubApi(false);
    pintar();

    await waitFor(() => expect(screen.getByText(/periodo sugerido/)).toBeTruthy());
    expect(screen.getByLabelText(/Inicio del periodo/)).toBeTruthy();
    expect(screen.getByLabelText(/Fin del periodo/)).toBeTruthy();
  });
});
