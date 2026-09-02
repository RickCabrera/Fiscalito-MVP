/**
 * Tests de la pantalla de nómina de un cliente (E-03; era la de D-07).
 *
 * QUE PRUEBAN Y QUE NO
 * --------------------
 * Con jsdom y `fetch` stubbeado se prueba el **contrato de la pantalla**: qué
 * pide, qué manda y qué pinta. **NO** prueban que el flujo se recorra en un
 * navegador contra la API real — eso es el runbook manual de
 * `docs/D-DEMO-CHECADOR.md` y no lo cubre CI.
 *
 * FIXTURES ESCRITAS A MANO, NUNCA PEGADAS
 * ---------------------------------------
 * El `raw` de una checada real trae el nombre de la persona, y `almacen.py`
 * dice que no debe escribirse a disco. Los datos de aquí son inventados y
 * mínimos.
 */

import { afterEach, describe, expect, it, vi, beforeEach } from 'vitest';
import { cleanup, render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

const setClienteId = vi.fn();
vi.mock('../context/clienteActivoStore', () => ({
  useClienteActivo: () => ({
    clientes: [], clienteId: 'demo', cliente: null, loading: false, error: null,
    setClienteId, recargar: vi.fn(),
  }),
}));

const { default: NominaClientePage } = await import('./NominaClientePage');

/** La ficha del cliente, que desde E-03 es la fuente de la pantalla. */
const FICHA = {
  id: 'demo',
  nombre: 'Cliente De Prueba',
  giro: 'Servicios',
  origen: 'fixtures-s04',
  num_empleados: 2,
  clase_riesgo: null,
  zona: 'general',
  fecha_referencia: '2026-09-01',
  empleados: [
    { empleado_no: 'E-01', nombre: 'PERSONA UNO', puesto: '', salario_diario: '316.00', salario_diario_integrado: '331.58', zona: 'general', fecha_alta: null, antiguedad_anios: null, factor: '1.0493', factor_implicito: true },
    { empleado_no: 'E-02', nombre: 'PERSONA DOS', puesto: '', salario_diario: '326.84', salario_diario_integrado: '357.44', zona: 'general', fecha_alta: null, antiguedad_anios: null, factor: '1.0936', factor_implicito: true },
  ],
  // A propósito NO es la prima real del cliente demo (0.0054355): si la
  // fixture usara ese valor, hardcodearlo en el front pasaría el test y la
  // aserción se estaría validando sola.
  prima_riesgo: '0.0271830',
  clave_periodicidad: '07',
  periodo_sugerido: { inicio: '2026-08-16', fin: '2026-08-31', fecha_pago: '2026-08-31' },
};

const EVENTOS = {
  eventos: [
    {
      empleado_no: 'E-01',
      timestamp: '2026-08-17T08:05:00-06:00',
      tipo: 'entrada',
      fuente: 'simulado',
      serial_no: 1,
      raw: { name: 'PERSONA UNO' },
    },
  ],
};

const CIERRE = {
  cliente: 'demo',
  periodo: { inicio: '2026-08-16', fin: '2026-08-31' },
  incidencias: [
    {
      empleado_no: 'E-01',
      dias_periodo: 16,
      dias_laborables: 11,
      dias_trabajados: 11,
      faltas: 0,
      dias_ausentismo: 0,
      retardos: 1,
      dias_cotizados: 16,
    },
    {
      empleado_no: 'E-02',
      dias_periodo: 16,
      dias_laborables: 11,
      dias_trabajados: 10,
      faltas: 1,
      dias_ausentismo: 1,
      retardos: 0,
      dias_cotizados: 15,
    },
  ],
  empleados_desconocidos: ['E-99'],
};

const NOMINA = {
  cliente: 'demo',
  periodo: { inicio: '2026-08-16', fin: '2026-08-31', fecha_pago: '2026-08-31' },
  fecha_pago_efectiva: '2026-08-31',
  origen_plantilla: 'demo',
  recibos: [
    {
      empleado_no: 'E-01',
      nombre: 'PERSONA UNO',
      sbc: '331.58',
      es_salario_minimo: false,
      dias_periodo: 16,
      dias_ausentismo: 0,
      dias_pagados: 16,
      percepciones: [],
      deducciones: [{ tipo: '002', clave: 'D002', concepto: 'ISR', importe: '91.08', gravado: null, exento: null, subsidio_causado: null }],
      otros_pagos: [],
      total_percepciones: '5056.00',
      total_deducciones: '217.07',
      neto: '4838.93',
      cuota_obrera: '125.99',
      cuota_patronal: '600.00',
      absorbio_cuota_obrera: false,
      ramos: [],
    },
  ],
  porcion_mensual: { periodicidad: 'mensual', por_ramo: { invalidez_vida: '100.00' }, total_patron: '600.00', total_obrero: '125.99', total: '725.99', empleados: 1 },
  porcion_bimestral: { periodicidad: 'bimestral', por_ramo: { retiro: '50.00' }, total_patron: '300.00', total_obrero: '0.00', total: '300.00', empleados: 1 },
  advertencias: ['Las cuotas son la porción devengada en este periodo de 16 días naturales, NO el entero mensual ni el bimestral del Art. 39 LSS.'],
};

/** Router de fetch por ruta. Devuelve las llamadas para poder asertarlas. */
function stubApi(overrides: Record<string, unknown> = {}) {
  const llamadas: Array<{ url: string; init?: RequestInit }> = [];
  const respuestas: Record<string, unknown> = {
    'despacho/clientes': FICHA,
    'asistencia/eventos': EVENTOS,
    'cerrar-periodo': CIERRE,
    'calcular-periodo': NOMINA,
    ...overrides,
  };
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string, init?: RequestInit) => {
      llamadas.push({ url, init });
      const clave = Object.keys(respuestas).find((k) => url.includes(k));
      if (!clave) throw new Error(`ruta no stubbeada: ${url}`);
      const cuerpo = respuestas[clave];
      if (cuerpo instanceof Error) {
        return Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({ error: cuerpo.message }) });
      }
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(cuerpo) });
    }),
  );
  return llamadas;
}

