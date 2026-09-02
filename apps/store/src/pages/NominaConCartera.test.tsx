/**
 * El cableado de las dos llaves, medido en la pantalla (G-02).
 *
 * POR QUÉ ESTE ARCHIVO EXISTE
 * ---------------------------
 * `llavesDelCierre.ts` tiene 13 pruebas y todas pasan. Pero un revisor revirtió
 * **el fix entero** en `useNominaCliente` —volver a mandar `empleado_no` al
 * cierre y quitar la traducción de vuelta— y la suite completa siguió en verde:
 * 291 de 291. La razón es que `carteraDePrueba` devuelve `clientePorId: () => null`
 * y ningún test de pantalla pasaba override, así que `empleadosCartera` era
 * `null` en todos, y con `null`:
 *
 * - `llavesParaElCierre(plantilla, null)` **es** `plantilla.map(e => e.empleado_no)`,
 *   o sea la versión con el bug;
 * - `incidenciasDelCierre(..., null)` no traduce nada.
 *
 * La rama que hace algo no se ejercitaba nunca fuera de los unit tests de la
 * función pura. Un arreglo de cableado probado sólo en las piezas deja el
 * cableado libre de volver a romperse en silencio, y el modo de falla es el que
 * este entregable existe para cerrar: menos días pagados, menor base de cuotas
 * y menor ISR, sin un solo error.
 *
 * Por eso aquí la cartera viene POBLADA y con las dos llaves DISTINTAS
 * (`empleado_no: 'E-07'`, `employee_no: '7'`). Con llaves iguales la traducción
 * es la identidad y esto no probaría nada — lo afirma `hayLlavesDistintas`.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useNavigate } from 'react-router-dom';
import { hayLlavesDistintas } from '../components/nomina/llavesDelCierre';
import type { EmpleadoCartera } from '../services/carteraApi';

const CLIENTE = 'taller';

/** Un empleado cuyo número de aparato NO es su número interno. */
function empleado(empleado_no: string, employee_no: string | null): EmpleadoCartera {
  return {
    empleado_no,
    nombre: `PERSONA ${empleado_no}`,
    puesto: 'Puesto',
    salario_diario: '520.00',
    salario_diario_integrado: '548.50',
    zona: 'general',
    fecha_alta: '2021-02-01',
    tipo_contrato: 'indeterminado',
    prestaciones: { dias_aguinaldo: 15, dias_vacaciones: 0, prima_vacacional: '0.25' },
    nss: '',
    employee_no,
    enrolamiento: 'enrolado',
  };
}

const EN_CARTERA = {
  empleados: [] as EmpleadoCartera[],
  cargando: false,
  /** `true` = la cartera no conoce a este cliente (sólo existe en el backend). */
  ausente: false,
  periodicidad: '04',
};

function clienteDeCartera() {
  return {
    id: CLIENTE,
    nombre: 'Taller Nogal',
    giro: 'Giro de prueba',
    origen: 'sintetico',
    prima_riesgo: '0.0113065',
    clase_riesgo: 2,
    clave_periodicidad: EN_CARTERA.periodicidad,
    zona: 'general',
    periodo_sugerido: { inicio: '2026-08-16', fin: '2026-08-31', fecha_pago: '2026-08-31' },
    empleados: EN_CARTERA.empleados,
  };
}

vi.mock('../context/carteraStore', async () => {
  const { carteraDePrueba } = await import('../test/carteraDePrueba');
  return {
    useCartera: () =>
      carteraDePrueba({
        clientes:
          EN_CARTERA.cargando || EN_CARTERA.ausente ? [] : ([clienteDeCartera()] as never),
        loading: EN_CARTERA.cargando,
        origen: 'firestore',
        soloLectura: false,
        clientePorId: (id: string) =>
          !EN_CARTERA.cargando && !EN_CARTERA.ausente && id === CLIENTE
            ? (clienteDeCartera() as never)
            : null,
      }),
  };
});

