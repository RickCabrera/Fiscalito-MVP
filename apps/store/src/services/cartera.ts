/**
 * La cartera del despacho: SIEMPRE por la API. (R-07 → P0-01)
 *
 * EL BACKEND ES EL ÚNICO DUEÑO DEL DATO
 * -------------------------------------
 * Hasta P0-01 había dos implementaciones detrás de un interruptor
 * (`VITE_CARTERA_BACKEND`): Firestore desde el navegador (el default) y el backend. El
 * interruptor y la rama de Firestore se retiraron: clientes y empleados se leen y se
 * escriben en `/api/v1/cartera/*`, que los guarda en SQL y filtra por despacho. Lo que
 * había en Firestore se trae con `apps/api/scripts/migrar_firestore.py`.
 *
 * EL uid NO VIAJA
 * ---------------
 * El despacho lo resuelve el backend del ID token que `apiFetch` adjunta en cada
 * request. Ninguna función de aquí manda un uid en la URL ni en el cuerpo.
 *
 * LA LECTURA NUNCA LANZA
 * ----------------------
 * Misma semántica que fijó R-06: vacía es vacía (y escribible), un fallo es un fallo
 * con su mensaje, y **nunca** se sustituye por datos de otra persona.
 */

import { apiFetch } from './api';
import { conPeriodoAlDia } from './periodoAlDia';
import type { ClienteCartera, EmpleadoCartera, EmpleadoIlegible } from './carteraApi';

export { sembrarDemo } from './semillaDemo';

/**
 * De dónde salió lo que se está viendo. `propia` = la cartera del despacho, escribible.
 * `catalogo` = todavía no se cargó nada (o es el catálogo de demostración): sólo lectura.
 */
export type OrigenCartera = 'propia' | 'catalogo';

export interface CarteraCargada {
  clientes: ClienteCartera[];
  origen: OrigenCartera;
  /** `null` = se leyó bien, aunque esté vacía. Vacía NO es un error. */
  error: string | null;
}

/** Ninguna lectura puede colgar el primer pintado más que esto. */
const TIMEOUT_LECTURA_MS = 8000;
/** Las escrituras no bloquean un pintado; un tope corto asustaría en redes lentas. */
const TIMEOUT_ESCRITURA_MS = 10000;

const ruta = (...partes: string[]) =>
  `/cartera/clientes${partes.map((p) => `/${encodeURIComponent(p)}`).join('')}`;

interface RespuestaEmpleados {
  empleados: EmpleadoCartera[];
  ilegibles_detalle?: EmpleadoIlegible[];
}

/**
 * La cartera del despacho autenticado. **Nunca lanza.**
 *
 * Los empleados van en una llamada por cliente, y cada cliente trae también sus
 * `ilegibles` con la razón (R-10) para que la ficha los pinte.
 */
export async function cargarCartera(uid: string | null): Promise<CarteraCargada> {
  if (!uid) return { clientes: [], origen: 'propia', error: null };
  try {
    const { clientes } = await apiFetch<{ clientes: Omit<ClienteCartera, 'empleados'>[] }>(
      ruta(),
      { timeoutMs: TIMEOUT_LECTURA_MS },
    );
    const conEmpleados = await Promise.all(
      clientes.map(async (c) => {
        const r = await apiFetch<RespuestaEmpleados>(ruta(c.id, 'empleados'), {
          timeoutMs: TIMEOUT_LECTURA_MS,
        });
        return { ...c, empleados: r.empleados, ilegibles: r.ilegibles_detalle ?? [] };
      }),
    );
    // Lo guardado es un SNAPSHOT del periodo; se refresca al leer (ver `periodoAlDia`).
    return { clientes: await conPeriodoAlDia(conEmpleados), origen: 'propia', error: null };
  } catch (e) {
    const detalle = e instanceof Error ? e.message : 'error desconocido';
    return { clientes: [], origen: 'propia', error: `No se pudo leer tu cartera: ${detalle}` };
  }
}

/** Alta o edición. Lo que no es del cliente (plantilla, ilegibles) no viaja. */
export async function guardarCliente(cliente: Omit<ClienteCartera, 'empleados'>): Promise<void> {
  // La plantilla y los ilegibles son de LECTURA: no son campos del cliente.
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const { empleados, ilegibles, ...datos } = cliente as ClienteCartera;
  // P6-04: el primer cliente de una cuenta nueva nace SIN periodo (ver `CarteraContext`), y
  // "sin periodo" es `null` para la API: las fechas vacías del modal eran un 422
  // ("input is too short") y el alta del primer cliente fallaba. Lo cazó el e2e.
  const periodo_sugerido = datos.periodo_sugerido?.inicio ? datos.periodo_sugerido : null;
  await apiFetch(ruta(cliente.id), {
    method: 'PUT',
    json: { ...datos, periodo_sugerido },
    timeoutMs: TIMEOUT_ESCRITURA_MS,
  });
}

/** Baja del cliente; el backend se lleva en cascada sus empleados y dispositivos. */
export async function borrarCliente(clienteId: string): Promise<void> {
  await apiFetch(ruta(clienteId), { method: 'DELETE', timeoutMs: TIMEOUT_ESCRITURA_MS });
}

export async function guardarEmpleado(clienteId: string, empleado: EmpleadoCartera): Promise<void> {
  await apiFetch(ruta(clienteId, 'empleados', empleado.empleado_no), {
    method: 'PUT',
    json: empleado,
    timeoutMs: TIMEOUT_ESCRITURA_MS,
  });
}

export async function borrarEmpleado(clienteId: string, empleadoNo: string): Promise<void> {
  await apiFetch(ruta(clienteId, 'empleados', empleadoNo), {
    method: 'DELETE',
    timeoutMs: TIMEOUT_ESCRITURA_MS,
  });
}
