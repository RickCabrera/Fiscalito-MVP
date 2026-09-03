/**
 * La guarda de "la empresa no está configurada", en el HANDLER. (O-01)
 *
 * POR QUÉ EN UN ARCHIVO APARTE
 * ----------------------------
 * `useNominaCliente.guardas.test.ts` —el archivo cuyo propósito entero es
 * *"la protección vive en el handler y no en el DOM"*— declara `modoDespacho()`
 * a nivel de archivo, y en modo despacho `faltaDeLaEmpresa` vale `[]` por
 * construcción. Ahí esta guarda es inalcanzable.
 *
 * EL HUECO QUE ESTO CIERRA
 * ------------------------
 * Un revisor lo midió: neutralizar `if (faltaDeLaEmpresa.length > 0) return;`
 * en `cerrar` **dejaba las 498 pruebas en verde**. Lo único que la cazaba era
 * `rutasEmpresaUnica.test.tsx`, que afirma el letrero y `boton.disabled`, o sea
 * el atributo del DOM — exactamente la defensa cosmética que este repo lleva
 * dos corridas quitándose de encima.
 *
 * Aquí se llaman `pedirCierre()` y `calcular()` **directo**, saltándose el
 * botón. Criterio: quitar la guarda de `cerrar` tiene que romper un test de
 * aquí, y quitar la de `calcular` otro. Por separado.
 */

import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const CLIENTE_ID = 'empresa';

/** Qué tan configurada está la empresa en cada caso. */
const empresa = { razonSocial: 'Orca Ordorica Cristal Templado', primaRiesgo: '0.0113065' };

vi.mock('../../context/carteraStore', async () => {
  const { carteraDePrueba } = await import('../../test/carteraDePrueba');
  const { EMPRESA_POR_DEFECTO } = await import('../../services/empresa');
  return {
    useCartera: () => {
      const CLIENTE = {
        id: CLIENTE_ID,
        nombre: empresa.razonSocial,
        giro: '',
        origen: 'propio',
        prima_riesgo: empresa.primaRiesgo,
        clase_riesgo: 3,
        clave_periodicidad: '04',
        zona: 'general',
        periodo_sugerido: { inicio: '2026-08-16', fin: '2026-08-31', fecha_pago: '2026-08-31' },
        empleados: [],
      };
      return carteraDePrueba({
        loading: false,
        clientes: [CLIENTE],
        origen: 'firestore',
        soloLectura: false,
        clientePorId: () => CLIENTE,
        empresa: { ...EMPRESA_POR_DEFECTO, ...empresa },
      });
    },
  };
});

vi.mock('../../context/clienteActivoStore', () => ({
  useClienteActivo: () => ({
    clientes: [], cliente: null, loading: false, error: null,
    clienteId: CLIENTE_ID, setClienteId: vi.fn(), recargar: vi.fn(),
  }),
}));

const { useNominaCliente } = await import('./useNominaCliente');

/**
 * Router de fetch. Devuelve las URLs pedidas para poder afirmar **ausencias**,
 * que es lo que mide una guarda: no que falle, sino que no llegue a pedir.
 */
function stubApi(conChecadas: boolean) {
  const llamadas: string[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string) => {
      llamadas.push(url);
      let cuerpo: unknown;
      if (url.includes('asistencia/eventos')) {
        cuerpo = {
          eventos: conChecadas
            ? [
                {
                  empleado_no: 'E-01', timestamp: '2026-08-17T08:05:00-06:00',
                  tipo: 'entrada', fuente: 'simulado', serial_no: 1, raw: null,
                },
              ]
            : [],
        };
      } else if (url.includes('cerrar-periodo')) {
        cuerpo = {
          cliente: CLIENTE_ID, periodo: { inicio: '2026-08-16', fin: '2026-08-31' },
          incidencias: [], empleados_desconocidos: [],
        };
      } else if (url.includes('calcular-periodo')) {
        cuerpo = { cliente: CLIENTE_ID, recibos: [] };
      } else {
        throw new Error(`ruta no stubbeada: ${url}`);
      }
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(cuerpo) });
    }),
  );
  return llamadas;
}

/**
 * Monta el hook y **espera a que las checadas hayan llegado**.
 *
 * Esperar sólo al periodo no basta y produjo un test flaky: el panel se refresca
 * en un efecto propio, así que `pedirCierre` a veces veía cero checadas —y abría
 * el diálogo— y a veces las veía —y llamaba a `cerrar`—. Los dos caminos son
 * reales y cada uno mide una guarda distinta, así que cuál se recorre no puede
 * quedar al azar del scheduler.
 */
async function montarHook(conChecadas: boolean) {
  const llamadas = stubApi(conChecadas);
  const { result, rerender } = renderHook(() => useNominaCliente(CLIENTE_ID));
  // El periodo se siembra desde la cartera (no hay ficha del backend en este
  // modo), así que esperar a que llegue es esperar a que el hook esté listo.
  await waitFor(() => expect(result.current.inicio).toBe('2026-08-16'));
  await waitFor(() =>
    expect(llamadas.some((u) => u.includes('asistencia/eventos'))).toBe(true),
  );
  await waitFor(() => expect(result.current.eventos.length).toBe(conChecadas ? 1 : 0));
  llamadas.length = 0;
  return { result, llamadas, rerender };
}