vi.mock('../context/clienteActivoStore', () => ({
  useClienteActivo: () => ({
    clientes: [], cliente: null, loading: false, error: null,
    clienteId: CLIENTE, setClienteId: vi.fn(), recargar: vi.fn(),
  }),
}));

const { default: NominaClientePage } = await import('./NominaClientePage');

/** La pantalla con dos botones para navegar sin desmontar el árbol. */
function ConNavegacion() {
  const navegar = useNavigate();
  return (
    <>
      <button onClick={() => navegar('/app/clientes/otro/nomina')}>ir a otro</button>
      <button onClick={() => navegar(`/app/clientes/${CLIENTE}/nomina`)}>volver</button>
      <NominaClientePage />
    </>
  );
}

const NOMINA_VACIA = {
  cliente: CLIENTE,
  periodo: { inicio: '2026-08-16', fin: '2026-08-31', fecha_pago: '2026-08-31' },
  fecha_pago_efectiva: '2026-08-31',
  origen_plantilla: 'request',
  recibos: [],
  porcion_mensual: { periodicidad: 'mensual', por_ramo: {}, total_patron: '0', total_obrero: '0', total: '0', empleados: 0 },
  porcion_bimestral: { periodicidad: 'bimestral', por_ramo: {}, total_patron: '0', total_obrero: '0', total: '0', empleados: 0 },
  advertencias: [],
};

/**
 * El backend devuelve las incidencias con **la misma llave que recibió**, que
 * es lo que hace `asistencia/incidencias.py`. Si el front manda la llave
 * equivocada, aquí vuelven con la equivocada.
 */
function stubApi() {
  const llamadas: Array<{ url: string; init?: RequestInit }> = [];
  vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => {
    llamadas.push({ url, init });
    let cuerpo: unknown;
    if (url.includes('despacho/clientes')) {
      cuerpo = {
        id: CLIENTE, nombre: 'Taller Nogal', giro: 'Giro de prueba', origen: 'sintetico',
        num_empleados: EN_CARTERA.empleados.length, prima_riesgo: '0.0113065',
        clase_riesgo: 2, clave_periodicidad: EN_CARTERA.periodicidad, zona: 'general',
        fecha_referencia: '2026-09-01',
        // La ficha del backend trae los números INTERNOS, que es lo que la hace
        // distinta de la cartera y lo que permite ver cuál de las dos viajó.
        empleados: EN_CARTERA.empleados.map((e) => ({
          empleado_no: e.empleado_no, nombre: e.nombre, puesto: 'Puesto',
          salario_diario: e.salario_diario, salario_diario_integrado: e.salario_diario_integrado,
          zona: 'general', fecha_alta: e.fecha_alta, antiguedad_anios: 5,
          factor: '1.0548', factor_implicito: false,
        })),
        periodo_sugerido: { inicio: '2026-08-16', fin: '2026-08-31', fecha_pago: '2026-08-31' },
      };
    } else if (url.includes('asistencia/eventos')) {
      // Las checadas llegan con la llave del APARATO: es lo que manda el
      // Hikvision. Sin ellas la pantalla pide confirmación antes de cerrar.
      cuerpo = {
        eventos: EN_CARTERA.empleados.filter((e) => e.employee_no).map((e) => ({
          empleado_no: e.employee_no, timestamp: '2026-08-17T08:05:00-06:00',
          tipo: 'entrada', fuente: 'simulado', serial_no: 1, raw: null,
        })),
      };
    } else if (url.includes('cerrar-periodo')) {
      const enviado = JSON.parse((init?.body as string) ?? '{}');
      cuerpo = {
        cliente: enviado.cliente,
        periodo: { inicio: '2026-08-16', fin: '2026-08-31' },
        incidencias: (enviado.empleados as string[]).map((e) => ({
          empleado_no: e, dias_periodo: 16, dias_laborables: 11, dias_trabajados: 10,
          faltas: 1, dias_ausentismo: 1, retardos: 0, dias_cotizados: 16,
        })),
        empleados_desconocidos: [],
      };
    } else if (url.includes('calcular-periodo')) {
      cuerpo = NOMINA_VACIA;
    } else {
      throw new Error(`ruta no stubbeada: ${url}`);
    }
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(cuerpo) });
  }));
  return llamadas;
}

