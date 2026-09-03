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
import { aFraccion, aPorcentaje, diasDeLey, erroresDeParametros, validar } from './validacionEmpresa';
import type { ParametrosSalariales } from '../../services/carteraApi';

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


describe('los mínimos de ley en la PANTALLA, que es donde la tarea los pide', () => {
  /**
   * POR QUÉ ESTA SECCIÓN EXISTE
   * ---------------------------
   * Un revisor de motor hizo que `erroresDeParametros` devolviera siempre `[]`
   * y **las 543 pruebas del front quedaron verdes**. Con esa línea muerta, la
   * Configuración de empresa **acepta guardar un aguinaldo de 10 días y una
   * prima del 5 %** — porque `puedeGuardar` se apoya en ella.
   *
   * El criterio de O-03 dice *"los mínimos de ley rechazan valores por debajo"*
   * y lo pide **en Configuración de empresa**. En el motor estaba probado; en la
   * pantalla donde la tarea lo pide, no había nada.
   */

  const OK: ParametrosSalariales = {
    dias_aguinaldo: 15,
    prima_vacacional: '0.25',
    tabla_vacaciones: [],
    horario: {
      hora_entrada: '08:00',
      hora_salida: '17:00',
      tolerancia_minutos: 15,
      dias_laborables: [0, 1, 2, 3, 4],
    },
  };

  const con = (over: Partial<ParametrosSalariales>) =>
    erroresDeParametros({ ...OK, ...over });

  it('el mínimo de ley exacto NO se rechaza: el rango es cerrado', () => {
    expect(erroresDeParametros(OK)).toEqual([]);
  });

  it('aguinaldo 14 rechaza citando el Art. 87 LFT; 15 pasa', () => {
    expect(con({ dias_aguinaldo: 14 })[0]).toMatch(/Art. 87 LFT/);
    expect(con({ dias_aguinaldo: 15 })).toEqual([]);
  });

  it('y 30 días también pasa: la ley es piso, no techo', () => {
    expect(con({ dias_aguinaldo: 30 })).toEqual([]);
  });

  it('prima 0.24 rechaza citando el Art. 80 LFT; 0.25 pasa', () => {
    expect(con({ prima_vacacional: '0.24' })[0]).toMatch(/Art. 80 LFT/);
    expect(con({ prima_vacacional: '0.25' })).toEqual([]);
  });

  it('prima por encima del 100 % también rechaza', () => {
    expect(con({ prima_vacacional: '1.01' })[0]).toMatch(/100 %/);
    expect(con({ prima_vacacional: '1' })).toEqual([]);
  });

  it('un renglón de la tabla bajo la ley rechaza, y dice cuál', () => {
    const errores = con({ tabla_vacaciones: [[1, 20], [5, 19]] });
    expect(errores[0]).toMatch(/19 días al año 5/);
    expect(errores[0]).toMatch(/mínimo de ley son 20/);
  });

  it('una tabla superior a la ley se acepta entera', () => {
    expect(con({ tabla_vacaciones: [[1, 15], [3, 20], [10, 30]] })).toEqual([]);
  });

  it('sin días laborables rechaza, y dice qué pasaría', () => {
    /**
     * No es un capricho de formulario: sin ningún día laborable el cierre no
     * marca una sola falta y **la nómina sale completa siempre**. Es dinero
     * decidido por un campo vacío.
     */
    const errores = con({ horario: { ...OK.horario, dias_laborables: [] } });
    expect(errores[0]).toMatch(/no marcaría una sola falta/);
  });

  it('salida anterior o igual a la entrada rechaza', () => {
    expect(
      con({ horario: { ...OK.horario, hora_salida: '07:00' } })[0],
    ).toMatch(/posterior a la de entrada/);
    expect(
      con({ horario: { ...OK.horario, hora_salida: '08:00' } })[0],
    ).toMatch(/posterior a la de entrada/);
  });

  it('reporta TODOS los motivos, no sólo el primero', () => {
    // El operador tiene que poder arreglar de una vez, no descubrirlos de uno
    // en uno a base de intentos.
    const errores = con({
      dias_aguinaldo: 10,
      prima_vacacional: '0.05',
      horario: { ...OK.horario, dias_laborables: [] },
    });
    expect(errores).toHaveLength(3);
  });
});

describe('`diasDeLey` no puede divergir del motor', () => {
  /**
   * Es una COPIA en TypeScript de `dias_vacaciones_de_ley`
   * (`apps/api/app/nomina_engine/vacaciones.py`), acotada a **etiquetar el
   * formulario**: el campo dice "Días (ley: 16)" mientras el operador teclea, y
   * pedirle ese número al backend con cada pulsación sería un request por tecla.
   *
   * Ningún SBC sale de aquí —los días que se aplican los devuelve
   * `POST /nomina/sbc` en `dias_vacaciones_aplicados`— así que no es la segunda
   * verdad que este repo prohíbe. Pero una copia sin test diverge sola, así que
   * los números quedan clavados: **son los del motor**, renglón por renglón de
   * la escala del Art. 76 (reforma DOF 27-12-2022).
   */
  it.each([
    [0, 12], [1, 12], [2, 14], [3, 16], [4, 18], [5, 20],
    [6, 22], [10, 22], [11, 24], [15, 24], [16, 26], [40, 34],
  ])('año %i → %i días', (anios, dias) => {
    expect(diasDeLey(anios)).toBe(dias);
  });
});
