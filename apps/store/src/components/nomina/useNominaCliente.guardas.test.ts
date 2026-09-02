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

const CLIENTE_ID = 'taller';

const estadoCartera = { loading: false, tieneAlCliente: true };

/**
 * R-06: `clientePorId` devolviendo `null` dejó de ser un caso neutro.
 *
 * Antes significaba "la cartera no lo tiene, usa la ficha del backend", que era
 * el camino del fallback. Ahora significa **"este cliente no es de tu cuenta"**
 * y el hook se niega a cerrar y a calcular. Por eso el doble lo hace explícito
 * con `tieneAlCliente`: los tests de la guarda de `loading` necesitan que el
 * cliente SÍ esté, y hay tests nuevos para la guarda nueva.
 */
vi.mock('../../context/carteraStore', async () => {
  const { carteraDePrueba } = await import('../../test/carteraDePrueba');
  const CLIENTE = {
    id: CLIENTE_ID, nombre: 'Taller', giro: 'Taller', origen: 'sintetico',
    prima_riesgo: '0.0113065', clase_riesgo: 2, clave_periodicidad: '04',
    zona: 'general',
    periodo_sugerido: { inicio: '2026-08-16', fin: '2026-08-31', fecha_pago: '2026-08-31' },
    empleados: [],
  };
  return {
    useCartera: () =>
      carteraDePrueba({
        loading: estadoCartera.loading,
        clientes: estadoCartera.tieneAlCliente ? [CLIENTE] : [],
        origen: 'firestore',
        soloLectura: false,
        clientePorId: () => (estadoCartera.tieneAlCliente ? CLIENTE : null),
      }),
  };
});