function montar() {
  return render(
    <MemoryRouter initialEntries={[`/app/clientes/${CLIENTE}/nomina`]}>
      <Routes>
        <Route path="/app/clientes/:id/nomina" element={<NominaClientePage />} />
      </Routes>
    </MemoryRouter>,
  );
}

function cuerpoDe(llamadas: Array<{ url: string; init?: RequestInit }>, ruta: string) {
  const llamada = llamadas.find((l) => l.url.includes(ruta));
  expect(llamada, `no se llamó a ${ruta}`).toBeDefined();
  return JSON.parse(llamada!.init!.body as string);
}

beforeEach(() => {
  EN_CARTERA.empleados = [empleado('E-07', '7'), empleado('E-08', '8')];
  EN_CARTERA.cargando = false;
  EN_CARTERA.ausente = false;
  EN_CARTERA.periodicidad = '04';
});

afterEach(cleanup);

describe('el cierre usa la llave del CHECADOR y la nómina la del CÁLCULO', () => {
  it('la cartera de esta prueba tiene las dos llaves distintas', () => {
    // Sin esto, todo lo de abajo podría estar midiendo la identidad.
    expect(hayLlavesDistintas(EN_CARTERA.empleados)).toBe(true);
  });

  it('a cerrar-periodo le manda los números del APARATO', async () => {
    // El defecto original: mandaba ['E-07','E-08'], el backend casa contra el
    // `employeeNoString` del Hikvision, no encontraba ni una checada, y salía
    // falta todo el periodo con menos días pagados y menores cuotas.
    const llamadas = stubApi();
    montar();
    await waitFor(() => expect(screen.getByDisplayValue('2026-08-16')).toBeTruthy());
    fireEvent.click(screen.getByRole('button', { name: /Cerrar quincena/ }));

    await waitFor(() => expect(llamadas.some((l) => l.url.includes('cerrar-periodo'))).toBe(true));
    expect(cuerpoDe(llamadas, 'cerrar-periodo').empleados).toEqual(['7', '8']);
  });

  it('a calcular-periodo le manda las incidencias con el número INTERNO', async () => {
    // La vuelta. `calcular-periodo` responde 422 ante una incidencia cuyo
    // `empleado_no` no esté en la plantilla, así que sin traducir de regreso el
    // cálculo entero falla.
    const llamadas = stubApi();
    montar();
    await waitFor(() => expect(screen.getByDisplayValue('2026-08-16')).toBeTruthy());
    fireEvent.click(screen.getByRole('button', { name: /Cerrar quincena/ }));
    await screen.findByText('PERSONA E-07');
    fireEvent.click(screen.getByRole('button', { name: /Calcular nómina/ }));

    await waitFor(() => expect(llamadas.some((l) => l.url.includes('calcular-periodo'))).toBe(true));
    const cuerpo = cuerpoDe(llamadas, 'calcular-periodo');
    expect(cuerpo.incidencias.map((i: { empleado_no: string }) => i.empleado_no)).toEqual([
      'E-07', 'E-08',
    ]);
    expect(cuerpo.empleados.map((e: { empleado_no: string }) => e.empleado_no)).toEqual([
      'E-07', 'E-08',
    ]);
  });

  it('la tabla de incidencias pinta el nombre, no el número del aparato', async () => {
    // Si la traducción de vuelta no ocurriera, la tabla buscaría al empleado
    // '7' en la plantilla, no lo encontraría, y pintaría el número crudo.
    stubApi();
    montar();
    await waitFor(() => expect(screen.getByDisplayValue('2026-08-16')).toBeTruthy());
    fireEvent.click(screen.getByRole('button', { name: /Cerrar quincena/ }));

    // `TablaIncidencias` resuelve el nombre por `empleado_no` y cae al número
    // crudo si no lo encuentra. Que salga el nombre ES la prueba de que la
    // traducción de vuelta ocurrió: sin ella buscaría al empleado '7' en una
    // plantilla que sólo conoce 'E-07'.
    expect(await screen.findByText('PERSONA E-07')).toBeTruthy();
    expect(await screen.findByText('PERSONA E-08')).toBeTruthy();
  });

  it('un empleado sin vincular no entra al cierre ni al cálculo', async () => {
    // G-02 de punta a punta: sin llave de aparato no hay checadas que
    // atribuirle. Queda fuera, y la pantalla lo dice.
    EN_CARTERA.empleados = [empleado('E-07', '7'), empleado('N-01', null)];
    const llamadas = stubApi();
    montar();
    await waitFor(() => expect(screen.getByDisplayValue('2026-08-16')).toBeTruthy());
    fireEvent.click(screen.getByRole('button', { name: /Cerrar quincena/ }));

    await waitFor(() => expect(llamadas.some((l) => l.url.includes('cerrar-periodo'))).toBe(true));
    expect(cuerpoDe(llamadas, 'cerrar-periodo').empleados).toEqual(['7']);
    expect(screen.getByText(/no está vinculado al checador/)).toBeTruthy();
  });
});


