/**
 * Las guardas del HANDLER, sin pasar por el `disabled` del botón.
 *
 * POR QUÉ ESTE ARCHIVO EXISTE
 * ---------------------------
 * El primer intento de probar esto fue por pantalla: poner la cartera en
 * `loading`, hacer clic en "Cerrar quincena" y afirmar que no hubo request.
 * **No probaba nada.** Con la cartera cargando el botón está `disabled`, y
 * `fireEvent.click` sobre un botón deshabilitado **no despacha el `onClick`**:
 * el test pasaba por el atributo, que es justo la defensa cosmética por la que
 * se levantó el bloqueante. Quitar las dos guardas del hook y dejar el
 * `disabled` daba cero fallas.
 *
 * Aquí se llaman `pedirCierre()` y `cerrar()` **directo**. Es la única forma de
 * fijar que la protección vive en el handler y no en el DOM — que es lo que el
 * propio encabezado de `NominaClientePage` lleva diciendo desde E-06:
 * *"`disabled` es una propiedad del DOM, no una garantía del handler"*.
 *
 * Criterio: mutar la guarda de `cerrar` debe romper un test de aquí, y mutar la
 * de `pedirCierre` debe romper otro. Por separado.
 */

import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const CLIENTE = 'taller';

const estadoCartera = { loading: false };

vi.mock('../../context/carteraStore', async () => {
  const { carteraDePrueba } = await import('../../test/carteraDePrueba');
  return {
    useCartera: () =>
      carteraDePrueba({
        loading: estadoCartera.loading,
        clientes: [],
        origen: 'firestore',
        soloLectura: false,
        clientePorId: () => null,
      }),
  };
});

vi.mock('../../context/clienteActivoStore', () => ({
  useClienteActivo: () => ({
    clientes: [], cliente: null, loading: false, error: null,
    clienteId: CLIENTE, setClienteId: vi.fn(), recargar: vi.fn(),
  }),
}));

const { useNominaCliente } = await import('./useNominaCliente');

/** Router de fetch. Devuelve las URLs pedidas para poder afirmar ausencias. */
function stubApi(conChecadas = true) {
  const llamadas: string[] = [];
  vi.stubGlobal('fetch', vi.fn((url: string) => {
    llamadas.push(url);
    let cuerpo: unknown;
    if (url.includes('despacho/clientes')) {
      cuerpo = {
        id: CLIENTE, nombre: 'Taller Nogal', giro: 'G', origen: 'sintetico',
        num_empleados: 1, prima_riesgo: '0.0113065', clase_riesgo: 2,
        clave_periodicidad: '04', zona: 'general', fecha_referencia: '2026-09-01',
        empleados: [{
          empleado_no: 'T-1', nombre: 'PERSONA UNA', puesto: '', salario_diario: '520.00',
          salario_diario_integrado: '548.50', zona: 'general', fecha_alta: null,
          antiguedad_anios: null, factor: '1.0548', factor_implicito: false,
        }],
        periodo_sugerido: { inicio: '2026-08-16', fin: '2026-08-31', fecha_pago: null },
      };
    } else if (url.includes('asistencia/eventos')) {
      cuerpo = {
        eventos: conChecadas
          ? [{
              empleado_no: 'T-1', timestamp: '2026-08-17T08:05:00-06:00',
              tipo: 'entrada', fuente: 'simulado', serial_no: 1, raw: null,
            }]
          : [],
      };
    } else if (url.includes('cerrar-periodo')) {
      cuerpo = {
        cliente: CLIENTE, periodo: { inicio: '2026-08-16', fin: '2026-08-31' },
        incidencias: [], empleados_desconocidos: [],
      };
    } else {
      throw new Error(`ruta no stubbeada: ${url}`);
    }
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(cuerpo) });
  }));
  return llamadas;
}

/** Monta el hook y espera a que la ficha del backend haya llegado. */
async function montarHook(conChecadas = true) {
  const llamadas = stubApi(conChecadas);
  const { result, rerender } = renderHook(() => useNominaCliente(CLIENTE));
  await waitFor(() => expect(result.current.inicio).toBe('2026-08-16'));
  /**
   * Pone la cartera en "cargando" y **vuelve a renderizar**: sin el rerender el
   * hook sigue con el valor viejo del contexto y la guarda nunca se evalúa —
   * el test pasaría por la razón equivocada.
   */
  const conCarteraCargando = () => {
    estadoCartera.loading = true;
    rerender();
  };
  return { result, llamadas, conCarteraCargando };
}

const seCerro = (llamadas: string[]) => llamadas.some((u) => u.includes('cerrar-periodo'));

beforeEach(() => {
  estadoCartera.loading = false;
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

describe('con la cartera cargando, el handler NO cierra', () => {
  /**
   * Cerrar en esa ventana usaría las llaves del CATÁLOGO en vez de las del
   * aparato: cero checadas encontradas para quien tenga número propio, y cuando
   * la cartera llegue la plantilla vuelve a cuadrar por `empleado_no`, así que
   * **nada levanta** — recibo con faltas de más, en silencio.
   */
  it('`cerrar()` llamado directo no dispara la petición', async () => {
    const { result, llamadas, conCarteraCargando } = await montarHook();
    conCarteraCargando();
    await act(async () => { await result.current.cerrar(); });
    expect(seCerro(llamadas)).toBe(false);
  });

  it('`pedirCierre()` llamado directo tampoco', async () => {
    // Es el camino del botón y también el de "Cerrar de todos modos".
    const { result, llamadas, conCarteraCargando } = await montarHook();
    conCarteraCargando();
    await act(async () => { result.current.pedirCierre(); });
    await new Promise((r) => setTimeout(r, 30));
    expect(seCerro(llamadas)).toBe(false);
  });

  it('SIN checadas en el periodo, tampoco abre el diálogo de confirmación', async () => {
    /**
     * Éste es el único test que aísla la guarda de `pedirCierre`.
     *
     * Con checadas, `pedirCierre` llama a `cerrar()`, que tiene su propia
     * guarda: quitar la de `pedirCierre` no cambia nada y la mutación
     * sobrevive — lo comprobé. Sin checadas, `pedirCierre` abre el diálogo en
     * vez de cerrar, y ahí sí se ve: sin su guarda, la pantalla pediría
     * confirmar un cierre que no debería poder ocurrir, y el operador que dijera
     * "Cerrar de todos modos" entraría igual.
     */
    const { result, conCarteraCargando } = await montarHook(false);
    conCarteraCargando();
    await act(async () => { result.current.pedirCierre(); });
    expect(result.current.confirmarCierre).toBe(false);
  });
});

describe('con la cartera lista, el handler SÍ cierra', () => {
  it('la guarda no deja el cierre muerto para siempre', async () => {
    // La otra mitad: una guarda que nunca se abre es un botón roto.
    const { result, llamadas } = await montarHook();
    await act(async () => { await result.current.cerrar(); });
    expect(seCerro(llamadas)).toBe(true);
  });

  it('`pedirCierre` con checadas en el periodo cierra sin preguntar', async () => {
    const { result, llamadas } = await montarHook();
    await act(async () => { result.current.pedirCierre(); });
    await waitFor(() => expect(seCerro(llamadas)).toBe(true));
    expect(result.current.confirmarCierre).toBe(false);
  });
});
