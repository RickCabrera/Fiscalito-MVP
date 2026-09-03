/**
 * Los centavos y el SBC, medidos de frente. (O-04)
 *
 * `cuadre.test.ts` los ejercita de refilón: si `aCentavos` redondeara, algún
 * total dejaría de cuadrar. Pero "de refilón" no defiende **la decisión**, que
 * es lo que el docstring de `dinero.ts` argumenta largo: `aCentavos('5056.005')`
 * **levanta**, no redondea, porque el motor ya redondea por concepto al estilo
 * SUA (`docs/decisiones-nomina.md` §D1) y un tercer decimal significa que algo
 * cambió aguas arriba.
 *
 * Lo señaló el revisor del cuadre con mutación: aflojar el patrón a `\d{1,3}` o
 * cambiar el parseo por `Math.round(Number(x) * 100)` dejaba la suite entera en
 * verde. El comportamiento era correcto y estaba indefenso.
 */

import { describe, expect, it } from 'vitest';
import { aCentavos, deCentavos, sumaCentavos } from './dinero';
import { sbcSeisPosiciones, fechaDDMMAAAA } from './registroFijo';

describe('aCentavos parsea la cadena; no la redondea', () => {
  it.each([
    ['0.00', 0],
    ['0.01', 1],
    ['0.99', 99],
    ['5056.07', 505607],
    ['13106.11', 1310611],
    // Un solo decimal es una cadena legítima: "5056.5" son 5056 pesos 50 centavos.
    ['5056.5', 505650],
    // Sin decimales también.
    ['400', 40000],
    ['-125.99', -12599],
  ])('%s → %i centavos', (entrada, esperado) => {
    expect(aCentavos(entrada)).toBe(esperado);
  });

  it.each([
    // EL caso del docstring: un tercer decimal NO se redondea a la callada.
    ['5056.005'],
    ['5056.0000'],
    // Separador de miles: viene de una cadena formateada para leer, no de un
    // importe. Aceptarlo invitaría a exportar lo que se imprime.
    ['1,234.56'],
    // Notación científica: `Number('1e3')` da 1000 sin protestar.
    ['1e3'],
    ['.50'],
    [''],
    ['abc'],
    ['12.3.4'],
  ])('%s LEVANTA en vez de inventar un redondeo', (entrada) => {
    expect(() => aCentavos(entrada)).toThrow();
  });

  it('el error dice por qué, citando la regla del motor', () => {
    // Un "importe inválido" pelón manda a leer el código; esto manda a §D1.
    expect(() => aCentavos('5056.005')).toThrow(/tercer decimal/);
  });
});

describe('deCentavos es el camino de vuelta exacto', () => {
  it.each(['0.00', '0.07', '9.90', '5056.07', '13106.11', '-125.99'])(
    'ida y vuelta de %s no pierde nada',
    (importe) => {
      expect(deCentavos(aCentavos(importe))).toBe(importe);
    },
  );

  it('rellena el centavo suelto en vez de escribir "5056.7"', () => {
    expect(deCentavos(505670)).toBe('5056.70');
    expect(deCentavos(7)).toBe('0.07');
  });
});

describe('sumaCentavos suma enteros, y por eso no arrastra float', () => {
  it('0.1 + 0.2 da exactamente 0.30', () => {
    // El caso de manual, y la razón entera de que este módulo exista.
    expect(deCentavos(sumaCentavos(['0.10', '0.20']))).toBe('0.30');
  });

  it('tres importes con centavos que no son redondos', () => {
    expect(sumaCentavos(['5056.07', '4838.93', '3211.11'])).toBe(1310611);
  });

  it('un importe malo en la lista LEVANTA: no se salta en silencio', () => {
    expect(() => sumaCentavos(['5056.07', '4838.939'])).toThrow();
  });
});

describe('sbcSeisPosiciones: 4 pesos + 2 centavos, punto implícito', () => {
  /** Los bordes, con el ejemplo literal de la guía DISP-MAG del IMSS. */
  it.each([
    [5, '000005'],
    [999, '000999'],
    // El de la guía: $526.05.
    [52605, '052605'],
    [123456, '123456'],
    [999999, '999999'],
  ])('%i centavos → %s', (centavos, esperado) => {
    expect(sbcSeisPosiciones(centavos)).toBe(esperado);
  });

  it('siempre mide 6, que es lo que el layout reserva', () => {
    for (const c of [0, 1, 9999, 52605, 999999]) {
      expect(sbcSeisPosiciones(c)).toHaveLength(6);
    }
  });

  it('un SBC que no cabe LEVANTA en vez de truncarse', () => {
    // Truncar $10,000.00 a "000000" declara un salario distinto al real en el
    // documento que se le entrega al IMSS.
    expect(() => sbcSeisPosiciones(1000000)).toThrow(/no cabe/);
  });

  it('un SBC negativo LEVANTA', () => {
    expect(() => sbcSeisPosiciones(-1)).toThrow(/negativo/);
  });
});

describe('fechaDDMMAAAA', () => {
  it('invierte el ISO y quita las diagonales', () => {
    // Sin diagonales a propósito: es un registro de posiciones fijas y el campo
    // mide 8. Es la desviación declarada del enunciado, que pedía DD/MM/AAAA.
    expect(fechaDDMMAAAA('2026-08-20')).toBe('20082026');
    expect(fechaDDMMAAAA('2026-01-01')).toBe('01012026');
  });

  it('mide 8 posiciones', () => {
    expect(fechaDDMMAAAA('2026-12-31')).toHaveLength(8);
  });

  it.each(['20/08/2026', '2026-8-20', '', '20-08-2026'])(
    'lo que no es ISO LEVANTA: %s',
    (mala) => {
      expect(() => fechaDDMMAAAA(mala)).toThrow(/ISO/);
    },
  );
});