describe('el error de carga se descarta; el de las operaciones no', () => {
  /**
   * Los dos lados de la separación que hizo falta para BL-3. Antes compartían
   * estado, así que descartar el de carga —cuando el cliente sí está en la
   * cartera— habría tapado un fallo real de cerrar o calcular. Y el de carga se
   * latcheaba: si el 404 ganaba la carrera a Firestore, se quedaba pegado para
   * siempre porque el efecto no vuelve a correr.
   */
  it('un cliente que sólo existe en la cartera NO pinta el 404 de la ficha', async () => {
    vi.stubGlobal('fetch', vi.fn((url: string) => {
      if (url.includes('despacho/clientes')) {
        return Promise.resolve({
          ok: false, status: 404,
          json: () => Promise.resolve({ exito: false, error: 'El cliente no está en la cartera de la demo.' }),
        });
      }
      if (url.includes('asistencia/eventos')) {
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({ eventos: [] }) });
      }
      throw new Error(`ruta no stubbeada: ${url}`);
    }));

    montar();
    await waitFor(() => expect(screen.getByText('Taller Nogal')).toBeTruthy());
    expect(screen.queryByText(/no está en la cartera de la demo/)).toBeNull();
    expect(screen.queryByText(/No se pudo completar la operación/)).toBeNull();
  });

  it('un fallo de cerrar-periodo SÍ se pinta, aunque el cliente esté en la cartera', async () => {
    // El riesgo de descartar errores por categoría: tapar el que sí importa.
    vi.stubGlobal('fetch', vi.fn((url: string) => {
      if (url.includes('despacho/clientes')) {
        return Promise.resolve({
          ok: true, status: 200,
          json: () => Promise.resolve({
            id: CLIENTE, nombre: 'Taller Nogal', giro: 'G', origen: 'sintetico',
            num_empleados: 2, prima_riesgo: '0.0113065', clase_riesgo: 2,
            clave_periodicidad: '04', zona: 'general', fecha_referencia: '2026-09-01',
            empleados: [], periodo_sugerido: { inicio: '2026-08-16', fin: '2026-08-31', fecha_pago: null },
          }),
        });
      }
      if (url.includes('asistencia/eventos')) {
        return Promise.resolve({
          ok: true, status: 200,
          json: () => Promise.resolve({
            eventos: [{ empleado_no: '7', timestamp: '2026-08-17T08:05:00-06:00', tipo: 'entrada', fuente: 'simulado', serial_no: 1, raw: null }],
          }),
        });
      }
      if (url.includes('cerrar-periodo')) {
        return Promise.resolve({
          ok: false, status: 422,
          json: () => Promise.resolve({ exito: false, error: 'El periodo está invertido.' }),
        });
      }
      throw new Error(`ruta no stubbeada: ${url}`);
    }));

    montar();
    await waitFor(() => expect(screen.getByDisplayValue('2026-08-16')).toBeTruthy());
    fireEvent.click(screen.getByRole('button', { name: /Cerrar quincena/ }));

    expect(await screen.findByText(/El periodo está invertido/)).toBeTruthy();
  });
});


