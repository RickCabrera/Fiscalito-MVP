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
import { MemoryRouter, Route, Routes } from 'react-router-dom';

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
    vi.stubGlobal('confirm', vi.fn(() => true));
    stubApi({ diasTrabajados: 0 });
    montar('taller');

    await waitFor(() => expect(screen.getByDisplayValue('2026-08-16')).toBeTruthy());
    fireEvent.click(screen.getByRole('button', { name: /Cerrar quincena/ }));

    const aviso = await screen.findByRole('alert');
    expect(aviso.textContent).toContain('Ningún empleado tiene checadas en este periodo');
    expect(aviso.textContent).toContain('no será de ceros');
  });

  it('pide confirmación antes de cerrar con el panel vacío', async () => {
    const confirmar = vi.fn(() => false);
    vi.stubGlobal('confirm', confirmar);
    const llamadas = stubApi({ eventos: [] });
    montar('taller');

    await waitFor(() => expect(screen.getByDisplayValue('2026-08-16')).toBeTruthy());
    fireEvent.click(screen.getByRole('button', { name: /Cerrar quincena/ }));

    expect(confirmar).toHaveBeenCalledTimes(1);
    // Dijo que no: no se cerró nada.
    expect(llamadas.some((l) => l.url.includes('cerrar-periodo'))).toBe(false);
  });

  it('con checadas en el panel no pregunta nada', async () => {
    const confirmar = vi.fn(() => true);
    vi.stubGlobal('confirm', confirmar);
    stubApi({
      eventos: [{ empleado_no: 'taller-1', timestamp: '2026-08-17T08:05:00-06:00', tipo: 'entrada', fuente: 'simulado', serial_no: 1, raw: null }],
    });
    montar('taller');

    await waitFor(() => expect(screen.getByDisplayValue('2026-08-16')).toBeTruthy());
    fireEvent.click(screen.getByRole('button', { name: /Cerrar quincena/ }));

    expect(confirmar).not.toHaveBeenCalled();
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
