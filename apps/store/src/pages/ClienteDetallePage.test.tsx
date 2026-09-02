/**
 * Ficha del cliente (E-02).
 *
 * EL CASO QUE VALE EL ARCHIVO es el etiquetado del factor. Para el caso real
 * anonimizado el factor es un **cociente observado** (SBC ÷ salario diario) que
 * puede incluir prestaciones superiores que el CFDI no desglosa: no es el
 * factor de ley del Art. 27 LSS, y §D9 documenta que ahí el SBC no se deriva de
 * la antigüedad. Enseñar los dos con la misma etiqueta llevaría a comparar
 * factor contra antigüedad y a concluir que el motor está mal.
 */

import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import type { ClienteDetalle } from '../services/despachoApi';

// R-06: las pantallas leen la cuenta para decidir si ven los datos de
// demostración. En jsdom `import.meta.env.DEV` es `true`, así que el doble
// basta con existir: la cuenta cuenta como de desarrollo y los tests de la
// demo siguen midiendo lo mismo que medían.
vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({ user: { uid: 'uid-demo', email: 'demo@ejemplo.mx' }, loading: false }),
}));

/**
 * G-03: la cartera del doble es **configurable**, y por default viene POBLADA
 * con el cliente de demostración.
 *
 * Con el doble vacío —como estaba— las ramas nuevas de esta pantalla
 * (`cabecera`, el error derivado, los tres estados de la ficha) sólo se
 * ejercitaban con `deLaCartera === null`, que es justo el caso que NO ocurre
 * después de sembrar. Esa ceguera dejó pasar dos defectos: la ficha de un
 * cliente de demostración abría diciendo "este cliente lo diste de alta tú"
 * durante toda la ventana del fetch, y el conteo de empleados pintaba el número
 * del backend cuando la cartera decía 0.
 */
const enCartera = {
  clientes: [] as Array<Record<string, unknown>>,
};

vi.mock('../context/carteraStore', async () => {
  const { carteraDePrueba } = await import('../test/carteraDePrueba');
  return {
    useCartera: () =>
      carteraDePrueba({
        clientes: enCartera.clientes as never,
        origen: 'firestore',
        soloLectura: false,
        clientePorId: (id: string) =>
          (enCartera.clientes.find((c) => c.id === id) as never) ?? null,
      }),
  };
});

/** El cliente de demostración tal como queda en la cartera después de sembrar. */
function enLaCartera(empleados: number) {
  return {
    id: 'demo',
    nombre: 'Servicios Administrativos Integrales',
    giro: 'Servicios administrativos',
    origen: 'fixtures-s04',
    prima_riesgo: '0.0054355',
    clase_riesgo: null,
    clave_periodicidad: '04',
    zona: 'general',
    periodo_sugerido: { inicio: '2026-08-16', fin: '2026-08-31', fecha_pago: null },
    empleados: Array.from({ length: empleados }, (_, i) => ({
      empleado_no: `E-0${i + 1}`, nombre: `EMPLEADO ${i + 1}`, puesto: '',
      salario_diario: '316.00', salario_diario_integrado: '331.58', zona: 'general',
      fecha_alta: null, tipo_contrato: 'indeterminado',
      prestaciones: { dias_aguinaldo: 15, dias_vacaciones: 0, prima_vacacional: '0.25' },
      nss: '', employee_no: `E-0${i + 1}`, enrolamiento: 'enrolado',
    })),
  };
}


const CASO_REAL: ClienteDetalle = {
  id: 'demo', nombre: 'Servicios Administrativos Integrales', giro: 'Servicios administrativos',
  origen: 'fixtures-s04', num_empleados: 2, prima_riesgo: '0.0054355',
  clase_riesgo: null, clave_periodicidad: '04', zona: 'general',
  empleados: [
    {
      empleado_no: 'E-01', nombre: 'PERSONA UNO', puesto: '',
      salario_diario: '316.00', salario_diario_integrado: '331.58', zona: 'general',
      fecha_alta: null, antiguedad_anios: null, factor: '1.0493', factor_implicito: true,
    },
    {
      empleado_no: 'E-02', nombre: 'PERSONA DOS', puesto: '',
      salario_diario: '326.84', salario_diario_integrado: '357.44', zona: 'general',
      fecha_alta: null, antiguedad_anios: null, factor: '1.0936', factor_implicito: true,
    },
  ],
  periodo_sugerido: { inicio: '2026-08-16', fin: '2026-08-31', fecha_pago: '2026-08-31' },
  fecha_referencia: '2026-09-01',
};

