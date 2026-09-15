/**
 * Modo empresa única — el pivote de la corrida O.
 *
 * QUÉ CAMBIA
 * ----------
 * El producto dejó de ser la herramienta de un DESPACHO que lleva la nómina de
 * varios clientes y pasó a ser la nómina interna de UNA empresa. Con el modo
 * encendido no existe cartera en la pantalla: hay una empresa implícita, y
 * Empleados, Dispositivos, Nómina y Calendario operan directo sobre ella.
 *
 * EL MODO DESPACHO NO SE BORRA
 * ----------------------------
 * Se apaga. Todas las pantallas, contextos y rutas de las épicas E, G y R
 * siguen en el árbol y siguen probadas; lo único que cambia es que no se
 * montan. La decisión es de Ricardo: el despacho se retoma en otro repo.
 *
 * EL DEFAULT ES **APAGADO** DESDE T1, Y ESO INVIRTIÓ UNA DECISIÓN DE O-01
 * -----------------------------------------------------------------------
 * O-01 lo dejó ENCENDIDO por default con este argumento, que sigue siendo
 * correcto para lo que O-01 quería: si el default fuera "apagado", el pivote
 * dependería de un `.env` gitignoreado y un clon nuevo arrancaría en el modo
 * viejo sin que nada lo delatara.
 *
 * T1 invierte el default porque **el producto que se enseña es el despacho**.
 * El mismo argumento, leído desde aquí, dice lo contrario: con el default
 * encendido, un clon nuevo arranca en modo empresa única, el contador no ve
 * cartera, y ninguna de las pantallas de las épicas E/G/R —que están enteras y
 * probadas— se monta. El riesgo no desaparece, cambia de lado: ahora es el modo
 * EMPRESA el que depende de que alguien escriba la variable.
 *
 * El modo empresa única **no se borra ni se afloja**: se enciende con
 * `VITE_MODO_EMPRESA_UNICA=1` y todas sus pruebas siguen midiendo lo mismo. La
 * mayoría ya declaraba su modo con `vi.stubEnv(..., '1')` desde O-01 y no se
 * enteró del cambio; **ocho bloques del asistente NO lo declaraban** —lo
 * heredaban del default— y al invertirse pasaron a medir el despacho y se
 * cayeron. T1 los hizo declararlo con el helper `modoEmpresa()`, que es la
 * gemela de `modoDespacho()` y nació por esto. Ninguna aserción se tocó.
 *
 * La simetría de O-cierre se conserva, sólo que del otro lado: **encienden los
 * valores que no pueden significar otra cosa**; lo ambiguo o vacío deja el modo
 * apagado (despacho).
 *
 * SE LEE EN CADA LLAMADA, NO EN UNA `const` DE MÓDULO
 * ---------------------------------------------------
 * Una constante capturada al importar no se puede volver a evaluar después de
 * que el módulo entró al grafo, así que `vi.stubEnv` en un `beforeEach` no
 * tendría efecto y los tests del modo despacho serían imposibles de escribir.
 * Es la misma razón por la que `BACKEND_ES_DUENO` de `services/cartera.ts` sí
 * puede ser constante y esto no: aquel se decide una vez por proceso, éste se
 * consulta en render.
 */

/**
 * Las formas de ENCENDER el modo, en un solo lugar.
 *
 * El conjunto es el espejo del que O-cierre escribió para apagarlo, y se
 * conserva la misma regla: valen los valores que **no pueden significar otra
 * cosa**. Un flag que ignora en silencio lo que le escribieron es peor que no
 * tenerlo, así que `VITE_MODO_EMPRESA_UNICA=true` enciende igual que `1`.
 *
 * Lo ambiguo y lo vacío dejan el modo APAGADO: un `.env` a medio escribir no
 * cambia de app, y la app que se queda es la del despacho.
 */
const ENCENDIDO = new Set(['1', 'true', 'on', 'yes', 'si', 'sí']);

/** `true` si la app es la nómina de una sola empresa. Default: **no** (T1). */
export function modoEmpresaUnica(): boolean {
  const v = import.meta.env.VITE_MODO_EMPRESA_UNICA;
  return ENCENDIDO.has(String(v ?? '').trim().toLowerCase());
}

/**
 * Id del cliente implícito bajo el que vive todo en modo empresa única.
 *
 * POR QUÉ HAY UN ID SI YA NO HAY CARTERA
 * --------------------------------------
 * Porque el almacenamiento no cambia: los empleados siguen viviendo en
 * `users/{uid}/clientes/{id}/empleados/{id}`, que es la ruta que ya leen
 * `carteraFirestore.ts` **y** el backend de R-07. Mantenerla significa que
 * encender el interruptor de R-07 no exige migrar un solo documento, y que el
 * cálculo, el checador y los dispositivos siguen encontrando lo suyo.
 *
 * Dicho sin adorno: **la cartera desaparece de la interfaz, no del almacén.**
 * Reescribir esas rutas sería una migración destructiva a cambio de estética.
 */
export const ID_EMPRESA = 'empresa';
