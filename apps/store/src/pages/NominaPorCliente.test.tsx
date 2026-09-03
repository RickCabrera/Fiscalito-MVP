/**
 * La nómina dentro del cliente (E-03).
 *
 * TRES INVARIANTES, y los tres son "que la pantalla no afirme un cliente y
 * enseñe otro" —el bloqueante de E-02— entrando por puertas distintas:
 *
 * 1. **La ruta es la fuente de verdad.** Entrar por URL con otro cliente
 *    guardado en `localStorage` tiene que sincronizar el contexto a la ruta, no
 *    al revés.
 * 2. **El request lleva el cliente de la ruta y SUS empleados.** Con la
 *    plantilla viajando en el body, "la pantalla afirma un cliente y calcula
 *    otro" ahora cabe en un JSON.
 * 3. **Cambiar de cliente no deja resultados del anterior en pantalla.**
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useNavigate } from 'react-router-dom';
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

// R-06: la plantilla sale SÓLO de la cartera del usuario. El doble vacío que
// tenía este archivo hacía que `useNominaCliente` cayera a los empleados de la
// ficha del backend, y ese fallback ya no existe: una cartera que no contiene al
// cliente significa "no es tuyo" y la pantalla se niega a calcular.
//
// El doble modela lo que pasa después de R-06 —el contador abre un cliente de su
// cartera— y **espeja los empleados de `ficha(id)`**, con la misma llave
// `${id}-1` / `${id}-2`, para que la plantilla que sale sea idéntica y estas
// pruebas sigan midiendo lo suyo: que el request lleve el cliente de la ruta y
// SUS empleados, y que cambiar de cliente no arrastre nada del anterior.
vi.mock('../context/carteraStore', async () => {
  const { carteraDePrueba } = await import('../test/carteraDePrueba');
  const empleado = (no: string, nombre: string, sd: string, sdi: string) => ({
    empleado_no: no, nombre, puesto: 'Puesto', salario_diario: sd,
    salario_diario_integrado: sdi, zona: 'general', fecha_alta: '2021-02-01',
    tipo_contrato: 'indeterminado' as const,
    prestaciones: { dias_aguinaldo: 15, dias_vacaciones: 0, prima_vacacional: '0.25' },
    nss: '', employee_no: no, enrolamiento: 'enrolado' as const,
  });
  const cliente = (id: string) => ({
    id, nombre: id, giro: 'Giro de prueba', origen: 'sintetico',
    prima_riesgo: '0.0113065', clase_riesgo: 2, clave_periodicidad: '04',
    zona: 'general',
    periodo_sugerido: { inicio: '2026-08-16', fin: '2026-08-31', fecha_pago: '2026-08-31' },
    empleados: [
      empleado(`${id}-1`, 'PERSONA UNA', '520.00', '548.50'),
      empleado(`${id}-2`, 'PERSONA DOS', '445.00', '467.56'),
    ],
  });
  return {
    useCartera: () =>
      carteraDePrueba({
        origen: 'firestore',
        soloLectura: false,
        // 'fantasma' NO está en la cartera a propósito: es el único id con el que
    // se puede ejercitar el camino del 404 que la cartera no rescata, y desde
    // R-06 también el de "este cliente no es de tu cuenta".
    clientePorId: (id: string) => (id === 'fantasma' ? null : cliente(id)),
      }),
  };
});


const setClienteId = vi.fn();
const estadoContexto = { clienteId: 'taller' as string | null };

vi.mock('../context/clienteActivoStore', () => ({
  useClienteActivo: () => ({
    clientes: [], cliente: null, loading: false, error: null,
    clienteId: estadoContexto.clienteId,
    setClienteId, recargar: vi.fn(),
  }),
}));

const { default: NominaClientePage } = await import('./NominaClientePage');

function ficha(id: string, nombre: string, origen = 'sintetico') {
  return {
    id, nombre, origen,
    giro: 'Giro de prueba',
    num_empleados: 2,
    prima_riesgo: '0.0113065',
    clase_riesgo: 2,
    clave_periodicidad: '04',
    zona: 'general',
    fecha_referencia: '2026-09-01',
    empleados: [
      { empleado_no: `${id}-1`, nombre: 'PERSONA UNA', puesto: 'Puesto', salario_diario: '520.00', salario_diario_integrado: '548.50', zona: 'general', fecha_alta: '2021-02-01', antiguedad_anios: 5, factor: '1.0548', factor_implicito: false },
      { empleado_no: `${id}-2`, nombre: 'PERSONA DOS', puesto: 'Puesto', salario_diario: '445.00', salario_diario_integrado: '467.56', zona: 'general', fecha_alta: '2024-06-10', antiguedad_anios: 2, factor: '1.0507', factor_implicito: false },
    ],
    periodo_sugerido: { inicio: '2026-08-16', fin: '2026-08-31', fecha_pago: '2026-08-31' },
  };
}

function incidencia(empleado_no: string, dias_trabajados: number) {
  return {
    empleado_no, dias_periodo: 16, dias_laborables: 11, dias_trabajados,
    faltas: 11 - dias_trabajados, dias_ausentismo: 11 - dias_trabajados,
    retardos: 0, dias_cotizados: 16,
  };
}

const NOMINA_VACIA = {
  cliente: 'x',
  periodo: { inicio: '2026-08-16', fin: '2026-08-31', fecha_pago: '2026-08-31' },
  fecha_pago_efectiva: '2026-08-31',
  origen_plantilla: 'request',
  recibos: [],
  porcion_mensual: { periodicidad: 'mensual', por_ramo: {}, total_patron: '0', total_obrero: '0', total: '0', empleados: 0 },
  porcion_bimestral: { periodicidad: 'bimestral', por_ramo: {}, total_patron: '0', total_obrero: '0', total: '0', empleados: 0 },
  // O-04: los totales del MOTOR viajan en la respuesta.
  total_percepciones: '0.00',
  total_neto: '0.00',
  total_isr: '0.00',
  advertencias: [],
};

/** Router de fetch. `eventos` y `dias_trabajados` se parametrizan por test. */
function stubApi(opciones: {
  cliente?: string;
  nombre?: string;
  eventos?: unknown[];
  diasTrabajados?: number;
} = {}) {
  const {
    cliente = 'taller', nombre = 'Taller Nogal', eventos = [], diasTrabajados = 10,
  } = opciones;
  const llamadas: Array<{ url: string; init?: RequestInit }> = [];

  vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => {
    llamadas.push({ url, init });
    let cuerpo: unknown;
    if (url.includes('despacho/clientes')) {
      const id = url.split('/').pop() ?? cliente;
      cuerpo = ficha(id, id === cliente ? nombre : `Cliente ${id}`);
    } else if (url.includes('asistencia/eventos')) {
      cuerpo = { eventos };
    } else if (url.includes('cerrar-periodo')) {
      const cuerpoEnviado = JSON.parse((init?.body as string) ?? '{}');
      cuerpo = {
        cliente: cuerpoEnviado.cliente,
        periodo: { inicio: '2026-08-16', fin: '2026-08-31' },
        incidencias: (cuerpoEnviado.empleados as string[]).map((e) =>
          incidencia(e, diasTrabajados),
        ),
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

function montar(clienteId: string) {
  return render(
    <MemoryRouter initialEntries={[`/app/clientes/${clienteId}/nomina`]}>
      <Routes>
        <Route path="/app/clientes/:id/nomina" element={<NominaClientePage />} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  estadoContexto.clienteId = 'taller';
  setClienteId.mockClear();
});

afterEach(cleanup);

describe('la ruta manda sobre el contexto', () => {
  it('entrar por URL a otro cliente sincroniza el contexto a la ruta', async () => {
    // El escenario exacto: `taller` guardado de la sesión anterior y el usuario
    // entra a la nómina de `demo` por URL (o por la redirección de
    // /app/nomina-demo). Sin esto, el header diría Taller y la pantalla
    // calcularía demo.
    stubApi({ cliente: 'demo', nombre: 'Cliente Demo' });
    montar('demo');

    await waitFor(() => expect(setClienteId).toHaveBeenCalledWith('demo'));
  });

  it('no reescribe el contexto cuando ya coincide con la ruta', async () => {
    stubApi();
    montar('taller');

    await waitFor(() => expect(screen.getByDisplayValue('2026-08-16')).toBeTruthy());
    expect(setClienteId).not.toHaveBeenCalled();
  });
});

describe('el cliente de la ruta es el que se calcula', () => {
  it('pide la ficha, las checadas y el cierre del cliente de la ruta', async () => {
    const llamadas = stubApi({ cliente: 'cafeteria', nombre: 'Cafeteria La Estacion' });
    montar('cafeteria');

    await waitFor(() => expect(screen.getByDisplayValue('2026-08-16')).toBeTruthy());
    expect(llamadas.some((l) => l.url.includes('despacho/clientes/cafeteria'))).toBe(true);
    expect(llamadas.some((l) => l.url.includes('cliente=cafeteria'))).toBe(true);
    // Y nunca se pide nada del cliente `demo`, que era el default de D-07.
    expect(llamadas.some((l) => l.url.includes('cliente=demo'))).toBe(false);
  });

  it('el encabezado dice de quién es la nómina', async () => {
    stubApi({ cliente: 'cafeteria', nombre: 'Cafeteria La Estacion' });
    montar('cafeteria');

    expect(await screen.findByText(/Nómina de Cafeteria La Estacion/)).toBeTruthy();
  });

  it('manda al backend el cliente de la ruta y SUS empleados', async () => {
    /**
     * Con la plantilla viajando en el body, "afirmar un cliente y calcular
     * otro" cabe en un JSON: el guard del backend no puede atraparlo porque el
     * `cliente` y los `empleados` vendrían coherentes entre sí pero ser de otro.
     */
    // Con checadas en el panel: si estuviera vacío, cerrar pediría confirmación
    // y este test mediría otra cosa.
    const llamadas = stubApi({
      cliente: 'cafeteria',
      nombre: 'Cafeteria La Estacion',
      eventos: [{ empleado_no: 'cafeteria-1', timestamp: '2026-08-17T08:05:00-06:00', tipo: 'entrada', fuente: 'simulado', serial_no: 1, raw: null }],
    });
    montar('cafeteria');

    await waitFor(() => expect(screen.getByDisplayValue('2026-08-16')).toBeTruthy());
    fireEvent.click(screen.getByRole('button', { name: /Cerrar quincena/ }));
    await screen.findByText('PERSONA UNA');
    fireEvent.click(screen.getByRole('button', { name: /Calcular nómina/ }));

    await waitFor(() =>
      expect(llamadas.some((l) => l.url.includes('calcular-periodo'))).toBe(true),
    );
    const cuerpo = JSON.parse(
      llamadas.find((l) => l.url.includes('calcular-periodo'))!.init!.body as string,
    );
    expect(cuerpo.cliente).toBe('cafeteria');
    expect(cuerpo.empleados.map((e: { empleado_no: string }) => e.empleado_no)).toEqual([
      'cafeteria-1', 'cafeteria-2',
    ]);
    // Los cinco campos van tal cual de la ficha, sin remapear.
    expect(cuerpo.empleados[0]).toEqual({
      empleado_no: 'cafeteria-1',
      nombre: 'PERSONA UNA',
      salario_diario: '520.00',
      salario_diario_integrado: '548.50',
      zona: 'general',
    });
  });
});

describe('panel sin checadas', () => {
  it('avisa arriba cuando ningún empleado tiene una sola checada', async () => {
    /**
     * El motor NO devuelve ceros: paga los días no laborables del periodo, así
     * que la nómina sale completa y creíble con la ausencia escondida. La
     * advertencia del backend llega hasta abajo, bajo Cuotas por ramo, después
     * de que alguien ya leyó los totales.
     */
    stubApi({ diasTrabajados: 0 });
    montar('taller');

    await waitFor(() => expect(screen.getByDisplayValue('2026-08-16')).toBeTruthy());
    fireEvent.click(screen.getByRole('button', { name: /Cerrar quincena/ }));
    // Sin checadas en el periodo, primero pregunta.
    fireEvent.click(await screen.findByRole('button', { name: 'Cerrar de todos modos' }));

    const aviso = await screen.findByRole('alert');
    expect(aviso.textContent).toContain('Ningún empleado tiene checadas en este periodo');
    expect(aviso.textContent).toContain('no será de ceros');
  });

  it('pide confirmación antes de cerrar sin checadas, y cancelar no cierra', async () => {
    const llamadas = stubApi({ eventos: [] });
    montar('taller');

    await waitFor(() => expect(screen.getByDisplayValue('2026-08-16')).toBeTruthy());
    fireEvent.click(screen.getByRole('button', { name: /Cerrar quincena/ }));

    expect(await screen.findByRole('alertdialog')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Cancelar' }));
    expect(llamadas.some((l) => l.url.includes('cerrar-periodo'))).toBe(false);
  });

  it('con checadas en el periodo no pregunta nada', async () => {
    stubApi({
      eventos: [{ empleado_no: 'taller-1', timestamp: '2026-08-17T08:05:00-06:00', tipo: 'entrada', fuente: 'simulado', serial_no: 1, raw: null }],
    });
    montar('taller');

    await waitFor(() => expect(screen.getByDisplayValue('2026-08-16')).toBeTruthy());
    fireEvent.click(screen.getByRole('button', { name: /Cerrar quincena/ }));

    expect(screen.queryByRole('alertdialog')).toBeNull();
  });

  /**
   * EL MODO DE FALLA MÁS PROBABLE DE LA DEMO, y no es el panel vacío: sembrar
   * el día 15 y demostrar el 16 son dos quincenas distintas
   * (`demo_nomina.quincena()` lo advierte). `obtenerEventos` no manda `desde`,
   * así que el panel se ve LLENO, ninguna checada cae en el periodo, y sin esto
   * `cerrar_periodo` marcaría falta todos los días sin preguntar nada.
   */
  it('pregunta también cuando el panel está lleno pero de otra quincena', async () => {
    stubApi({
      eventos: [{ empleado_no: 'taller-1', timestamp: '2026-07-17T08:05:00-06:00', tipo: 'entrada', fuente: 'simulado', serial_no: 1, raw: null }],
    });
    montar('taller');

    await waitFor(() => expect(screen.getByDisplayValue('2026-08-16')).toBeTruthy());
    fireEvent.click(screen.getByRole('button', { name: /Cerrar quincena/ }));

    expect(await screen.findByRole('alertdialog')).toBeTruthy();
  });

  it('navegar a otro cliente no deja la ficha ni las checadas del anterior', async () => {
    /**
     * EL CASO QUE VALE EL ARCHIVO, y es la cuarta vez que este patrón aparece
     * en la épica. Entre el cambio de ruta y la llegada de la ficha nueva, un
     * `cliente` a secas conservaba el viejo: la URL y el selector dicen
     * "Taller", el encabezado seguía diciendo el nombre anterior y **los
     * botones seguían habilitados**, así que "Cerrar quincena" en esa ventana
     * cerraba el periodo del cliente que ya no se está viendo.
     *
     * Lo mismo con las checadas: el panel enseñaba las del cliente anterior
     * bajo el encabezado del nuevo.
     */
    // TODO lo del segundo cliente se queda colgado: es la ventana exacta en la
    // que la pantalla podría seguir enseñando lo del primero.
    const pendientes: Array<(v: unknown) => void> = [];
    vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => {
      const responder = (cuerpo: unknown) =>
        Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(cuerpo) });
      const esDeDemo = url.includes('demo');

      if (!esDeDemo && !url.includes('cerrar-periodo')) {
        return new Promise((res) => { pendientes.push(res); });
      }
      if (url.includes('despacho/clientes')) return responder(ficha('demo', 'Cliente Demo'));
      if (url.includes('asistencia/eventos')) {
        return responder({
          eventos: [{ empleado_no: 'demo-1', timestamp: '2026-08-17T08:05:00-06:00', tipo: 'entrada', fuente: 'simulado', serial_no: 1, raw: null }],
        });
      }
      if (url.includes('cerrar-periodo')) {
        const enviado = JSON.parse((init?.body as string) ?? '{}');
        return responder({
          cliente: enviado.cliente,
          periodo: { inicio: '2026-08-16', fin: '2026-08-31' },
          incidencias: (enviado.empleados as string[]).map((e) => incidencia(e, 10)),
          empleados_desconocidos: [],
        });
      }
      throw new Error(`ruta no stubbeada: ${url}`);
    }));

    function Navegador() {
      const navegar = useNavigate();
      return (
        <button onClick={() => navegar('/app/clientes/taller/nomina')}>ir al taller</button>
      );
    }

    render(
      <MemoryRouter initialEntries={['/app/clientes/demo/nomina']}>
        <Navegador />
        <Routes>
          <Route path="/app/clientes/:id/nomina" element={<NominaClientePage />} />
        </Routes>
      </MemoryRouter>,
    );

    // El primer cliente cargó: nombre, su checada en el panel, y se cierra el
    // periodo para que haya también una tabla de incidencias que arrastrar.
    expect(await screen.findByText(/Nómina de Cliente Demo/)).toBeTruthy();
    await waitFor(() => expect(screen.getAllByText('08:05').length).toBeGreaterThan(0));
    fireEvent.click(screen.getByRole('button', { name: /Cerrar quincena/ }));
    expect(await screen.findByText('PERSONA UNA')).toBeTruthy();

    fireEvent.click(screen.getByText('ir al taller'));

    // Con todo lo del taller pendiente: ni el nombre viejo, ni sus checadas, ni
    // su cierre, ni botones vivos.
    await waitFor(() => expect(pendientes.length).toBeGreaterThan(0));
    expect(screen.queryByText(/Nómina de Cliente Demo/)).toBeNull();
    expect(screen.queryAllByText('08:05')).toHaveLength(0);
    expect(screen.queryByText('PERSONA UNA')).toBeNull();
    expect(
      (screen.getByRole('button', { name: /Cerrar quincena/ }) as HTMLButtonElement).disabled,
    ).toBe(true);
  });

  it('el cierre y la nómina del cliente anterior no quedan bajo el nuevo', async () => {
    /**
     * Complemento del anterior: aquí la ficha del segundo cliente **sí** carga,
     * así que el guard de "cliente todavía null" no tapa nada. Si el cierre y
     * la nómina no se derivaran del id de la ruta, la tabla de incidencias y
     * los recibos del cliente anterior se quedarían pintados bajo el nombre del
     * nuevo — que es exactamente la mentira que persigue toda la épica.
     */
    vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => {
      const responder = (cuerpo: unknown) =>
        Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(cuerpo) });

      if (url.includes('despacho/clientes')) {
        const id = url.split('/').pop()!;
        return responder(ficha(id, `Cliente ${id}`));
      }
      if (url.includes('asistencia/eventos')) {
        // Cada cliente con SUS checadas: si todas dijeran `demo-1`, el panel del
        // taller lo mostraría legítimamente y la aserción mediría otra cosa.
        const suyo = url.includes('cliente=demo') ? 'demo-1' : 'taller-1';
        return responder({
          eventos: [{ empleado_no: suyo, timestamp: '2026-08-17T08:05:00-06:00', tipo: 'entrada', fuente: 'simulado', serial_no: 1, raw: null }],
        });
      }
      if (url.includes('cerrar-periodo')) {
        const enviado = JSON.parse((init?.body as string) ?? '{}');
        return responder({
          cliente: enviado.cliente,
          periodo: { inicio: '2026-08-16', fin: '2026-08-31' },
          incidencias: (enviado.empleados as string[]).map((e) => incidencia(e, 10)),
          empleados_desconocidos: [],
        });
      }
      if (url.includes('calcular-periodo')) return responder(NOMINA_VACIA);
      throw new Error(`ruta no stubbeada: ${url}`);
    }));

    function Navegador() {
      const navegar = useNavigate();
      return <button onClick={() => navegar('/app/clientes/taller/nomina')}>ir al taller</button>;
    }

    render(
      <MemoryRouter initialEntries={['/app/clientes/demo/nomina']}>
        <Navegador />
        <Routes>
          <Route path="/app/clientes/:id/nomina" element={<NominaClientePage />} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByDisplayValue('2026-08-16')).toBeTruthy());
    fireEvent.click(screen.getByRole('button', { name: /Cerrar quincena/ }));
    expect(await screen.findByText('PERSONA UNA')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: /Calcular nómina/ }));
    await waitFor(() => expect(screen.getByText(/Calculado con fecha de pago/)).toBeTruthy());

    fireEvent.click(screen.getByText('ir al taller'));

    // La ficha del taller carga, así que la pantalla es utilizable — pero sin
    // nada del cliente anterior.
    expect(await screen.findByText(/Nómina de Cliente taller/)).toBeTruthy();
    // Se asserta sobre el NÚMERO del empleado, no sobre su nombre: los dos
    // clientes de la fixture tienen gente llamada igual, y una incidencia
    // arrastrada de `demo` se pintaría con el número `demo-1` porque
    // `TablaIncidencias` no lo encontraría en la plantilla del taller.
    expect(screen.queryByText('demo-1')).toBeNull();
    expect(screen.queryByText(/Calculado con fecha de pago/)).toBeNull();
  });

  it('el error de un cliente no se queda pegado al siguiente', async () => {
    vi.stubGlobal('fetch', vi.fn((url: string) => {
      if (url.includes('despacho/clientes/fantasma')) {
        return Promise.resolve({
          ok: false, status: 404,
          json: () => Promise.resolve({ exito: false, error: "El cliente 'fantasma' no está en la cartera" }),
        });
      }
      if (url.includes('despacho/clientes')) {
        const id = url.split('/').pop()!;
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(ficha(id, `Cliente ${id}`)) });
      }
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({ eventos: [] }) });
    }));

    function Navegador() {
      const navegar = useNavigate();
      return <button onClick={() => navegar('/app/clientes/taller/nomina')}>ir al taller</button>;
    }

    render(
      <MemoryRouter initialEntries={['/app/clientes/fantasma/nomina']}>
        <Navegador />
        <Routes>
          <Route path="/app/clientes/:id/nomina" element={<NominaClientePage />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByText(/no está en la cartera/)).toBeTruthy();
    fireEvent.click(screen.getByText('ir al taller'));

    expect(await screen.findByText(/Nómina de Cliente taller/)).toBeTruthy();
    expect(screen.queryByText(/no está en la cartera/)).toBeNull();
  });

  it('no avisa cuando todos trabajaron', async () => {
    stubApi({ eventos: [{ empleado_no: 'taller-1', timestamp: '2026-08-17T08:05:00-06:00', tipo: 'entrada', fuente: 'simulado', serial_no: 1, raw: null }] });
    montar('taller');

    await waitFor(() => expect(screen.getByDisplayValue('2026-08-16')).toBeTruthy());
    fireEvent.click(screen.getByRole('button', { name: /Cerrar quincena/ }));
    await screen.findByText('PERSONA UNA');

    expect(screen.queryByRole('alert')).toBeNull();
  });
});
