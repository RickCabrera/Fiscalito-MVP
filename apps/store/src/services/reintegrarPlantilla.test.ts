/**
 * Reintegrar la plantilla: el hueco entre O-03 y la nómina. (O-cierre)
 *
 * O-03 dejó cambiar el aguinaldo, la prima vacacional y la tabla de vacaciones,
 * y su criterio ("cambiar aguinaldo 15→30 cambia el factor y el SBC") se cumplía
 * **al pie de la letra**: el motor sí cambia el factor, y un alta nueva sí lo
 * usa. Lo que no ocurría es lo que el patrón espera: que la plantilla que ya
 * existe se reintegre.
 *
 * Y la dirección del error es la mala. `ModalEmpleado` es el único escritor de
 * `salario_diario_integrado`, `plantillaDeNomina` manda el SDI guardado y el
 * motor no lo recalcula (§D9). Subir el aguinaldo y correr la nómina daba
 * cuotas **subintegradas, en silencio**, con recibo creíble.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { EmpleadoCartera, ParametrosSalariales } from './carteraApi';

const integrarSBC = vi.fn();
vi.mock('./carteraApi', async () => {
  const real = await vi.importActual<typeof import('./carteraApi')>('./carteraApi');
  return { ...real, integrarSBC: (...args: unknown[]) => integrarSBC(...args) };
});

const { reintegrarPlantilla, antiguedadCumplida } = await import('./reintegrarPlantilla');

function empleado(no: string, sdi: string, fechaAlta: string | null = '2020-03-01'): EmpleadoCartera {
  return {
    empleado_no: no,
    nombre: `PERSONA ${no}`,
    puesto: '',
    salario_diario: '500.00',
    salario_diario_integrado: sdi,
    zona: 'general',
    fecha_alta: fechaAlta,
    tipo_contrato: 'indeterminado',
    prestaciones: { dias_aguinaldo: 15, dias_vacaciones: 0, prima_vacacional: '0.25' },
    nss: '01010101011',
    employee_no: no,
    enrolamiento: 'enrolado',
  };
}

const PARAMETROS: ParametrosSalariales = {
  dias_aguinaldo: 30,
  prima_vacacional: '0.25',
  tabla_vacaciones: [],
  horario: {
    hora_entrada: '08:00',
    hora_salida: '17:00',
    tolerancia_minutos: 15,
    dias_laborables: [0, 1, 2, 3, 4],
  },
};

/** Respuesta del motor con el SBC pedido. */
function sbc(valor: string) {
  return {
    factor: '1.0986', dias_vacaciones_aplicados: 14, sbc_sin_acotar: valor, sbc: valor,
    piso_aplicado: false, tope_aplicado: false, piso: '315.04', tope: '2932.75',
    fundamento: 'Arts. 27, 28 y 30 fr. I LSS',
  };
}

beforeEach(() => {
  integrarSBC.mockReset();
});

describe('el SBC lo vuelve a calcular el MOTOR, uno por uno', () => {
  it('le pregunta al motor por cada empleado, no una vez para todos', async () => {
    // La antigüedad cumplida mueve los días de vacaciones y con ellos el
    // factor: un atajo que calculara el factor una vez daría mal a quien acaba
    // de cumplir años de servicio.
    integrarSBC.mockResolvedValue(sbc('540.00'));
    await reintegrarPlantilla([empleado('E-01', '524.65'), empleado('E-02', '524.65')], PARAMETROS);
    expect(integrarSBC).toHaveBeenCalledTimes(2);
  });

  it('manda los parámetros vigentes, no los guardados en la ficha del empleado', async () => {
    // La ficha del empleado trae `dias_aguinaldo: 15`. Lo que manda son los 30
    // del patrón — que es el cambio que hay que propagar.
    integrarSBC.mockResolvedValue(sbc('540.00'));
    await reintegrarPlantilla([empleado('E-01', '524.65')], PARAMETROS);
    expect(integrarSBC.mock.calls[0][0]).toMatchObject({
      dias_aguinaldo: 30,
      prima_vacacional: '0.25',
      salario_diario: '500.00',
      zona: 'general',
    });
  });

  it('el front NO calcula el factor: sólo consume el SBC que devolvió el motor', async () => {
    integrarSBC.mockResolvedValue(sbc('612.34'));
    const r = await reintegrarPlantilla([empleado('E-01', '524.65')], PARAMETROS);
    expect(r.empleados[0].salario_diario_integrado).toBe('612.34');
  });
});