vi.mock('../../context/clienteActivoStore', () => ({
  useClienteActivo: () => ({
    clientes: [], cliente: null, loading: false, error: null,
    clienteId: CLIENTE_ID, setClienteId: vi.fn(), recargar: vi.fn(),
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
        id: CLIENTE_ID, nombre: 'Taller Nogal', giro: 'G', origen: 'sintetico',
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
        cliente: CLIENTE_ID, periodo: { inicio: '2026-08-16', fin: '2026-08-31' },
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
  const { result, rerender } = renderHook(() => useNominaCliente(CLIENTE_ID));
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
  return { result, llamadas, conCarteraCargando, rerender };
}

const seCerro = (llamadas: string[]) => llamadas.some((u) => u.includes('cerrar-periodo'));

beforeEach(() => {
  estadoCartera.loading = false;
  estadoCartera.tieneAlCliente = true;
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

describe('R-06 · el cliente que NO está en la cartera de esta cuenta', () => {
  /**
   * LA GUARDA MÁS IMPORTANTE DE R-06, Y LA MENOS VISIBLE.
   *
   * Hasta ahora eran dos estados: la cartera carga, o la cartera está. Con el
   * fallback de G-03 daba igual —`clientePorId` siempre devolvía algo porque el
   * catálogo del backend poblaba la cartera— así que el tercer estado no
   * existía.
   *
   * Quitado el fallback aparece: **cargada, y el cliente no está en ella**.
   * Entrar por URL a `/app/clientes/demo/nomina` desde una cuenta cuya cartera
   * no tiene `demo` daba `clientePorId → null`, y entonces `plantillaDeNomina`
   * caía a la ficha COMPLETA del backend **sin filtrar vinculados**, con
   * `sinVincular` en 0 — así que el aviso tampoco salía. Otro conjunto de
   * empleados entrando a `POST /nomina/calcular-periodo`, en silencio.
   *
   * Se prueba llamando a los handlers DIRECTO, por la razón del encabezado de
   * este archivo: `disabled` es una propiedad del DOM, no una garantía.
   */
  it('`pedirCierre` NO cierra un cliente ajeno a la cartera', async () => {
    estadoCartera.tieneAlCliente = false;
    const { result, llamadas } = await montarHook(true);
    expect(result.current.ajenoALaCartera).toBe(true);


    act(() => result.current.pedirCierre());

    expect(llamadas.some((u) => u.includes('cerrar-periodo'))).toBe(false);
    // Y tampoco pregunta: preguntar sugeriría que decir que sí serviría.
    expect(result.current.confirmarCierre).toBe(false);
  });

  it('`calcular` lo rechaza aunque ya haya un cierre en estado', async () => {
    /**
     * ESTE ES EL ESCENARIO QUE LA GUARDA DE `calcular` DEFIENDE, y montarlo mal
     * la volvía inalcanzable: con la cartera ya resuelta a "no es tuyo" desde el
     * principio, `pedirCierre` bloquea antes y `calcular` sale por su
     * `!cierre`. El test pasaba sin ejercitar nada.
     *
     * El caso real es el otro: se cerró el periodo con la cartera diciendo que
     * sí, y **después** la cartera se recarga y el cliente ya no está —otra
     * pestaña lo borró, o la lectura se rehízo—. El `cierre` sigue en estado y
     * el botón de calcular está vivo. Cerrar una sola de las dos puertas deja
     * la otra abierta.
     */
    estadoCartera.tieneAlCliente = true;
    const { result, llamadas, rerender } = await montarHook(true);

    act(() => result.current.pedirCierre());
    await waitFor(() => expect(result.current.cierre).not.toBeNull());

    // Ahora el cliente desaparece de la cartera, con el cierre ya hecho. El
    // `rerender` es obligatorio y este archivo ya lo advierte para la otra
    // guarda: sin él, el hook sigue con el valor viejo del contexto y el test
    // pasaría por la razón equivocada.
    estadoCartera.tieneAlCliente = false;
    rerender();
    await waitFor(() => expect(result.current.ajenoALaCartera).toBe(true));

    await act(async () => { await result.current.calcular(); });

    expect(llamadas.some((u) => u.includes('calcular-periodo'))).toBe(false);
    expect(result.current.error).toContain('no está en la cartera de tu cuenta');
  });

  it('`cerrar` —la TERCERA puerta— tampoco cierra un cliente ajeno', async () => {
    /**
     * `cerrar` se exporta y el diálogo de confirmación la llama **directo**
     * ("Cerrar de todos modos", `NominaClientePage`), sin pasar por
     * `pedirCierre`. Escribí "cerrar una sola de las dos puertas deja la otra
     * abierta" y eran tres; un revisor encontró la que faltaba.
     *
     * El camino es el mismo que hace alcanzable la guarda de `calcular`: se
     * pide el cierre con el cliente presente y sin checadas —lo que abre el
     * diálogo—, la cartera se recarga sin él, y el diálogo sigue en pantalla
     * porque `confirmarPara` apunta al mismo id. El clic mandaba al backend la
     * ficha COMPLETA del catálogo, sin filtrar vinculados.
     *
     * No llega a `calcular-periodo`, así que no sale un recibo con ISR mal.
     * Pero sí un cierre con el conjunto de empleados equivocado, que es el
     * insumo del cálculo.
     */
    estadoCartera.tieneAlCliente = true;
    const { result, llamadas, rerender } = await montarHook(false); // sin checadas
    act(() => result.current.pedirCierre());
    await waitFor(() => expect(result.current.confirmarCierre).toBe(true));

    estadoCartera.tieneAlCliente = false;
    rerender();
    await waitFor(() => expect(result.current.ajenoALaCartera).toBe(true));
    // El diálogo sigue vivo: es lo que hace el camino alcanzable.
    expect(result.current.confirmarCierre).toBe(true);

    await act(async () => { await result.current.cerrar(); });
    expect(llamadas.some((u) => u.includes('cerrar-periodo'))).toBe(false);
  });

  it('con el cliente EN la cartera, `ajenoALaCartera` es falso y sí se cierra', async () => {
    // La mitad simétrica. Sin ella, una guarda que bloqueara SIEMPRE pasaría
    // los dos tests de arriba y dejaría la nómina inservible.
    estadoCartera.tieneAlCliente = true;
    const { result, llamadas } = await montarHook(true);
    expect(result.current.ajenoALaCartera).toBe(false);

    act(() => result.current.pedirCierre());
    await waitFor(() => expect(llamadas.some((u) => u.includes('cerrar-periodo'))).toBe(true));
  });
});
