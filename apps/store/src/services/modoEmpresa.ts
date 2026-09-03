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
 * EL DEFAULT ES ENCENDIDO, Y ESO TIENE UNA CONSECUENCIA QUE HAY QUE DECIR
 * -----------------------------------------------------------------------
 * Un build sin la variable tiene que dar la app de la empresa, no la del
 * despacho: si el default fuera "apagado", el pivote dependería de un `.env`
 * que está gitignoreado, y un clon nuevo arrancaría en el modo viejo sin que
 * nada lo delatara.
 *
 * A cambio, los tests del modo despacho tienen que **declarar** en qué modo
 * corren (`src/test/modoDespacho.ts`). Eso no afloja ninguna aserción: las deja
 * diciendo en voz alta algo que hasta hoy era ambiente implícito.
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

/** `true` si la app es la nómina de una sola empresa. Default: **sí**. */
export function modoEmpresaUnica(): boolean {
  return import.meta.env.VITE_MODO_EMPRESA_UNICA !== '0';
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
