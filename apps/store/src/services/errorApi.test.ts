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
