/**
 * Los cuatro errores del backend se traducen a cuatro mensajes distintos.
 *
 * Las formas de abajo NO son inventadas: se midieron contra la API corriendo el
 * 2026-09-02 y están tabuladas en el encabezado de `errorApi.ts`.
 */

import { describe, expect, it } from 'vitest';
import { detalleDelError } from './errorApi';

/**
 * Una `Response` con `url` puesta, que es de donde sale "el backend en …".
 * `url` es de sólo lectura en el constructor, así que se define encima.
 */
function conUrl(status: number, url: string): Response {
  const res = new Response(null, { status });
  Object.defineProperty(res, 'url', { value: url, configurable: true });
  return res;
}

describe('detalleDelError', () => {
  it('un 404 de dominio devuelve el mensaje del backend, no el genérico', () => {
    // `FiscalAgentError` viaja con sobre propio. Es un recurso que no existe,
    // NO una ruta que no existe, y el mensaje del backend ya lo explica.
    const msg = detalleDelError(conUrl(404, 'http://localhost:8000/api/v1/despacho/clientes/x'), {
      exito: false,
      error: "El cliente 'x' no está en la cartera del despacho.",
    });
    expect(msg).toBe("El cliente 'x' no está en la cartera del despacho.");
  });

  it('un 404 con `detail` string dice que el backend no reconoce la llamada', () => {
    const msg = detalleDelError(
      conUrl(404, 'http://localhost:8000/api/v1/despacho/calendario?anio_de_las_cuotas=2026'),
      { detail: 'Not Found' },
    );
    expect(msg).toContain('http://localhost:8000/api/v1/despacho/calendario');
    expect(msg).toContain('no reconoce esta llamada');
    // El query string no aporta al diagnóstico y alarga el mensaje.
    expect(msg).not.toContain('anio_de_las_cuotas');
    // NO dice "Not Found", que es justo lo que no le decía nada a nadie.
    expect(msg).not.toContain('Not Found');
  });

  it('no atribuye una sola causa: ofrece las dos que existen', () => {
    // Un mensaje que afirmara "reinicia el servidor" mandaría a reiniciar
    // cuando el problema es que VITE_FISCAL_AGENT_URL apunta a otro backend.
    const msg = detalleDelError(conUrl(404, 'http://localhost:8000/api/v1/x'), {
      detail: 'Not Found',
    });
    expect(msg).toContain('antes del último merge');
    expect(msg).toContain('VITE_FISCAL_AGENT_URL');
  });

  it('el 405 se trata igual que el 404: el backend tampoco conoce esa llamada', () => {
    // Una ruta que cambió de verbo entre commits da 405, y el diagnóstico es
    // el mismo. Dejarlo fuera sería cerrar media puerta.
    const msg = detalleDelError(conUrl(405, 'http://localhost:8000/api/v1/despacho/clientes'), {
      detail: 'Method Not Allowed',
    });
    expect(msg).toContain('no reconoce esta llamada');
  });

  it('un 422 de validación de FastAPI muestra el primer mensaje', () => {
    const msg = detalleDelError(conUrl(422, 'http://localhost:8000/api/v1/x'), {
      detail: [{ msg: 'Input should be a valid integer' }],
    });
    expect(msg).toBe('Input should be a valid integer');
  });

  it('un 422 de `extra_forbidden` NOMBRA el campo que sobra (F-02)', () => {
    // El 422 exacto que tumbó el alta de empleado: el `msg` de FastAPI no dice
    // cuál campo sobra, y sin el nombre el operador no tiene qué tocar.
    const msg = detalleDelError(conUrl(422, 'http://localhost:8000/api/v1/nomina/sbc'), {
      detail: [
        {
          loc: ['body', 'tabla_vacaciones'],
          msg: 'Extra inputs are not permitted',
          type: 'extra_forbidden',
        },
      ],
    });
    expect(msg).toBe('tabla_vacaciones: Extra inputs are not permitted');
  });

  it('un 422 con varios campos los muestra todos, no sólo el primero', () => {
    // Mostrar sólo el primero obliga a arreglar-reintentar-descubrir en ciclo.
    const msg = detalleDelError(conUrl(422, 'http://localhost:8000/api/v1/x'), {
      detail: [
        { loc: ['body', 'salario_diario'], msg: 'Input should be greater than 0' },
        { loc: ['body', 'dias_aguinaldo'], msg: 'Input should be greater than 14' },
      ],
    });
    expect(msg).toBe(
      'salario_diario: Input should be greater than 0 · ' +
        'dias_aguinaldo: Input should be greater than 14',
    );
  });

  it('conserva el índice del renglón en una lista', () => {
    // En una plantilla de 40 empleados, saber que es el renglón 12 es la mitad
    // del arreglo.
    const msg = detalleDelError(conUrl(422, 'http://localhost:8000/api/v1/x'), {
      detail: [{ loc: ['body', 'incidencias', 12, 'faltas'], msg: 'Input should be >= 0' }],
    });
    expect(msg).toBe('incidencias.12.faltas: Input should be >= 0');
  });

  it('con muchos errores corta en tres y dice cuántos faltan', () => {
    const msg = detalleDelError(conUrl(422, 'http://localhost:8000/api/v1/x'), {
      detail: [1, 2, 3, 4, 5].map((n) => ({ loc: ['body', `c${n}`], msg: 'mal' })),
    });
    expect(msg).toBe('c1: mal · c2: mal · c3: mal (y 2 más)');
  });

  it('un `detail` array que no trae `msg` no se traga el error', () => {
    // Antes caía en `El servidor respondió 422`, que es poco pero es algo;
    // el riesgo real sería devolver cadena vacía y no pintar nada.
    const msg = detalleDelError(conUrl(422, 'http://localhost:8000/api/v1/x'), {
      detail: [{ algo: 'raro' }],
    });
    expect(msg).toBe('El servidor respondió 422');
  });

  it('`error` gana sobre `detail` cuando vienen los dos', () => {
    // Invertir el orden haría que un 404 de dominio que algún día traiga los
    // dos campos se reporte como ruta inexistente: lo contrario de la verdad.
    const msg = detalleDelError(conUrl(404, 'http://localhost:8000/api/v1/x'), {
      exito: false,
      error: 'El cliente no existe.',
      detail: 'Not Found',
    });
    expect(msg).toBe('El cliente no existe.');
  });

  it('un cuerpo que no es JSON cae al código de estado', () => {
    const msg = detalleDelError(conUrl(500, 'http://localhost:8000/api/v1/x'), null);
    expect(msg).toBe('El servidor respondió 500');
  });

  it('sin URL disponible el mensaje sigue siendo útil', () => {
    // `res.url` viene vacío en respuestas opacas. Se omite el "en <url>" en vez
    // de inventar una.
    const msg = detalleDelError(conUrl(404, ''), { detail: 'Not Found' });
    expect(msg).toContain('El backend contestó 404');
    expect(msg).not.toContain('undefined');
  });
});