beforeEach(() => {
  vi.stubEnv('VITE_MODO_EMPRESA_UNICA', '1');
  empresa.razonSocial = 'Orca Ordorica Cristal Templado';
  empresa.primaRiesgo = '0.0113065';
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('sin prima de riesgo, el HANDLER no cierra ni calcula', () => {
  it('`pedirCierre` ni siquiera abre el diálogo de confirmación', async () => {
    /**
     * **SIN checadas a propósito.** Con checadas, `pedirCierre` llamaría a
     * `cerrar`, cuya guarda taparía a la de aquí y la mutación sobreviviría —
     * que es exactamente lo que pasó la primera vez que se escribió esto.
     * Sin checadas el camino es `setConfirmarPara`, y entonces esta guarda es
     * la única que puede impedirlo.
     */
    empresa.primaRiesgo = '';
    const { result, llamadas } = await montarHook(false);

    expect(result.current.faltaDeLaEmpresa).toContain('la prima de riesgos de trabajo');
    await act(async () => {
      await result.current.pedirCierre();
    });

    // NI SIQUIERA ABRE EL DIÁLOGO. Sin esta aserción el test pasaba por la
    // razón equivocada: `pedirCierre` no llama a `cerrar` cuando no hay
    // checadas en el periodo, así que "no llamó a cerrar-periodo" era cierto
    // por el diálogo de confirmación y no por la guarda. Un revisor lo midió:
    // quitar el `if` de `cerrar` dejaba este archivo entero en verde.
    expect(result.current.confirmarCierre).toBe(false);
    expect(llamadas.some((u) => u.includes('cerrar-periodo'))).toBe(false);
  });

  it('`cerrar` directo tampoco: es la otra puerta, la del diálogo', async () => {
    /**
     * `cerrar` se exporta y el botón "Cerrar de todos modos" la llama **sin
     * pasar por `pedirCierre`**. Es la tercera puerta que R-06 documentó, y su
     * guarda se mide aquí por separado: mutar una de las dos tiene que romper
     * exactamente un test.
     */
    empresa.primaRiesgo = '';
    const { result, llamadas } = await montarHook(true);

    await act(async () => {
      await result.current.cerrar();
    });

    expect(llamadas.some((u) => u.includes('cerrar-periodo'))).toBe(false);
  });

  it('`calcular` tampoco, y lo dice con el camino para arreglarlo', async () => {
    /**
     * SE CIERRA PRIMERO, CON LA EMPRESA COMPLETA, Y LUEGO SE LE QUITA LA PRIMA.
     *
     * `calcular` sale antes si no hay cierre (`if (!cliente || !cierre) return`),
     * así que llamarlo con la empresa a medias desde el arranque **no llega a
     * la guarda**: el test pasaría por la razón equivocada y no cazaría a quien
     * borrara el `if`.
     *
     * Y el camino que simula es real: la empresa se edita en Perfil mientras la
     * nómina ya tiene un cierre en estado. Es el mismo argumento con el que
     * R-06 puso la guarda de `ajenoALaCartera` también en `calcular`: *"se puede
     * llegar aquí con un cierre viejo en estado"*.
     */
    const { result, llamadas, rerender } = await montarHook(true);
    await act(async () => {
      await result.current.pedirCierre();
    });
    await waitFor(() => expect(result.current.cierre).not.toBeNull());

    empresa.primaRiesgo = '';
    rerender();
    await waitFor(() =>
      expect(result.current.faltaDeLaEmpresa).toContain('la prima de riesgos de trabajo'),
    );
    llamadas.length = 0;

    await act(async () => {
      await result.current.calcular();
    });

    expect(llamadas.some((u) => u.includes('calcular-periodo'))).toBe(false);
    expect(result.current.error).toMatch(/prima de riesgos de trabajo/);
    // El mensaje tiene que llevar a donde se arregla, no sólo decir que falta.
    expect(result.current.error).toMatch(/Configuración de empresa/);
  });
});

describe('sin razón social, tampoco', () => {
  it('lo cuenta entre lo que falta y frena el cierre', async () => {
    empresa.razonSocial = '   ';
    const { result, llamadas } = await montarHook(false);

    expect(result.current.faltaDeLaEmpresa).toContain('la razón social');
    await act(async () => {
      await result.current.pedirCierre();
    });
    expect(llamadas.some((u) => u.includes('cerrar-periodo'))).toBe(false);
  });
});

describe('con la empresa configurada, el flujo corre', () => {
  /**
   * El contrapeso, y no es de relleno: una guarda que bloquee SIEMPRE también
   * dejaría verdes los tests de arriba. Sin este caso, "no llama a
   * cerrar-periodo" se cumpliría rompiendo la pantalla entera.
   */
  it('con checadas, `pedirCierre` llega hasta cerrar-periodo', async () => {
    const { result, llamadas } = await montarHook(true);

    expect(result.current.faltaDeLaEmpresa).toEqual([]);
    await act(async () => {
      await result.current.pedirCierre();
    });

    expect(llamadas.some((u) => u.includes('cerrar-periodo'))).toBe(true);
  });

  it('sin checadas, pregunta antes de cerrar (la guarda de R-06 sigue viva)', async () => {
    const { result } = await montarHook(false);

    await act(async () => {
      await result.current.pedirCierre();
    });

    expect(result.current.confirmarCierre).toBe(true);
  });
});
