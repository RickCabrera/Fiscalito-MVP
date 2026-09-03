/**
 * Las validaciones del alta de empleado que impiden un error fiscal.
 *
 * Las tres de aquí son lógica nueva que quedó **sin un solo test** hasta que un
 * revisor las mutó y la suite siguió verde. Cada una atrapa algo que después no
 * se ve:
 *
 * 1. `empleado_no` repetido — es la llave del CÁLCULO: dos iguales y uno se
 *    come las incidencias del otro.
 * 2. `employee_no` repetido — el checador manda **una sola** serie de checadas
 *    por número, así que una de las dos personas se queda sin incidencias y el
 *    cálculo revienta con "estos empleados no traen incidencias del periodo",
 *    un mensaje que manda a cerrar un periodo que sí se cerró.
 * 3. Sin el SBC del motor no se guarda — el front no calcula el Art. 27, así
 *    que si `POST /nomina/sbc` falla no hay SDI que escribir.
 *
 * **Lo que este archivo NO prueba:** la cota de la prima de RT del Art. 72. Esa
 * validación vive en `ModalCliente`, no aquí, y la prueba
 * `ModalCliente.test.tsx`. El encabezado la reclamaba: era una afirmación de
 * cobertura que no existía, del mismo tipo que este entregable ya cazó dos veces.
 */

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import ModalEmpleado from './ModalEmpleado';
import type { EmpleadoCartera, ParametrosSalariales } from '../../services/carteraApi';

const integrarSBC = vi.fn();
vi.mock('../../services/carteraApi', async () => {
  const real = await vi.importActual<typeof import('../../services/carteraApi')>(
    '../../services/carteraApi',
  );
  return { ...real, integrarSBC: (req: unknown) => integrarSBC(req) };
});

const SBC_OK = {
  factor: '1.0521',
  dias_vacaciones_aplicados: 16,
  sbc_sin_acotar: '526.05',
  sbc: '526.05',
  piso_aplicado: false,
  tope_aplicado: false,
  piso: '315.04',
  tope: '2932.75',
  fundamento: 'Arts. 27, 28 y 30 fr. I LSS',
};

afterEach(() => {
  vi.clearAllMocks();
  cleanup();
});

function pintar(opciones: {
  empleado?: EmpleadoCartera | null;
  existentes?: string[];
  enUsoPorOtro?: string[];
  parametros?: ParametrosSalariales;
} = {}) {
  const onGuardar = vi.fn().mockResolvedValue(undefined);
  integrarSBC.mockResolvedValue(SBC_OK);
  render(
    <ModalEmpleado
      empleado={opciones.empleado ?? null}
      existentes={opciones.existentes ?? []}
      enUsoPorOtro={opciones.enUsoPorOtro ?? []}
      onGuardar={onGuardar}
      onCerrar={vi.fn()}
      parametros={opciones.parametros}
    />,
  );
  return onGuardar;
}

function capturar(campo: RegExp, valor: string) {
  fireEvent.change(screen.getByLabelText(campo), { target: { value: valor } });
}

/** Llena lo mínimo para que el botón dependa sólo de lo que se está probando. */
async function llenarBasico() {
  capturar(/Número de empleado/, 'N-01');
  // O-04: hay dos campos que empiezan con "Nombre" —el completo y el de pila
  // del layout del IMSS— así que el matcher tiene que ser exacto.
  capturar(/^Nombre \*$/, 'PERSONA NUEVA');
  capturar(/Salario diario/, '500.00');
  // Se espera a que el MOTOR haya respondido, no a que aparezca un texto: el
  // panel del SBC tiene debounce de 400 ms y "SBC" también es una etiqueta.
  await waitFor(() => expect(integrarSBC).toHaveBeenCalled());
  await waitFor(() => expect(screen.getByText(/^\$526\.05$/)).toBeTruthy());
}

const botonAlta = () => screen.getByRole('button', { name: /Dar de alta/ });

describe('ModalEmpleado · el número del checador no se puede repetir', () => {
  it('avisa y no deja guardar si otro empleado ya tiene ese número', async () => {
    pintar({ enUsoPorOtro: ['7'] });
    await llenarBasico();
    capturar(/employeeNo del aparato/, '7');

    expect(screen.getByRole('alert').textContent).toContain('ya tiene el número de checador');
    await waitFor(() => expect(botonAlta()).toHaveProperty('disabled', true));
  });

  it('un número libre sí deja guardar', async () => {
    pintar({ enUsoPorOtro: ['7'] });
    await llenarBasico();
    capturar(/employeeNo del aparato/, '8');

    await waitFor(() => expect(botonAlta()).toHaveProperty('disabled', false));
  });

  it('dejarlo vacío no cuenta como repetido', async () => {
    // Sin vincular es un estado legítimo: la pantalla lo marca, no lo impide.
    pintar({ enUsoPorOtro: ['7'] });
    await llenarBasico();

    await waitFor(() => expect(botonAlta()).toHaveProperty('disabled', false));
  });
});

