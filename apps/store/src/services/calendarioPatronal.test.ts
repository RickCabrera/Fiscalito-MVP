/**
 * Lógica pura del calendario patronal de E-07 (`agrupar`, `estadoDeFecha`).
 *
 * Vivía en `CalendarioPatronalPage.test.tsx`. Desde P3-10 esa pantalla es el calendario
 * unificado de la cartera (fechas del backend, `/calendario/cartera`); estas funciones siguen
 * en `services/calendarioPatronal.ts` y sus pruebas se mudan aquí sin cambios.
 */

import { describe, expect, it } from 'vitest';
import type { ObligacionPatronal } from './despachoApi';
import { agrupar, estadoDeFecha } from './calendarioPatronal';

/** 15 de abril de 2026: el ISR de marzo está próximo y las cuotas también. */
const HOY = new Date(2026, 3, 15);

function obligacion(over: Partial<ObligacionPatronal> = {}): ObligacionPatronal {
  return {
    cliente_id: 'demo',
    cliente_nombre: 'Cliente Uno',
    clave: 'imss_mensual',
    nombre: 'Cuotas IMSS de marzo 2026',
    descripcion: 'Entero mensual.',
    fecha_limite: '2026-04-20',
    periodicidad: 'mensual',
    periodo_cubierto: 'marzo 2026',
    fundamento: 'Art. 39 LSS',
    regimen_de_plazo: 'imss',
    condicional: false,
    nota: '',
    ...over,
  };
}

describe('estadoDeFecha', () => {
  it('clasifica contra el `hoy` que recibe, no contra el reloj', () => {
    expect(estadoDeFecha('2026-04-20', HOY)).toBe('proxima');
    expect(estadoDeFecha('2026-03-17', HOY)).toBe('vencida');
    expect(estadoDeFecha('2026-12-19', HOY)).toBe('futura');
  });

  it('el mismo día NO está vencido', () => {
    /** Vence hoy: todavía se puede presentar. Marcarlo vencido es un error. */
    expect(estadoDeFecha('2026-04-15', HOY)).toBe('proxima');
  });
});

describe('agrupar', () => {
  it('junta la misma obligación de varios clientes en un renglón', () => {
    const grupos = agrupar([
      obligacion({ cliente_nombre: 'Uno' }),
      obligacion({ cliente_id: 'b', cliente_nombre: 'Dos' }),
    ]);
    expect(grupos).toHaveLength(1);
    const [[fecha, renglones]] = grupos;
    expect(fecha).toBe('2026-04-20');
    expect(renglones).toHaveLength(1);
    expect(renglones[0].clientes).toEqual(['Uno', 'Dos']);
  });

  it('NO junta dos que difieren en `condicional` o en `nota`', () => {
    /**
     * EL CASO QUE VALE ESTE TEST. Hoy los tres calendarios son idénticos, pero
     * `condicional` y `nota` dependen de datos por cliente en cuanto F1-09 los
     * registre. Sin ellos en la clave, dos clientes con distinta personalidad
     * jurídica se colapsarían en un renglón y uno de los dos textos
     * desaparecería sin que nada fallara.
     */
    const grupos = agrupar([
      obligacion({ clave: 'ptu_moral', condicional: true, nota: 'no consta' }),
      obligacion({ clave: 'ptu_moral', cliente_id: 'b', condicional: false, nota: '' }),
    ]);
    expect(grupos[0][1]).toHaveLength(2);
  });

  it('devuelve las fechas en orden ascendente', () => {
    const grupos = agrupar([
      obligacion({ fecha_limite: '2026-05-30' }),
      obligacion({ fecha_limite: '2026-04-17' }),
    ]);
    expect(grupos.map(([f]) => f)).toEqual(['2026-04-17', '2026-05-30']);
  });
});