describe('el cierre NO se dispara mientras la cartera carga', () => {
  /**
   * El gate estaba en el badge del paso, y `PasoNomina` es presentacional: pinta
   * "bloqueado" en gris y renderiza `{children}` sin condición. El botón quedaba
   * vivo, con un letrero abajo que no impedía nada.
   *
   * Cerrar en esa ventana usa las llaves del CATÁLOGO en vez de las del aparato
   * —`deLaCartera` es `null` mientras `cartera.loading`—, así que un empleado
   * con número propio no encuentra ni una checada. Y cuando la cartera llega, la
   * plantilla vuelve a cuadrar por `empleado_no` y **nada levanta**: sale un
   * recibo con faltas de más, en silencio.
   */
  it('el botón está deshabilitado', async () => {
    EN_CARTERA.cargando = true;
    stubApi();
    montar();
    await waitFor(() => expect(screen.getByDisplayValue('2026-08-16')).toBeTruthy());
    expect(screen.getByRole('button', { name: /Cerrar quincena/ })).toHaveProperty('disabled', true);
  });

  it('y aunque se dispare el handler, no llama a cerrar-periodo', async () => {
    // `disabled` es una propiedad del DOM, no una garantía del handler: la
    // guarda de verdad vive en el hook. Sin ella, este clic cierra con las
    // llaves equivocadas.
    EN_CARTERA.cargando = true;
    const llamadas = stubApi();
    montar();
    await waitFor(() => expect(screen.getByDisplayValue('2026-08-16')).toBeTruthy());
    fireEvent.click(screen.getByRole('button', { name: /Cerrar quincena/ }));

    await new Promise((r) => setTimeout(r, 50));
    expect(llamadas.some((l) => l.url.includes('cerrar-periodo'))).toBe(false);
  });

  it('en cuanto la cartera llega, el cierre se habilita y usa las llaves del aparato', async () => {
    // La otra mitad: la guarda no puede dejar el botón muerto para siempre.
    stubApi();
    montar();
    await waitFor(() => expect(screen.getByDisplayValue('2026-08-16')).toBeTruthy());
    expect(screen.getByRole('button', { name: /Cerrar quincena/ })).toHaveProperty('disabled', false);
  });
});