const SINTETICO: ClienteDetalle = {
  id: 'cafeteria', nombre: 'Cafeteria La Estacion', giro: 'Alimentos y bebidas',
  origen: 'sintetico', num_empleados: 1, prima_riesgo: '0.0113065',
  clase_riesgo: 2, clave_periodicidad: '04', zona: 'general',
  empleados: [
    {
      empleado_no: 'C-01', nombre: 'MARISOL ABREGO QUINTERO', puesto: 'Encargada de tienda',
      salario_diario: '520.00', salario_diario_integrado: '548.50', zona: 'general',
      fecha_alta: '2021-02-01', antiguedad_anios: 5, factor: '1.0548', factor_implicito: false,
    },
  ],
  periodo_sugerido: { inicio: '2026-08-16', fin: '2026-08-31', fecha_pago: '2026-08-31' },
  fecha_referencia: '2026-09-01',
};

const respuesta = { actual: CASO_REAL as ClienteDetalle, falla: null as string | null };

vi.mock('../services/despachoApi', async () => {
  const real = await vi.importActual<typeof import('../services/despachoApi')>('../services/despachoApi');
  return {
    ...real,
    obtenerCliente: vi.fn(async () => {
      if (respuesta.falla) throw new Error(respuesta.falla);
      return respuesta.actual;
    }),
  };
});

const { default: ClienteDetallePage } = await import('./ClienteDetallePage');

function montar(id: string) {
  return render(
    <MemoryRouter initialEntries={[`/app/clientes/${id}`]}>
      <Routes>
        <Route path="/app/clientes/:id" element={<ClienteDetallePage />} />
      </Routes>
    </MemoryRouter>,
  );
}

afterEach(() => {
  // En `afterEach`: si una asercion revienta antes, `DEV=false` se filtraria
  // a los tests siguientes del archivo.
  vi.unstubAllEnvs();
  respuesta.actual = CASO_REAL;
  respuesta.falla = null;
  enCartera.clientes = [];
  cleanup();
});

describe('ficha del caso real anonimizado', () => {
  it('pinta la plantilla con salario diario y SBC', async () => {
    montar('demo');
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Servicios Administrativos Integrales' })).toBeTruthy());

    expect(screen.getByText('PERSONA UNO')).toBeTruthy();
    expect(screen.getByText('316.00')).toBeTruthy();
    expect(screen.getByText('331.58')).toBeTruthy();
  });

  it('marca el factor como observado y no enseña alta inventada', async () => {
    montar('demo');
    await waitFor(() => expect(screen.getByText('PERSONA UNO')).toBeTruthy());

    // Cada renglón afectado lleva su marca, no sólo la nota al pie: la tabla se
    // lee renglón por renglón y el pie se pierde de vista al hacer scroll.
    expect(screen.getAllByTitle(/Cociente observado/i)).toHaveLength(2);
    // Y la nota explica por qué no hay alta ni antigüedad para este cliente.
    expect(screen.getByText(/cociente observado/i)).toBeTruthy();
    expect(screen.getByText(/no las trae y no se inventan/i)).toBeTruthy();
    // Y las celdas de alta y antigüedad salen vacías, no con un cero engañoso.
    expect(screen.getAllByText('—').length).toBeGreaterThanOrEqual(4);
  });

  it('dice que su prima es autodeterminada, no que no tenga clase', async () => {
    // Todo patrón tiene clase de riesgo; lo que no se hizo fue deducir su prima
    // de una clase. "No aplica" habría sido falso.
    montar('demo');
    await waitFor(() => expect(screen.getByText('Autodeterminada (Art. 74)')).toBeTruthy());
  });
});

describe('ficha de un cliente sintético', () => {
  it('enseña alta, antigüedad y puesto', async () => {
    respuesta.actual = SINTETICO;
    montar('cafeteria');
    await waitFor(() => expect(screen.getByText('MARISOL ABREGO QUINTERO')).toBeTruthy());

    expect(screen.getByText('2021-02-01')).toBeTruthy();
    expect(screen.getByText('5 años')).toBeTruthy();
    expect(screen.getByText('Encargada de tienda')).toBeTruthy();
  });

  it('dice contra qué fecha se midió la antigüedad, y no la llama "hoy"', async () => {
    respuesta.actual = SINTETICO;
    montar('cafeteria');
    await waitFor(() => expect(screen.getByText(/medidos al/i)).toBeTruthy());
    expect(screen.getByText('2026-09-01')).toBeTruthy();
  });

  it('declara que la clase de riesgo es un supuesto', async () => {
    respuesta.actual = SINTETICO;
    montar('cafeteria');
    await waitFor(() => expect(screen.getByText('2 (supuesta)')).toBeTruthy());
  });

  it('no marca su factor como implícito', async () => {
    respuesta.actual = SINTETICO;
    montar('cafeteria');
    await waitFor(() => expect(screen.getByText('MARISOL ABREGO QUINTERO')).toBeTruthy());
    expect(screen.queryByText(/cociente observado/i)).toBeNull();
    expect(screen.queryAllByTitle(/Cociente observado/i)).toHaveLength(0);
  });
});

