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

// G-03: las pantallas piden la cartera. El doble viene vacío, así que
// `useNominaCliente` cae a los empleados de la ficha del backend — el mismo
// camino que estas pruebas medían antes de G-01.
vi.mock('../context/carteraStore', async () => {
  const { carteraDePrueba } = await import('../test/carteraDePrueba');
  return { useCartera: () => carteraDePrueba() };
});


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

/**
 * G-01: la ficha abre en el tab **Empleados**, que es el editable y sale de la
 * cartera. Estas pruebas miden el tab **Plantilla** (la vista de E-02/E-04, que
 * sigue intacta), así que lo seleccionan explícitamente. El default lo fija su
 * propia prueba, abajo.
 */
async function verPlantilla() {
  fireEvent.click(await screen.findByRole('button', { name: 'Plantilla' }));
}

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
  respuesta.actual = CASO_REAL;
  respuesta.falla = null;
  cleanup();
});

describe('ficha del caso real anonimizado', () => {
  it('pinta la plantilla con salario diario y SBC', async () => {
    montar('demo');
    await verPlantilla();
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Servicios Administrativos Integrales' })).toBeTruthy());

    expect(screen.getByText('PERSONA UNO')).toBeTruthy();
    expect(screen.getByText('316.00')).toBeTruthy();
    expect(screen.getByText('331.58')).toBeTruthy();
  });

  it('marca el factor como observado y no enseña alta inventada', async () => {
    montar('demo');
    await verPlantilla();
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
    await verPlantilla();
    await waitFor(() => expect(screen.getByText('MARISOL ABREGO QUINTERO')).toBeTruthy());

    expect(screen.getByText('2021-02-01')).toBeTruthy();
    expect(screen.getByText('5 años')).toBeTruthy();
    expect(screen.getByText('Encargada de tienda')).toBeTruthy();
  });

  it('dice contra qué fecha se midió la antigüedad, y no la llama "hoy"', async () => {
    respuesta.actual = SINTETICO;
    montar('cafeteria');
    await verPlantilla();
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
    await verPlantilla();
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
  it('abre en Empleados, que es el tab editable', async () => {
    // El default es deliberado: G-01 pide que el contador llegue a la gestión
    // de empleados, no a la vista de sólo lectura. Si alguien lo invierte, esta
    // prueba lo dice en vez de dejarlo pasar como un cambio de estilo.
    montar('demo');
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Empleados' }).getAttribute('aria-current')).toBe('true'),
    );
  });

  it('el tab Plantilla sigue alcanzable y es el camino probado de E-02/E-04', async () => {
    // Dejarlo alcanzable es lo que hace que la demo siga teniendo su vista
    // verificada aunque el camino de Firestore falle.
    montar('demo');
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Servicios Administrativos Integrales' })).toBeTruthy());
    fireEvent.click(screen.getByRole('button', { name: 'Plantilla' }));
    expect(screen.getByText('PERSONA UNO')).toBeTruthy();
  });
});