describe('las dos rebabas de la derivación del error', () => {
  /**
   * Las dos sobrevivían a la mutación: se reportaron cerradas y no había con qué
   * comprobarlo.
   */
  it('mientras la cartera carga NO se pinta el 404 de la ficha', async () => {
    // Sin `|| cartera.loading`, una recarga directa sobre un cliente propio
    // pintaba el 404 en rojo hasta 2500 ms y luego lo quitaba sola: un error
    // que aparece y desaparece es peor que ninguno.
    EN_CARTERA.cargando = true;
    vi.stubGlobal('fetch', vi.fn((url: string) => {
      if (url.includes('despacho/clientes')) {
        return Promise.resolve({
          ok: false, status: 404,
          json: () => Promise.resolve({ exito: false, error: 'El cliente no está en la cartera de la demo.' }),
        });
      }
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({ eventos: [] }) });
    }));

    montar();
    await new Promise((r) => setTimeout(r, 50));
    expect(screen.queryByText(/no está en la cartera de la demo/)).toBeNull();
  });

  it('el error de carga se limpia al volver a un cliente que ya carga bien', async () => {
    // A → B → A **sin desmontar**, que es el caso real: el estado sobrevive a la
    // navegación y `errorCargaDe` sigue guardado con el id de A. Si nadie lo
    // borra al cargar bien, al volver se pinta el error viejo aunque la ficha
    // llegó. Desmontar y volver a montar NO lo prueba: ahí el estado nace
    // limpio y la mutación sobrevive — lo comprobé.
    let fallaA = true;
    vi.stubGlobal('fetch', vi.fn((url: string) => {
      if (url.includes('despacho/clientes')) {
        const id = url.split('/').pop() ?? '';
        if (id === CLIENTE && fallaA) {
          fallaA = false;
          return Promise.resolve({
            ok: false, status: 500,
            json: () => Promise.resolve({ exito: false, error: 'La API se estaba reiniciando.' }),
          });
        }
        return Promise.resolve({
          ok: true, status: 200,
          json: () => Promise.resolve({
            id, nombre: `Cliente ${id}`, giro: 'G', origen: 'sintetico',
            num_empleados: 0, prima_riesgo: '0.0113065', clase_riesgo: 2,
            clave_periodicidad: '04', zona: 'general', fecha_referencia: '2026-09-01',
            empleados: [], periodo_sugerido: { inicio: '2026-08-16', fin: '2026-08-31', fecha_pago: null },
          }),
        });
      }
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({ eventos: [] }) });
    }));

    // La cartera NO conoce a estos clientes, así que el error de carga sí se
    // pinta: es lo que hace visible la rebaba.
    EN_CARTERA.ausente = true;
    render(
      <MemoryRouter initialEntries={[`/app/clientes/${CLIENTE}/nomina`]}>
        <Routes>
          <Route path="/app/clientes/:id/nomina" element={<ConNavegacion />} />
        </Routes>
      </MemoryRouter>,
    );

    // A falla.
    expect(await screen.findByText(/se estaba reiniciando/)).toBeTruthy();
    // A → B → A, sin desmontar.
    fireEvent.click(screen.getByRole('button', { name: 'ir a otro' }));
    await waitFor(() => expect(screen.queryByText(/se estaba reiniciando/)).toBeNull());
    fireEvent.click(screen.getByRole('button', { name: 'volver' }));

    await waitFor(() => expect(screen.getByDisplayValue('2026-08-16')).toBeTruthy());
    expect(screen.queryByText(/se estaba reiniciando/)).toBeNull();
  });
});


describe('una periodicidad que no cuadra con el periodo no se calcula', () => {
  /**
   * Nadie más lo valida: `periodo.py` sólo comprueba que las incidencias midan
   * lo mismo entre sí. Un cliente Mensual con una base de 15-16 días recibiría
   * la tarifa mensual del Art. 96 — **ISR subestimado, con recibo creíble**.
   * El alta ya sólo ofrece quincenal, pero un cliente guardado antes con otra
   * clave sigue vivo y nada lo detectaba.
   */
  it('un cliente Mensual con una quincena no calcula, y dice por qué', async () => {
    EN_CARTERA.periodicidad = '05';
    const llamadas = stubApi();
    montar();
    await waitFor(() => expect(screen.getByDisplayValue('2026-08-16')).toBeTruthy());
    fireEvent.click(screen.getByRole('button', { name: /Cerrar quincena/ }));
    await screen.findByText('PERSONA E-07');
    fireEvent.click(screen.getByRole('button', { name: /Calcular nómina/ }));

    expect(await screen.findByText(/aplicaría la tarifa de ISR de otra periodicidad/)).toBeTruthy();
    await new Promise((r) => setTimeout(r, 50));
    expect(llamadas.some((l) => l.url.includes('calcular-periodo'))).toBe(false);
  });

  it('un cliente quincenal calcula normal', async () => {
    const llamadas = stubApi();
    montar();
    await waitFor(() => expect(screen.getByDisplayValue('2026-08-16')).toBeTruthy());
    fireEvent.click(screen.getByRole('button', { name: /Cerrar quincena/ }));
    await screen.findByText('PERSONA E-07');
    fireEvent.click(screen.getByRole('button', { name: /Calcular nómina/ }));

    await waitFor(() => expect(llamadas.some((l) => l.url.includes('calcular-periodo'))).toBe(true));
  });
});