describe('el reporte dice quién cambió y de cuánto a cuánto', () => {
  it('sólo lista a los que de verdad cambiaron', async () => {
    integrarSBC
      .mockResolvedValueOnce(sbc('540.00')) // cambia
      .mockResolvedValueOnce(sbc('524.65')); // ya estaba integrado
    const r = await reintegrarPlantilla(
      [empleado('E-01', '524.65'), empleado('E-02', '524.65')],
      PARAMETROS,
    );
    expect(r.revisados).toBe(2);
    expect(r.cambios).toHaveLength(1);
    expect(r.cambios[0]).toMatchObject({ empleadoNo: 'E-01', anterior: '524.65', nuevo: '540.00' });
  });

  it('sin cambios el reporte lo dice, en vez de quedarse callado', async () => {
    integrarSBC.mockResolvedValue(sbc('524.65'));
    const r = await reintegrarPlantilla([empleado('E-01', '524.65')], PARAMETROS);
    expect(r.cambios).toEqual([]);
    expect(r.revisados).toBe(1);
  });
});

describe('un empleado que el motor rechaza queda EXACTAMENTE como estaba', () => {
  /**
   * Una plantilla a medio reintegrar —unos al valor nuevo, otros al viejo, y
   * nadie avisado— es peor que no haber reintegrado: la nómina saldría con dos
   * criterios mezclados y el recibo no lo diría.
   */
  it('no se le pisa el SDI y sale en `fallidos` con el motivo', async () => {
    integrarSBC
      .mockResolvedValueOnce(sbc('540.00'))
      .mockRejectedValueOnce(new Error('Salario diario inválido'));
    const r = await reintegrarPlantilla(
      [empleado('E-01', '524.65'), empleado('E-02', '499.99')],
      PARAMETROS,
    );
    expect(r.cambios).toHaveLength(1);
    expect(r.fallidos).toHaveLength(1);
    expect(r.fallidos[0].fallo).toMatch(/Salario diario inválido/);
    // El que falló conserva su SDI: no se pisa con nada.
    expect(r.empleados.find((e) => e.empleado_no === 'E-02')!.salario_diario_integrado).toBe(
      '499.99',
    );
  });

  it('un fallo no aborta la corrida: los demás sí se reintegran', async () => {
    integrarSBC
      .mockRejectedValueOnce(new Error('caída'))
      .mockResolvedValueOnce(sbc('540.00'));
    const r = await reintegrarPlantilla(
      [empleado('E-01', '524.65'), empleado('E-02', '524.65')],
      PARAMETROS,
    );
    expect(r.cambios.map((c) => c.empleadoNo)).toEqual(['E-02']);
  });
});

describe('la antigüedad cumplida', () => {
  it('cuenta años cumplidos, no calendario', () => {
    // Alta el 1-mar-2020; al 28-feb-2026 todavía son 5, no 6.
    expect(antiguedadCumplida('2020-03-01', new Date(2026, 1, 28))).toBe(5);
    expect(antiguedadCumplida('2020-03-01', new Date(2026, 2, 1))).toBe(6);
  });

  it('sin fecha de alta es 0, no un NaN que viaje al motor', () => {
    expect(antiguedadCumplida(null, new Date(2026, 5, 1))).toBe(0);
    expect(antiguedadCumplida('no-es-fecha', new Date(2026, 5, 1))).toBe(0);
  });

  it('nunca es negativa', () => {
    // Un alta futura es dato malo, pero mandar -1 al motor es peor.
    expect(antiguedadCumplida('2030-01-01', new Date(2026, 5, 1))).toBe(0);
  });

  it('viaja al motor: es lo que mueve los días de vacaciones', async () => {
    integrarSBC.mockResolvedValue(sbc('540.00'));
    await reintegrarPlantilla([empleado('E-01', '524.65', '2020-03-01')], PARAMETROS, new Date(2026, 5, 1));
    expect(integrarSBC.mock.calls[0][0].anios_servicio_cumplidos).toBe(6);
  });
});

describe('no escribe nada: guardar es de quien llama', () => {
  it('devuelve la plantilla nueva sin tocar la que le pasaron', async () => {
    // Es lo que permite enseñar el cambio ANTES de aplicarlo — y reintegrar es
    // un aviso de modificación de salario ante el IMSS por cada empleado.
    integrarSBC.mockResolvedValue(sbc('540.00'));
    const original = [empleado('E-01', '524.65')];
    const r = await reintegrarPlantilla(original, PARAMETROS);
    expect(original[0].salario_diario_integrado).toBe('524.65');
    expect(r.empleados[0].salario_diario_integrado).toBe('540.00');
  });
});
