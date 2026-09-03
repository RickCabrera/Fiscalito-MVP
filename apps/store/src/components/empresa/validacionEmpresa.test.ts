/**
 * La validación y la conversión de la Configuración de empresa. (O-01)
 *
 * POR QUÉ ESTO MERECE SU ARCHIVO
 * ------------------------------
 * `aFraccion` y `aPorcentaje` dividen y multiplican por 100 **la prima de
 * Riesgos de Trabajo**, que entra directo a `cuotas.py`. Un factor de 100 mal
 * puesto no rompe nada visible: produce una cuota patronal cien veces mayor o
 * cien veces menor, con un recibo perfectamente creíble. Es el mismo modo de
 * falla que `ClienteCarteraSchema` documenta para capturar `5.4355` en vez de
 * `0.054355`.
 *
 * Y se puede medir **sin jsdom**, que es la razón por la que estas funciones se
 * extrajeron del componente: una regla probada a través de un formulario se
 * prueba peor.
 */

import { describe, expect, it } from 'vitest';
import { aFraccion, aPorcentaje, validar } from './validacionEmpresa';

describe('la prima se captura en porcentaje y se guarda en fracción', () => {
  it('ida y vuelta con la prima del caso real, sin perder dígitos', () => {
    // 1.13065 % es la prima del cliente de las fixtures S-04. Un `toFixed(2)`
    // en el camino la dejaría en 1.13 % y movería la cuota de RT.
    expect(aPorcentaje('0.0113065')).toBe('1.13065');
    expect(aFraccion('1.13065')).toBe('0.0113065');
  });

  it('ida y vuelta con la prima mínima de ley (0.5 %)', () => {
    expect(aPorcentaje('0.005')).toBe('0.5');
    expect(aFraccion('0.5')).toBe('0.005');
  });

  it('ida y vuelta con la prima máxima de ley (15 %)', () => {
    expect(aPorcentaje('0.15')).toBe('15');
    expect(aFraccion('15')).toBe('0.15');
  });

  it('la fracción vacía se queda vacía: no se convierte en 0', () => {
    // Un `0` aquí sería afirmar que la empresa declaró prima cero, que no
    // existe. Vacío significa "no capturada", y `faltantesDeLaEmpresa` lo usa.
    expect(aPorcentaje('')).toBe('');
    expect(aPorcentaje('   ')).toBe('');
  });

  it('una fracción ilegible no explota ni inventa un número', () => {
    expect(aPorcentaje('no soy un número')).toBe('');
  });
});

describe('los mínimos y máximos de ley rechazan, con el motivo', () => {
  const OK = { razon: 'Orca Ordorica', rfc: '', rp: '', prima: '1.13065' };

  function errores(over: Partial<typeof OK> = {}) {
    const v = { ...OK, ...over };
    return validar(v.razon, v.rfc, v.rp, v.prima);
  }

  it('lo válido no produce ningún error', () => {
    expect(errores()).toEqual({});
  });

  it('sin razón social no se puede: es lo que sale impreso en los recibos', () => {
    expect(errores({ razon: '   ' }).razonSocial).toMatch(/obligatoria/);
  });

  it('sin prima no se pueden calcular las cuotas patronales', () => {
    expect(errores({ prima: '' }).primaPct).toMatch(/cuotas patronales/);
  });

  it('por debajo del 0.5 % (Arts. 72 y 73 LSS) rechaza', () => {
    expect(errores({ prima: '0.4' }).primaPct).toMatch(/Arts. 72 y 73 LSS/);
  });

  it('por encima del 15 % rechaza', () => {
    expect(errores({ prima: '15.1' }).primaPct).toMatch(/Arts. 72 y 73 LSS/);
  });

  it('los extremos exactos SÍ se aceptan: el rango es cerrado', () => {
    expect(errores({ prima: '0.5' }).primaPct).toBeUndefined();
    expect(errores({ prima: '15' }).primaPct).toBeUndefined();
  });

  it('EL CASO CARO: capturar la fracción en el campo de porcentaje rechaza', () => {
    // `0.0054355` en un campo que pide porcentaje es la prima de la clase I
    // escrita como fracción: 0.0054 % en vez de 0.54 %. Cien veces menos cuota
    // de RT, y ninguna tabla de referencia lo detecta después.
    expect(errores({ prima: '0.0054355' }).primaPct).toMatch(/Arts. 72 y 73 LSS/);
  });

  it('y el simétrico: el porcentaje escrito como si fuera por mil', () => {
    expect(errores({ prima: '54.355' }).primaPct).toMatch(/Arts. 72 y 73 LSS/);
  });

  it('un texto en la prima rechaza, no pasa como NaN', () => {
    expect(errores({ prima: 'medio por ciento' }).primaPct).toBeDefined();
  });
});

describe('RFC y registro patronal: opcionales, pero si vienen, bien formados', () => {
  const OK = { razon: 'Orca Ordorica', rfc: '', rp: '', prima: '1.0' };
  const errores = (over: Partial<typeof OK> = {}) => {
    const v = { ...OK, ...over };
    return validar(v.razon, v.rfc, v.rp, v.prima);
  };

  it('vacíos se aceptan: se capturan cuando se conocen y nunca se inventan', () => {
    expect(errores().rfc).toBeUndefined();
    expect(errores().registroPatronal).toBeUndefined();
  });

  it('el RFC de una moral son 12 y el de una física 13', () => {
    expect(errores({ rfc: 'OOC010101AAA' }).rfc).toBeUndefined();
    expect(errores({ rfc: 'OOCA010101AAA' }).rfc).toBeUndefined();
    expect(errores({ rfc: 'OOC01' }).rfc).toMatch(/12 caracteres/);
  });

  it('el registro patronal son 11: los 10 del registro más su verificador', () => {
    expect(errores({ rp: 'A1234567890' }).registroPatronal).toBeUndefined();
    // Diez es el error clásico: se teclea el registro y se olvida el dígito.
    expect(errores({ rp: 'A123456789' }).registroPatronal).toMatch(/11 caracteres/);
    expect(errores({ rp: 'A12345678901' }).registroPatronal).toMatch(/11 caracteres/);
  });
});