function montar(clienteId = 'demo') {
  return render(
    <MemoryRouter initialEntries={[`/app/clientes/${clienteId}/nomina`]}>
      <Routes>
        <Route path="/app/clientes/:id/nomina" element={<NominaClientePage />} />
      </Routes>
    </MemoryRouter>,
  );
}

/**
 * Espera a que la ficha del cliente haya cargado.
 *
 * NO basta con esperar a que el botón exista: existe desde el primer render,
 * **deshabilitado** hasta que llega `GET /despacho/clientes/{id}`, y un click
 * sobre él no hace nada. Esperar sólo su existencia hacía el test dependiente
 * de que la promesa resolviera rápido — verde en local, rojo en CI.
 *
 * El valor de la fecha sólo aparece cuando la plantilla llegó, así que es la
 * señal correcta.
 */
async function esperarPlantilla() {
  await waitFor(() => expect(screen.getByDisplayValue('2026-08-16')).toBeTruthy());
  const boton = screen.getByRole('button', { name: /Cerrar quincena/ }) as HTMLButtonElement;
  expect(boton.disabled).toBe(false);
  return boton;
}

describe('NominaClientePage', () => {
  beforeEach(() => {
    vi.useRealTimers();
  });

  // `vitest.config.ts` no activa `globals`, asi que el auto-cleanup de
  // Testing Library NO corre: sin esto los renders se acumulan y las
  // consultas encuentran elementos de tests anteriores.
  afterEach(cleanup);

  it('pinta las checadas con nombre y hora', async () => {
    stubApi();
    montar();
    expect(await screen.findByText(/PERSONA UNO/)).toBeTruthy();
    expect(screen.getByText('08:05')).toBeTruthy();
  });

  it('el polling NO manda `desde`', async () => {
    /**
     * Es la regresión que dejaría el panel vacío en la demo: el simulador
     * siembra la última quincena YA TERMINADA, así que un `desde` anclado en
     * el presente no devolvería nada. Y si algún día se mandara, tendría que
     * llevar offset — un `desde` naive revienta en el almacén.
     */
    const llamadas = stubApi();
    montar();
    await waitFor(() => expect(llamadas.some((l) => l.url.includes('asistencia/eventos'))).toBe(true));
    const eventos = llamadas.filter((l) => l.url.includes('asistencia/eventos'));
    for (const l of eventos) {
      expect(l.url).not.toContain('desde');
    }
  });

  it('el periodo se precarga del backend y no se deduce de las checadas', async () => {
    /**
     * Del 16 al 31 de agosto son 16 días naturales; la primera checada es del
     * 17 porque el 16 es domingo. Deducirlo de los eventos daría 15 y movería
     * la base de las cuotas y los días pagados.
     */
    stubApi();
    montar();
    await waitFor(() => expect(screen.getByDisplayValue('2026-08-16')).toBeTruthy());
    expect(screen.getByDisplayValue('2026-08-31')).toBeTruthy();
  });

  it('muestra la fecha de pago con la que se va a calcular', async () => {
    stubApi();
    montar();
    await waitFor(() => expect(screen.getAllByText(/2026-08-31/).length).toBeGreaterThan(0));
  });

  it('al cerrar pinta faltas, retardos y los empleados desconocidos', async () => {
    stubApi();
    montar();
    fireEvent.click(await esperarPlantilla());
    expect(await screen.findByText(/Checadas de empleados que no están en la plantilla/)).toBeTruthy();
    expect(screen.getByText(/E-99/)).toBeTruthy();
    expect(screen.getByText('PERSONA DOS')).toBeTruthy();
  });

  it('manda las incidencias verbatim al calcular', async () => {
    /**
     * `dias_periodo`, `faltas` y `dias_ausentismo` alimentan `DiasDelPeriodo` y
     * los días pagados. Si la pantalla los recompusiera, estaría moviendo las
     * cuotas del IMSS desde la UI.
     *
     * De los tres, **sólo `faltas` y `dias_ausentismo` distinguen de verdad**:
     * están puestos distintos entre E-01 (0/0) y E-02 (1/1) y no se pueden
     * recuperar de ningún otro campo. `dias_periodo` sí sería recomponible
     * desde las fechas —`(fin − inicio) + 1` da el mismo 16 que devuelve
     * `cerrar_periodo`, por construcción del backend, no por suerte—, así que
     * esa parte de la aserción no protege contra nada. Se deja escrito para
     * que nadie la lea como si protegiera.
     */
    const llamadas = stubApi();
    montar();
    fireEvent.click(await esperarPlantilla());
    await screen.findByText('PERSONA DOS');
    fireEvent.click(screen.getByRole('button', { name: /Calcular nómina/ }));

    await waitFor(() => expect(llamadas.some((l) => l.url.includes('calcular-periodo'))).toBe(true));
    const llamada = llamadas.find((l) => l.url.includes('calcular-periodo'))!;
    const cuerpo = JSON.parse(llamada.init!.body as string);
    expect(cuerpo.incidencias).toEqual([
      { empleado_no: 'E-01', dias_periodo: 16, faltas: 0, dias_ausentismo: 0 },
      { empleado_no: 'E-02', dias_periodo: 16, faltas: 1, dias_ausentismo: 1 },
    ]);
    // Los parámetros del patrón salen de la plantilla del backend, no del
    // front: son constantes con fundamento legal (Art. 72/74 LSS).
    expect(cuerpo.parametros.prima_riesgo).toBe(FICHA.prima_riesgo);
    expect(cuerpo.parametros.clave_periodicidad).toBe(FICHA.clave_periodicidad);
  });

  it('si el operador mueve el periodo, la fecha de pago la resuelve el backend', async () => {
    /**
     * O-A: con el periodo editado a otro mes, mandar la `fecha_pago` de la
     * quincena sugerida calcularía con la vigencia equivocada (UMA, salario
     * mínimo, tarifa y transitorio de enero dependen de ella). Se manda `null`
     * y el backend resuelve; la pantalla imprime `fecha_pago_efectiva`.
     */
    const llamadas = stubApi();
    montar();
    await esperarPlantilla();
    fireEvent.change(screen.getByDisplayValue('2026-08-16'), { target: { value: '2026-01-16' } });
    fireEvent.change(screen.getByDisplayValue('2026-08-31'), { target: { value: '2026-01-31' } });
    fireEvent.click(screen.getByRole('button', { name: /Cerrar quincena/ }));
    // Las checadas del panel son de agosto y el periodo ahora es de enero: la
    // pantalla pregunta antes de cerrar, y con razón.
    fireEvent.click(await screen.findByRole('button', { name: 'Cerrar de todos modos' }));
    await screen.findByText('PERSONA DOS');
    fireEvent.click(screen.getByRole('button', { name: /Calcular nómina/ }));

    await waitFor(() => expect(llamadas.some((l) => l.url.includes('calcular-periodo'))).toBe(true));
    const cuerpo = JSON.parse(
      llamadas.find((l) => l.url.includes('calcular-periodo'))!.init!.body as string,
    );
    expect(cuerpo.periodo).toEqual({ inicio: '2026-01-16', fin: '2026-01-31', fecha_pago: null });
  });

  it('sin tocar el periodo se manda la fecha de pago sugerida', async () => {
    const llamadas = stubApi();
    montar();
    fireEvent.click(await esperarPlantilla());
    await screen.findByText('PERSONA DOS');
    fireEvent.click(screen.getByRole('button', { name: /Calcular nómina/ }));

    await waitFor(() => expect(llamadas.some((l) => l.url.includes('calcular-periodo'))).toBe(true));
    const cuerpo = JSON.parse(
      llamadas.find((l) => l.url.includes('calcular-periodo'))!.init!.body as string,
    );
    expect(cuerpo.periodo.fecha_pago).toBe('2026-08-31');
  });

  it('pinta recibos, cuotas por ramo y las advertencias del backend', async () => {
    stubApi();
    montar();
    fireEvent.click(await esperarPlantilla());
    await screen.findByText('PERSONA DOS');
    fireEvent.click(screen.getByRole('button', { name: /Calcular nómina/ }));

    expect(await screen.findByText('Recibos')).toBeTruthy();
    expect(screen.getByText('Invalidez y Vida')).toBeTruthy();
    expect(screen.getByText(/NO el entero mensual ni el bimestral/)).toBeTruthy();
  });

  /**
   * E-06 — la pantalla se explica sola.
   *
   * QUE PRUEBAN: que los cuatro pasos existan DESDE EL PRIMER RENDER, con su
   * línea de qué hacen, y que se habiliten en orden. El modo de falla que
   * cierran es el de antes: tres botones sueltos, sin numerar, y el de exportar
   * **ni siquiera renderizado** hasta que hubiera nómina — así que el cuarto
   * paso no existía en pantalla y no había forma de saber que estaba ahí.
   */
  describe('los cuatro pasos', () => {
    const TITULOS = [
      /1\. Checadas recibidas/,
      /2\. Cerrar quincena/,
      /3\. Calcular nómina/,
      /4\. Exportar/,
    ];

    it('los cuatro están numerados y visibles desde el primer render', async () => {
      stubApi();
      montar();
      for (const titulo of TITULOS) {
        expect(await screen.findByRole('heading', { name: titulo })).toBeTruthy();
      }
    });

    it('cada paso dice en una línea qué hace', async () => {
      stubApi();
      montar();
      expect(await screen.findByText(/convierte las checadas en días trabajados/i)).toBeTruthy();
      expect(screen.getByText(/percepciones, ISR retenido, cuotas del IMSS/i)).toBeTruthy();
      expect(screen.getByText(/PDF con los recibos y las cuotas patronales/i)).toBeTruthy();
      expect(screen.getByText(/el panel se refresca solo/i)).toBeTruthy();
    });

    it('el paso 3 está bloqueado hasta cerrar la quincena, y dice por qué', async () => {
      stubApi();
      montar();
      await esperarPlantilla();

      const calcular = screen.getByRole('button', { name: /Calcular nómina/ }) as HTMLButtonElement;
      expect(calcular.disabled).toBe(true);
      expect(screen.getByText(/Cierra la quincena primero/)).toBeTruthy();

      fireEvent.click(screen.getByRole('button', { name: /Cerrar quincena/ }));
      await screen.findByText('PERSONA DOS');
      expect((screen.getByRole('button', { name: /Calcular nómina/ }) as HTMLButtonElement).disabled)
        .toBe(false);
    });

    it('el paso 4 EXISTE deshabilitado antes de calcular, no aparece de la nada', async () => {
      /**
       * La regresión concreta: antes el botón de exportar se renderizaba sólo
       * con `{nomina && ...}`. Un paso que no está en pantalla no se puede
       * anticipar, y la pantalla dejaba de tener cuatro pasos.
       */
      stubApi();
      montar();
      const exportar = await screen.findByRole('button', { name: /Exportar PDF/ });
      expect((exportar as HTMLButtonElement).disabled).toBe(true);
      expect(screen.getByText(/Calcula la nómina primero/)).toBeTruthy();

      fireEvent.click(await esperarPlantilla());
      await screen.findByText('PERSONA DOS');
      fireEvent.click(screen.getByRole('button', { name: /Calcular nómina/ }));
      await screen.findByText('Recibos');

      expect((screen.getByRole('button', { name: /Exportar PDF/ }) as HTMLButtonElement).disabled)
        .toBe(false);
    });

    it('la migaja de pan dice en qué cliente estoy y da el regreso', async () => {
      stubApi();
      montar();
      const migaja = await screen.findByRole('navigation', { name: 'Ruta' });
      expect(migaja.textContent).toContain('Clientes');
      await waitFor(() => expect(migaja.textContent).toContain('Cliente De Prueba'));
      expect(migaja.textContent).toContain('Nómina');
    });
  });

  it('un error de red se muestra en pantalla y no deja la página en blanco', async () => {
    stubApi({ 'asistencia/eventos': new Error('conexión rechazada') });
    montar();
    expect(await screen.findByText(/No se pudieron leer las checadas/)).toBeTruthy();
    expect(screen.getByText(/conexión rechazada/)).toBeTruthy();
  });
});
