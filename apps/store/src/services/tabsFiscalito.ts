/**
 * Tabs del servicio Fiscalito por régimen y tipo de persona.
 *
 * Salió de `navigation.ts` en P6-05 (tope de 300 líneas) sin cambiar nada;
 * `navigation.ts` lo reexporta.
 */

export type TabFiscalito =
  | 'declaracion' | 'anual' | 'deducciones' | 'calendario' | 'comparar'
  | 'diot' | 'retenciones' | 'multiperiodo' | 'estado' | 'pagospm' | 'resumen';

/**
 * Los tabs de una PERSONA MORAL (601) — T6, cascarón.
 *
 * `pagospm` primero **porque es el tab por defecto**: `allowedTabIds[0]` es lo
 * que la pantalla abre, y abrir en `declaracion` sería recibir a la PM con la
 * única pantalla que no le sirve.
 *
 * `declaracion` entra a propósito aunque el motor no la soporte: la tarea pide
 * que quede **deshabilitada con mensaje**, no escondida. Escondida, el contador
 * no tiene cómo saber si es que la PM no declara o es que el producto todavía
 * no puede; `FiscalitoServicePage` la reemplaza por el aviso. El resto —anual,
 * comparar, DIOT, retenciones, multi-periodo, estado de cuenta— sí se queda
 * fuera: todas salen del mismo motor de persona física y no hay nada honesto
 * que pintar en ellas para una moral.
 */
const TABS_601: readonly TabFiscalito[] = Object.freeze<TabFiscalito[]>([
  // P3-01/P3-06: con el motor PM, `pagospm` ya calcula en el backend y la moral
  // tiene su anual (ajuste por inflación, PTU, pérdidas, papeles de trabajo).
  'pagospm', 'anual', 'calendario', 'declaracion',
  // P3-02: el resumen de impuestos; su ISR propio sale del motor PM (P3-01).
  'resumen',
]);

/**
 * El set completo: el de `pyme` y el de un 612.
 *
 * Congelado, y **se devuelve copiado** (`tabsCompletos()`), no por referencia.
 * Antes cada rama de `getTabsForProfile` construía su propio literal, así que
 * extraer la constante introdujo un arreglo compartido entre cuatro ramas: un
 * `.sort()` o un `.push()` de un consumidor futuro le habría cambiado los tabs a
 * todos los perfiles a la vez, y eso se ve bien hasta que no. Hoy nadie lo muta
 * —los dos consumidores sólo hacen `.includes()` y `[0]`— pero la trampa era
 * nueva y la cerró el revisor de T1.
 */
const TABS_COMPLETOS: readonly TabFiscalito[] = Object.freeze<TabFiscalito[]>([
  'declaracion', 'anual', 'calendario', 'comparar', 'diot', 'retenciones', 'multiperiodo', 'estado',
  'resumen',
]);

/** Copia fresca del set completo, para no repartir la misma referencia. */
function tabsCompletos(): TabFiscalito[] {
  return [...TABS_COMPLETOS];
}

/**
 * Tabs de Fiscalito para el CLIENTE ACTIVO del despacho, por su régimen.
 *
 * Desde K no hay contribuyentes: el sujeto del cálculo siempre es un cliente.
 * Sin cliente elegido (`regimen` vacío) no hay tabs: la pantalla pinta el estado
 * vacío con el selector en vez de tabs sobre un cliente inexistente.
 */
export function getTabsForProfile(regimen: string | null, rfc?: string | null): TabFiscalito[] {
  if (!regimen) return [];
  // P3-01: un 626 con RFC de persona moral (12 caracteres) es RESICO PM (Arts. 206-215
  // LISR): su ISR es el del motor de morales, no el RESICO de personas físicas.
  if (regimen === '626' && (rfc ?? '').trim().length === 12) {
    return ['pagospm', 'anual', 'calendario', 'resumen'];
  }
  return tabsPorRegimenDeCliente(regimen);
}

/**
 * Tabs que se le pueden trabajar a un cliente del despacho, por su régimen.
 *
 * Los dos regímenes que `contributorProfiles.ts` declara para el perfil
 * `contador` —y los dos únicos que el alta de cliente ofrece— son 612 y 626, y
 * son los que deciden el caso que importa: a un 626 no se le ofrecen DIOT ni
 * Retenciones.
 *
 * **ESE CORTE ES HEREDADO, NO VERIFICADO.** La rama `regimen === '626'` de abajo
 * existe desde E-01 y T1 no la inventó: lo que T1 cambió es a quién se le aplica
 * (el cliente del despacho, no el contribuyente). **Pendiente de confirmar con
 * la contadora: `docs/decisiones-nomina.md` §D30**, donde queda escrito por qué
 * DIOT y Retenciones son dos preguntas separadas y por qué la de Retenciones
 * probablemente no se contesta con el régimen.
 *
 * El resto de los regímenes no se inventa: si algún día el alta de cliente
 * abriera 605, 606 o 625, esto ya responde lo mismo que responde para un
 * contribuyente de ese régimen, en vez de degradar al set completo en silencio.
 */
function tabsPorRegimenDeCliente(regimen: string): TabFiscalito[] {
  // T6: un cliente persona moral ve lo mismo que una PM que entra por su
  // cuenta. El alta de cliente ya ofrece 601 (`REGIMENES_DE_CLIENTE`), así que
  // esta rama no es hipotética como las de 605/606/625.
  if (regimen === '601') return [...TABS_601];
  if (regimen === '605') return ['deducciones', 'calendario'];
  // P3-02: `resumen` (resumen y actualización de impuestos) al final de cada régimen
  // que declara mensualmente; no cambia el tab por defecto. El 605 no declara mensual.
  if (regimen === '626') return ['declaracion', 'anual', 'calendario', 'comparar', 'estado', 'resumen'];
  if (regimen === '606') return ['declaracion', 'anual', 'calendario', 'comparar', 'multiperiodo', 'estado', 'resumen'];
  if (regimen === '625') return ['declaracion', 'anual', 'calendario', 'estado', 'resumen'];
  // 612 y cualquier otro: el set completo, que es el de `pyme`.
  return tabsCompletos();
}
