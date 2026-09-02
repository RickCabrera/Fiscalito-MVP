/**
 * La nota de "días cotizados" dice lo que el motor hace, en positivo y acotada.
 *
 * El texto viejo —"el ausentismo no reduce Enfermedades y Maternidad"— era
 * correcto y se leía al revés: en un proyector pasaba por "EyM no se toma en
 * cuenta", que es lo contrario. Estos tests fijan las tres propiedades que el
 * texto nuevo tiene que conservar, no su redacción exacta:
 *
 * 1. Dice, en afirmativo, que EyM se cobra íntegro.
 * 2. Está ACOTADO a ausencias de hasta 7 días. La fr. II del Art. 31 libera al
 *    patrón de todas las cuotas al exceder ese plazo y el motor no lo
 *    implementa (§D3): sigue cobrando 30 días de EyM con 20 de ausencia, de más
 *    y a propósito. Una frase incondicional sería clara y falsa.
 * 3. Nombra los ramos que SÍ descuentan, para que "cada ramo usa su propia
 *    base" no quede como una abstracción.
 */

import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import TablaIncidencias from './TablaIncidencias';
import type { CierrePeriodo, EmpleadoDemo } from '../../services/nominaDemoApi';

// `globals` no esta activo en vitest.config.ts, asi que el auto-cleanup de
// Testing Library no corre: sin esto, el segundo render convive con el primero
// y `getByText` encuentra dos.
afterEach(cleanup);

const EMPLEADOS: EmpleadoDemo[] = [{ empleado_no: 'E-01', nombre: 'ANA LOPEZ' }];

const CIERRE: CierrePeriodo = {
  cliente: 'demo',
  periodo: { inicio: '2026-08-16', fin: '2026-08-31' },
  incidencias: [
    {
      empleado_no: 'E-01',
      dias_periodo: 16,
      dias_laborables: 11,
      dias_trabajados: 10,
      faltas: 1,
      dias_ausentismo: 1,
      retardos: 2,
      dias_cotizados: 15,
    },
  ],
  empleados_desconocidos: [],
};

function pintar(cierre: CierrePeriodo = CIERRE) {
  return render(<TablaIncidencias cierre={cierre} empleados={EMPLEADOS} />);
}

/** El texto de la nota al pie, sin los saltos de línea del JSX. */
function notaAlPie(): string {
  const nota = document.querySelector('section > p:last-of-type');
  return (nota?.textContent ?? '').replace(/\s+/g, ' ');
}

describe('TablaIncidencias · nota de días cotizados', () => {
  it('afirma que Enfermedades y Maternidad se cobra íntegro', () => {
    pintar();
    expect(notaAlPie()).toContain('Enfermedades y Maternidad se cobra íntegro');
  });

  it('acota la afirmación a ausencias de hasta 7 días AL MES (Art. 31 fr. II, §D3)', () => {
    // "al mes" no sobra: §D3 fija el umbral por mes y esta tabla muestra una
    // quincena. Sin esas dos palabras, el lector lo lee como umbral del periodo.
    pintar();
    const nota = notaAlPie();
    expect(nota).toContain('hasta 7 días al mes');
    expect(nota).toContain('Art. 31 LSS');
  });

  it('no vuelve a la redacción en negativo que se leía al revés', () => {
    // "el ausentismo no reduce Enfermedades y Maternidad" es la frase que
    // Ricardo reportó como ilegible. Si alguien la reintroduce, esto lo caza.
    // OJO: sin `pintar()` este test pasaría contra un documento vacío, que es
    // el modo en que una aserción negativa se vuelve decorativa.
    pintar();
    const nota = notaAlPie();
    expect(nota).not.toBe('');
    expect(nota).not.toMatch(/no reduce Enfermedades/i);
  });

  it('nombra los SEIS ramos que sí descuentan los días de ausencia', () => {
    // Seis, no cinco. La frase está construida como partición —EyM no reduce /
    // estos sí—, así que omitir uno lo empuja al lado de EyM. Cesantía y Vejez
    // es el que se cae solo: vive en `ceav.py`, no en `CUOTAS_RAMOS`, pero toma
    // el mismo default `se_reduce_por_ausentismo=True` y **aparece en pantalla**
    // en el desglose de ramos del recibo, con sus días ya reducidos.
    pintar();
    const nota = notaAlPie();
    for (const ramo of [
      'Invalidez y Vida',
      'Guarderías',
      'Retiro',
      'Cesantía y Vejez',
      'Infonavit',
      'Riesgos de Trabajo',
    ]) {
      expect(nota).toContain(ramo);
    }
  });

  it('sigue diciendo que el número no alimenta ningún cálculo', () => {
    pintar();
    expect(notaAlPie()).toContain('no alimenta ningún cálculo');
  });

  it('el tooltip de la columna dice lo mismo que la nota', () => {
    pintar();
    const encabezado = screen.getByText(/Días cotizados/);
    expect(encabezado.getAttribute('title')).toContain('íntegro');
  });
});

describe('TablaIncidencias · lo que la tabla ya hacía', () => {
  it('pinta el nombre del empleado y sus incidencias', () => {
    pintar();
    expect(screen.getByText('ANA LOPEZ')).toBeTruthy();
  });

  it('avisa de las checadas de empleados que no están en la plantilla', () => {
    // Herencia de D-04: sin este aviso, un alta con el employeeNo equivocado
    // en el checador se ve como "faltaron todos" y nadie sabe por qué.
    pintar({ ...CIERRE, empleados_desconocidos: ['E-99'] });
    expect(screen.getByRole('alert').textContent).toContain('E-99');
  });
});
