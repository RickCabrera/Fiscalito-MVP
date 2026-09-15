/**
 * Planes de la cuenta — límites de uso, SIN cobro. (T8)
 *
 * QUÉ ES Y QUÉ NO ES
 * ------------------
 * Esto es el **encuadre comercial** del producto: cuántos usuarios y cuántos
 * clientes cabe llevar en cada plan, para que un despacho vea en pantalla en
 * qué tamaño está parado. **No hay billing**: ni pasarela de pago, ni
 * suscripción, ni fecha de corte, ni factura. Por eso el precio es
 * `'Consultar'` en los tres y no un número: publicar "$499/mes" en una pantalla
 * que no cobra nada es una promesa comercial que el producto no puede cumplir,
 * y se lee igual de real que las que sí.
 *
 * EL LÍMITE SÍ MUERDE, Y ESO ES A PROPÓSITO
 * -----------------------------------------
 * `maxClientes` bloquea el alta de un cliente nuevo cuando se llega al tope
 * (`ClientesPage`). Es la única parte del plan con consecuencia, y existe
 * porque un límite que sólo se pinta no es un límite: el contador lo descubre
 * cuando alguien le pasa una factura, no cuando le toca decidir.
 *
 * **`maxUsuarios` NO se hace cumplir**, y se dice aquí en vez de que alguien lo
 * suponga: la app no tiene cuentas de equipo —un `users/{uid}` es una persona—
 * así que no hay a quién contar. El número se muestra como lo que describe el
 * plan, no como algo que el código vigile.
 *
 * DÓNDE VIVE EL PLAN ELEGIDO
 * --------------------------
 * En `users/{uid}.plan`, vía `ProfileContext`. Es **opcional**: una cuenta que
 * nunca entró a `/app/planes` no tiene el campo, y entonces manda
 * `planPorDefecto()`. No se escribe solo al iniciar sesión — un default
 * guardado en silencio convierte una suposición del código en un dato del
 * usuario, y luego nadie sabe si lo eligió él.
 */

import { modoEmpresaUnica } from './modoEmpresa';

export type IdPlan = 'contador' | 'despacho' | 'empresa';

export interface Plan {
  id: IdPlan;
  nombre: string;
  /** Para quién es, en una línea. Se pinta debajo del nombre. */
  descripcion: string;
  /** Descriptivo: la app no tiene cuentas de equipo. Ver el encabezado. */
  maxUsuarios: number;
  /** Éste SÍ se hace cumplir: bloquea el alta en `ClientesPage`. */
  maxClientes: number;
  /**
   * No hay precio publicado porque no hay cobro. El tipo es literal para que
   * agregar un número exija tocar el tipo y no se cuele como una cadena más.
   */
  precio: 'Consultar';
  incluye: string[];
}

/**
 * Los tres planes, congelados y devueltos por referencia de lectura.
 *
 * `readonly` no es adorno: `PlanesPage` los recorre y cualquier `.sort()` de un
 * consumidor futuro reordenaría el catálogo para todas las pantallas a la vez.
 * Es la misma trampa que cerró el revisor de T1 en `TABS_COMPLETOS`.
 */
export const PLANES: readonly Plan[] = Object.freeze<Plan[]>([
  {
    id: 'contador',
    nombre: 'Contador',
    descripcion: 'Un contador independiente que lleva su propia cartera.',
    maxUsuarios: 1,
    maxClientes: 25,
    precio: 'Consultar',
    incluye: [
      'Hasta 25 clientes',
      '1 usuario',
      'Nómina, IMSS y calendario patronal',
      'Pre-declaración, DIOT y retenciones por cliente',
    ],
  },
  {
    id: 'despacho',
    nombre: 'Despacho',
    descripcion: 'Un equipo contable con cartera grande.',
    maxUsuarios: 10,
    maxClientes: 200,
    precio: 'Consultar',
    incluye: [
      'Hasta 200 clientes',
      'Hasta 10 usuarios',
      'Todo lo del plan Contador',
      'Exportadores IMSS y dispersión bancaria',
    ],
  },
  {
    id: 'empresa',
    nombre: 'Empresa',
    descripcion: 'Una sola empresa que lleva su nómina en casa.',
    maxUsuarios: 1,
    maxClientes: 1,
    precio: 'Consultar',
    incluye: [
      'Una empresa',
      '1 usuario',
      'Nómina, IMSS y calendario patronal',
      'Checador y dispositivos',
    ],
  },
]);

export function planPorId(id: string): Plan | undefined {
  return PLANES.find((p) => p.id === id);
}

/**
 * El plan de una cuenta que nunca eligió uno.
 *
 * Depende del MODO, no del perfil: en modo empresa única no hay cartera que
 * llevar, así que ofrecer 25 clientes sería describir un producto que esa
 * instalación no tiene. En modo despacho se elige el MÁS CHICO de los dos de
 * cartera — un default generoso regala capacidad que nadie contrató, y además
 * haría que el bloqueo del alta no se viera nunca.
 */
export function planPorDefecto(): Plan {
  return planPorId(modoEmpresaUnica() ? 'empresa' : 'contador')!;
}

/**
 * El plan efectivo del perfil.
 *
 * Acepta `string | undefined` y no `IdPlan` a propósito: lo que llega de
 * Firestore no está tipado —`ProfileContext` hace `as UserProfile` sobre el
 * documento— así que un valor viejo o escrito a mano cae aquí. Se resuelve al
 * default en vez de romper la pantalla.
 */
export function planDelPerfil(plan: string | undefined): Plan {
  return (plan ? planPorId(plan) : undefined) ?? planPorDefecto();
}

export interface UsoDeClientes {
  actual: number;
  limite: number;
  /** "3 / 25 clientes", el texto que se pinta en Perfil y en el selector. */
  texto: string;
  /** `true` cuando ya no se puede dar de alta otro. */
  alLimite: boolean;
}

/** Cuántos clientes lleva contra cuántos le caben. */
export function usoDeClientes(plan: Plan, clientes: number): UsoDeClientes {
  return {
    actual: clientes,
    limite: plan.maxClientes,
    texto: `${clientes} / ${plan.maxClientes} clientes`,
    alLimite: clientes >= plan.maxClientes,
  };
}

/**
 * El mensaje del alta bloqueada.
 *
 * Vive aquí y no en la pantalla porque lo dicen dos: el botón de la cartera y
 * el chip del selector. Dice el número, porque "llegaste al límite" sin decir
 * cuál obliga a ir a buscarlo.
 */
export function motivoDelTope(plan: Plan): string {
  return (
    `El plan ${plan.nombre} llega hasta ${plan.maxClientes} ` +
    `${plan.maxClientes === 1 ? 'cliente' : 'clientes'}. ` +
    'Cambia de plan para dar de alta más.'
  );
}