describe('ModalEmpleado · el número interno tampoco', () => {
  it('avisa y no deja guardar si ya existe', async () => {
    pintar({ existentes: ['N-01'] });
    await llenarBasico();

    expect(screen.getByRole('alert').textContent).toContain('Ya hay un empleado con el número');
    await waitFor(() => expect(botonAlta()).toHaveProperty('disabled', true));
  });
});

describe('ModalEmpleado · el SBC lo calcula el motor', () => {
  it('no se puede guardar sin el SBC del motor', async () => {
    // El SDI que se guarda es el que devolvió el backend, ya acotado. Sin él no
    // hay nada que guardar: el front no calcula el Art. 27.
    pintar();
    // Después de `pintar`, que es quien deja el mock en modo feliz.
    integrarSBC.mockReset();
    integrarSBC.mockRejectedValue(new Error('API caída'));
    capturar(/Número de empleado/, 'N-01');
    // O-04: hay dos campos que empiezan con "Nombre" —el completo y el de pila
  // del layout del IMSS— así que el matcher tiene que ser exacto.
  capturar(/^Nombre \*$/, 'PERSONA NUEVA');
    capturar(/Salario diario/, '500.00');

    await waitFor(() =>
      expect(screen.getAllByRole('alert').some((a) => a.textContent?.includes('API caída'))).toBe(true),
    );
    expect(botonAlta()).toHaveProperty('disabled', true);
  });

  it('guarda el SBC que devolvió el motor, no uno recalculado', async () => {
    const onGuardar = pintar();
    await llenarBasico();
    capturar(/employeeNo del aparato/, '9');
    await waitFor(() => expect(botonAlta()).toHaveProperty('disabled', false));

    fireEvent.click(botonAlta());
    await waitFor(() => expect(onGuardar).toHaveBeenCalled());
    expect(onGuardar.mock.calls[0][0].salario_diario_integrado).toBe('526.05');
  });

  it('manda la fecha explícita al motor: piso y tope se mueven en fechas distintas', async () => {
    pintar();
    await llenarBasico();
    expect(integrarSBC.mock.calls[0][0].fecha).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });
});

describe('ModalEmpleado · NSS (R-03)', () => {
  it('vacío guarda: es la salida del contador que no tiene el número', async () => {
    // No es un caso de borde: es lo que hace seguro rechazar por longitud sin
    // acorralar a nadie. Si esto dejara de guardar, el bloqueo por longitud
    // tendría que caerse con él.
    const onGuardar = pintar();
    await llenarBasico();
    await waitFor(() => expect(botonAlta()).toHaveProperty('disabled', false));

    fireEvent.click(botonAlta());
    await waitFor(() => expect(onGuardar).toHaveBeenCalled());
    expect(onGuardar.mock.calls[0][0].nss).toBe('');
  });

  it('longitud mala BLOQUEA, y no sólo por el atributo `disabled`', async () => {
    // LA TRAMPA DE LA CORRIDA G: `fireEvent.click` sobre un botón `disabled`
    // **no despacha `onClick`**, así que un test que sólo mirara el atributo
    // pasaría verde aunque el gate no existiera. Por eso se afirman las dos
    // cosas, y la que importa es la segunda.
    const onGuardar = pintar();
    await llenarBasico();
    capturar(/NSS/, '1234567890'); // 10 dígitos

    await waitFor(() => expect(botonAlta()).toHaveProperty('disabled', true));
    fireEvent.click(botonAlta());
    expect(onGuardar).not.toHaveBeenCalled();
  });

  it('el mensaje de longitud cierra el atajo de completar el dígito a mano', async () => {
    pintar();
    await llenarBasico();
    capturar(/NSS/, '1234567890');

    const alerta = await waitFor(() =>
      screen.getAllByRole('alert').find((a) => a.textContent?.includes('11 dígitos')),
    );
    expect(alerta?.textContent).toContain('no lo completes a mano');
  });

  it('el dígito verificador ADVIERTE pero SÍ deja guardar', async () => {
    // La desviación consciente del enunciado de R-03. Bloquear aquí empujaría a
    // teclear un NSS que pase Luhn — un número inventado junto a datos reales.
    const onGuardar = pintar();
    await llenarBasico();
    capturar(/NSS/, '12345678900'); // 11 dígitos, verificador 0 en vez de 3

    // Se anuncia como `status`, no como `alert`: una advertencia que se anuncia
    // como error entrena a ignorarlas.
    await waitFor(() =>
      expect(screen.getByRole('status').textContent).toContain('no coincide'),
    );
    await waitFor(() => expect(botonAlta()).toHaveProperty('disabled', false));

    fireEvent.click(botonAlta());
    await waitFor(() => expect(onGuardar).toHaveBeenCalled());
    expect(onGuardar.mock.calls[0][0].nss).toBe('12345678900');
  });

  it('guarda el NSS normalizado: se captura con separadores, se guarda en dígitos', async () => {
    const onGuardar = pintar();
    await llenarBasico();
    capturar(/NSS/, '12-34 5678 903');

    await waitFor(() => expect(botonAlta()).toHaveProperty('disabled', false));
    fireEvent.click(botonAlta());
    await waitFor(() => expect(onGuardar).toHaveBeenCalled());
    expect(onGuardar.mock.calls[0][0].nss).toBe('12345678903');
  });
});