describe('cliente que no existe', () => {
  it('enseña el error del backend, no una pantalla en blanco', async () => {
    respuesta.falla = "El cliente 'fantasma' no está en la cartera de la demo.";
    montar('fantasma');

    await waitFor(() => expect(screen.getByText(/no está en la cartera/i)).toBeTruthy());
    expect(screen.queryByText('Plantilla')).toBeNull();
  });
});

describe('tabs de la ficha (G-01)', () => {
  it('una cuenta de desarrollo abre en Plantilla', async () => {
    // En jsdom `import.meta.env.DEV` es `true`, así que ésta es la rama de
    // desarrollo. El default de G-01 era Plantilla para no mover el guion de la
    // demo; se conserva para quien la necesita.
    montar('demo');
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Plantilla' }).getAttribute('aria-current')).toBe('true'),
    );
  });

  it('una cuenta normal NO tiene la pestaña Plantilla, y abre en Empleados', async () => {
    /**
     * R-06. La pestaña Plantilla enseña el histórico del caso real: un CFDI
     * timbrado con montos reales anonimizados de nueve personas. Una cuenta de
     * producción no tiene por qué verlo.
     *
     * **Las fixtures y sus tests no se tocan** — son la verificación del motor
     * contra la realidad. Lo que se oculta es una pestaña.
     */
    vi.stubEnv('DEV', false);
    montar('demo');

    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Empleados' }).getAttribute('aria-current')).toBe('true'),
    );
    expect(screen.queryByRole('button', { name: 'Plantilla' })).toBeNull();
    // Y el contenido tampoco se cuela por otro lado: ningún salario del caso
    // real en el DOM.
    expect(screen.queryByText('316.00')).toBeNull();
  });

  it('el tab Empleados está visible y a un clic', async () => {
    montar('demo');
    await waitFor(() => expect(screen.getByRole('button', { name: 'Empleados' })).toBeTruthy());
    fireEvent.click(screen.getByRole('button', { name: 'Empleados' }));
    expect(screen.getByRole('button', { name: 'Empleados' }).getAttribute('aria-current')).toBe('true');
  });
});


describe('la ficha con la cartera POBLADA (el estado real tras sembrar)', () => {
  it('un cliente de demostración NO dice "lo diste de alta tú" mientras carga', async () => {
    // El defecto: con la cartera poblada, `loading` era false y `cliente` aún
    // null, así que la ficha de Servicios Administrativos Integrales abría con
    // el mensaje de "cliente propio" durante toda la ventana del fetch. En una
    // demo con red lenta y proyector, segundos en pantalla.
    enCartera.clientes = [enLaCartera(2)];
    montar('demo');
    expect(screen.queryByText(/lo diste de alta t/i)).toBeNull();
    await waitFor(() =>
      expect(screen.getByRole('heading', { name: 'Servicios Administrativos Integrales' })).toBeTruthy(),
    );
    expect(screen.queryByText(/lo diste de alta t/i)).toBeNull();
  });

  it('un cliente que sólo existe en la cartera sí lo dice, y no muere', async () => {
    // El caso legítimo del mensaje: no hay ficha en el backend y no la habrá.
    respuesta.falla = 'El cliente no está en la cartera de la demo.';
    enCartera.clientes = [{ ...enLaCartera(1), id: 'mio', nombre: 'Tortilleria Lopez' }];
    montar('mio');
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Tortilleria Lopez' })).toBeTruthy());
    expect(screen.getByText(/lo diste de alta t/i)).toBeTruthy();
    // Y NO se pinta el error del 404: el cliente existe.
    expect(screen.queryByText(/no está en la cartera de la demo/i)).toBeNull();
  });

  it('el conteo de empleados sale de la cartera, incluido el cero', async () => {
    // Con `||`, una cartera de 0 empleados pintaba el número del backend.
    enCartera.clientes = [enLaCartera(0)];
    montar('demo');
    await waitFor(() =>
      expect(screen.getByRole('heading', { name: 'Servicios Administrativos Integrales' })).toBeTruthy(),
    );
    // "Empleados" aparece dos veces: la etiqueta del dato y el tab. La del
    // dato es un div; el tab es un button.
    const etiqueta = screen.getAllByText('Empleados').find((el) => el.tagName === 'DIV');
    expect(etiqueta?.parentElement?.textContent).toBe('Empleados0');
  });
});
