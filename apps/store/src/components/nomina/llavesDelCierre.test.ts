/**
 * Las dos llaves no se confunden en el borde del cierre (G-02).
 *
 * POR QUÉ IMPORTA TANTO
 * ---------------------
 * `cerrar_periodo` casa las checadas por la llave del CHECADOR y los recibos se
 * indexan por la del CÁLCULO. Mientras coincidieron —y coinciden para los 25 de
 * la semilla, porque el backend les pone `employee_no = empleado_no`— el error
 * era invisible. En cuanto G-03 deja dar de alta a alguien con un número de
 * aparato distinto, mandar la llave equivocada hace que no se encuentre ni una
 * de sus checadas: **falta todo el periodo, menos días pagados, menor base de
 * cuotas y menor ISR**, y sus checadas reales salen como "desconocidas", que el
 * contador lee como "nadie sembró a este cliente".
 *
 * Por eso casi todos los casos de abajo usan llaves DISTINTAS: con llaves
 * iguales, la traducción es la identidad y no prueba nada.
 */

import { describe, expect, it } from 'vitest';
import {
  hayLlavesDistintas,
  incidenciasConLlaveDeCalculo,
  llavesParaElCierre,
} from './llavesDelCierre';
import type { EmpleadoCartera } from '../../services/carteraApi';
import type { IncidenciasEmpleado } from '../../services/nominaDemoApi';

function emp(empleado_no: string, employee_no: string | null): EmpleadoCartera {
  return {
    empleado_no,
    nombre: `EMPLEADO ${empleado_no}`,
    puesto: '',
    salario_diario: '316.00',
    salario_diario_integrado: '331.58',
    zona: 'general',
    fecha_alta: null,
    tipo_contrato: 'indeterminado',
    prestaciones: { dias_aguinaldo: 15, dias_vacaciones: 0, prima_vacacional: '0.25' },
    nss: '',
    employee_no,
    enrolamiento: 'enrolado',
  };
}

function inc(empleado_no: string, faltas = 0): IncidenciasEmpleado {
  return {
    empleado_no,
    dias_periodo: 16,
    dias_laborables: 11,
    dias_trabajados: 11 - faltas,
    faltas,
    dias_ausentismo: faltas,
    retardos: 0,
    dias_cotizados: 16 - faltas,
  };
}

describe('llavesParaElCierre · lo que se le manda al cierre', () => {
  it('con cartera manda la llave del APARATO, no la interna', () => {
    // El caso que delata el bug: si esto devolviera 'E-07', el cierre buscaría
    // checadas de 'E-07' cuando el Hikvision manda '7'.
    expect(llavesParaElCierre([], [emp('E-07', '7')])).toEqual(['7']);
  });

  it('deja fuera a los no vinculados', () => {
    // Sin llave de aparato no hay nada que casar, y `plantillaDeNomina` ya los
    // excluyó del cálculo: mandarlos aquí los reportaría como desconocidos.
    expect(llavesParaElCierre([], [emp('E-01', '1'), emp('N-01', null)])).toEqual(['1']);
  });

  it('SIN cartera manda la plantilla del catálogo: es el camino de la demo', () => {
    // Cuando Firestore no está desplegado, la app corre sobre el catálogo del
    // backend. Devolver [] aquí dejaba el cierre sin un solo empleado —faltas
    // para todos y la tabla en blanco—, o sea rompía la demo. Lo cazó
    // `NominaPorCliente.test.tsx` antes de que llegara a ningún lado.
    expect(llavesParaElCierre([{ empleado_no: 'cafeteria-1' }], null)).toEqual(['cafeteria-1']);
  });

  it('con cartera vacía no manda nada, y eso NO es lo mismo que sin cartera', () => {
    // `[]` es un cliente sin empleados; `null` es "todavía no llegó".
    expect(llavesParaElCierre([{ empleado_no: 'X' }], [])).toEqual([]);
  });
});

describe('incidenciasConLlaveDeCalculo · la vuelta', () => {
  it('traduce la llave del aparato a la del cálculo', () => {
    // `calcular-periodo` responde 422 ante una incidencia cuyo `empleado_no` no
    // esté en la plantilla, así que sin esta vuelta el cálculo entero falla.
    const [i] = incidenciasConLlaveDeCalculo([inc('7')], [emp('E-07', '7')]);
    expect(i.empleado_no).toBe('E-07');
  });

  it('conserva los números de la incidencia intactos', () => {
    // Se traduce la llave, no el contenido: faltas y días alimentan la base de
    // cuotas y los días pagados.
    const [i] = incidenciasConLlaveDeCalculo([inc('7', 2)], [emp('E-07', '7')]);
    expect(i.faltas).toBe(2);
    expect(i.dias_trabajados).toBe(9);
    expect(i.dias_cotizados).toBe(14);
  });

  it('descarta una incidencia cuya llave no corresponde a nadie', () => {
    // Es una checada de un número no dado de alta; el backend ya la reporta en
    // `empleados_desconocidos`. Colarla daría un 422 o un recibo a nombre de un
    // número.
    expect(incidenciasConLlaveDeCalculo([inc('999')], [emp('E-07', '7')])).toEqual([]);
  });

  it('traduce varias y respeta a quién le toca cada una', () => {
    // El error que importa no es perder una incidencia: es cruzarlas. Aquí las
    // llaves están invertidas a propósito respecto del orden interno.
    const traducidas = incidenciasConLlaveDeCalculo(
      [inc('7', 3), inc('1', 0)],
      [emp('E-01', '1'), emp('E-07', '7')],
    );
    const porEmpleado = Object.fromEntries(traducidas.map((i) => [i.empleado_no, i.faltas]));
    expect(porEmpleado).toEqual({ 'E-07': 3, 'E-01': 0 });
  });

  it('con llaves iguales es la identidad: la demo no cambia', () => {
    // Los 25 de la semilla tienen `employee_no === empleado_no`. Si esto
    // alterara algo, la demo cambiaría de números al mergear.
    const antes = [inc('E-01', 1), inc('E-02')];
    expect(incidenciasConLlaveDeCalculo(antes, [emp('E-01', 'E-01'), emp('E-02', 'E-02')]))
      .toEqual(antes);
  });

  it('un no vinculado no aparece por más que llegue una incidencia suya', () => {
    expect(incidenciasConLlaveDeCalculo([inc('N-01')], [emp('N-01', null)])).toEqual([]);
  });
});

describe('hayLlavesDistintas', () => {
  it('es false para la semilla, donde las dos llaves coinciden', () => {
    expect(hayLlavesDistintas([emp('E-01', 'E-01')])).toBe(false);
  });

  it('es true en cuanto alguien tiene un número de aparato propio', () => {
    expect(hayLlavesDistintas([emp('E-01', 'E-01'), emp('E-07', '7')])).toBe(true);
  });

  it('un no vinculado no cuenta como llave distinta', () => {
    // No tiene llave de aparato: no es que difiera, es que no hay.
    expect(hayLlavesDistintas([emp('N-01', null)])).toBe(false);
  });
});