describe('O-03 · las prestaciones del PATRÓN llegan al motor', () => {
  /**
   * POR QUÉ ESTA SECCIÓN EXISTE
   * ---------------------------
   * Un revisor de motor borró `tabla_vacaciones: tablaVacaciones` del request
   * de SBC y **las 543 pruebas del front quedaron verdes**. Con esa línea
   * muerta, el formulario de "Vacaciones por antigüedad" de Configuración de
   * empresa queda **decorativo**: se captura, se guarda, y el SBC sigue
   * saliendo con los días de ley.
   *
   * Es literalmente el modo de falla contra el que O-03 se defiende en su
   * propio mensaje de commit, y no tenía una sola prueba.
   */

  const PARAMETROS: ParametrosSalariales = {
    dias_aguinaldo: 30,
    prima_vacacional: '0.50',
    tabla_vacaciones: [[1, 15], [3, 20], [10, 30]],
    horario: {
      hora_entrada: '08:00',
      hora_salida: '17:00',
      tolerancia_minutos: 15,
      dias_laborables: [0, 1, 2, 3, 4],
    },
  };

  it('la escala de vacaciones viaja ENTERA en el cuerpo de /nomina/sbc', async () => {
    pintar({ parametros: PARAMETROS });
    await llenarBasico();

    const enviado = integrarSBC.mock.calls[integrarSBC.mock.calls.length - 1][0] as Record<string, unknown>;
    expect(enviado.tabla_vacaciones).toEqual(PARAMETROS.tabla_vacaciones);
  });

  it('y el front NO resuelve los días él mismo', async () => {
    /**
     * Manda la tabla y la antigüedad; los días aplicados los devuelve el
     * backend en `dias_vacaciones_aplicados`. Buscar el renglón aquí sería una
     * segunda implementación de la misma búsqueda, y el centinela
     * `dias_vacaciones: 0` ("los de ley") sería ambiguo con una tabla presente.
     */
    pintar({ parametros: PARAMETROS });
    await llenarBasico();

    const enviado = integrarSBC.mock.calls[integrarSBC.mock.calls.length - 1][0] as Record<string, unknown>;
    expect(enviado).toHaveProperty('anios_servicio_cumplidos');
    // El centinela sigue siendo 0: quien decide es el backend.
    expect(enviado.dias_vacaciones).toBe(0);
  });

  it('el aguinaldo y la prima del patrón son el DEFAULT del alta', async () => {
    // 30 días y 50 %, no el mínimo de ley: es la política de la empresa, que es
    // lo que aplica a casi todos. Se puede pisar para un caso particular.
    pintar({ parametros: PARAMETROS });
    await llenarBasico();

    const enviado = integrarSBC.mock.calls[integrarSBC.mock.calls.length - 1][0] as Record<string, unknown>;
    expect(enviado.dias_aguinaldo).toBe(30);
    expect(enviado.prima_vacacional).toBe('0.50');
  });

  it('sin parámetros manda el mínimo de ley, como antes de O-03', async () => {
    // El modo despacho no tiene una empresa única de la que sacarlos, y ahí el
    // comportamiento no puede cambiar.
    pintar();
    await llenarBasico();

    const enviado = integrarSBC.mock.calls[integrarSBC.mock.calls.length - 1][0] as Record<string, unknown>;
    expect(enviado.dias_aguinaldo).toBe(15);
    expect(enviado.prima_vacacional).toBe('0.25');
    expect(enviado.tabla_vacaciones).toEqual([]);
  });
});
