/**
 * La cartera del despacho en Firestore, por uid (G-03).
 *
 * `users/{uid}/clientes/{clienteId}` y `.../empleados/{empleadoId}`.
 *
 * POR QUÉ `users/` Y NO `contadores/`
 * -----------------------------------
 * PLAN_NOMINA §3.3 prescribe `contadores/{uid}`. Se usa `users/{uid}` porque es
 * lo que la app YA escribe: `ProfileContext` guarda ahí el perfil y
 * `declaracionesHistory` la subcolección `declaraciones`. Migrar el perfil a
 * otro árbol no es de esta tarea, y tener el perfil en un árbol y la cartera en
 * otro obligaría a dos reglas de seguridad distintas para el mismo dueño.
 * §3.3 se corrigió en el mismo PR para que la próxima sesión no escriba reglas
 * para el árbol equivocado.
 *
 * EL BACKEND PINTA PRIMERO. FIRESTORE ES OVERLAY.
 * -----------------------------------------------
 * Regla de Ricardo: la demo funciona en TODO momento. El modo de falla
 * peligroso NO es que Firestore truene —eso se atrapa— sino que **devuelva
 * vacío**: con unas reglas que permitan leer y nieguen escribir, la siembra
 * nunca se escribe, la lectura no lanza, y queda una app que se ve bien y no
 * tiene clientes. Por eso:
 *
 * 1. Cero devuelto se trata **igual** que error: se cae al catálogo del backend.
 * 2. Toda lectura lleva **timeout duro**. Ningún `await` sin cota en el camino
 *    de la demo.
 * 3. Sembrar **no es precondición de renderizar**: corre en segundo plano.
 *
 * CONSECUENCIA QUE HAY QUE DECIR EN VOZ ALTA
 * ------------------------------------------
 * Con el fallback puesto, una segunda cuenta cuyas reglas nieguen el acceso cae
 * al backend y ve **los mismos tres clientes**. O sea: el fallback **derrota el
 * criterio de G-03** ("dos cuentas distintas ven carteras distintas"). Gana la
 * demo, porque Ricardo lo puso primero. G-03 sólo se cumple con las reglas de
 * `firestore.rules` desplegadas, y eso es acción suya.
 */

import {
  collection,
  deleteDoc,
  doc,
  getDocs,
  setDoc,
  writeBatch,
} from 'firebase/firestore';
import { db } from './firebase';
import { obtenerClientes, obtenerCliente, type ClienteResumen } from './despachoApi';
import {
  obtenerEmpleadosSemilla,
  type EmpleadoCartera,
  type ClienteCartera,
} from './carteraApi';

/** Ninguna lectura de Firestore puede colgar el primer pintado más que esto. */
const TIMEOUT_MS = 2500;

/** De dónde salió lo que se está viendo. La pantalla lo dice, no lo esconde. */
export type OrigenCartera = 'firestore' | 'backend';

export interface CarteraCargada {
  clientes: ClienteCartera[];
  origen: OrigenCartera;
  /** Por qué se cayó al backend, cuando pasó. `null` = todo bien. */
  motivoFallback: string | null;
}

function conTimeout<T>(promesa: Promise<T>, que: string): Promise<T> {
  return Promise.race([
    promesa,
    new Promise<T>((_, rechazar) =>
      setTimeout(() => rechazar(new Error(`${que} tardó más de ${TIMEOUT_MS} ms`)), TIMEOUT_MS),
    ),
  ]);
}

// ── Rutas de la colección ──

const clientesRef = (uid: string) => collection(db, 'users', uid, 'clientes');
const clienteRef = (uid: string, id: string) => doc(db, 'users', uid, 'clientes', id);
const empleadosRef = (uid: string, clienteId: string) =>
  collection(db, 'users', uid, 'clientes', clienteId, 'empleados');
const empleadoRef = (uid: string, clienteId: string, id: string) =>
  doc(db, 'users', uid, 'clientes', clienteId, 'empleados', id);

// ── Lectura ──

async function leerDeFirestore(uid: string): Promise<ClienteCartera[]> {
  const snap = await getDocs(clientesRef(uid));
  const clientes = await Promise.all(
    snap.docs.map(async (d) => {
      const empleados = await getDocs(empleadosRef(uid, d.id));
      return {
        ...(d.data() as Omit<ClienteCartera, 'id' | 'empleados'>),
        id: d.id,
        empleados: empleados.docs.map((e) => ({ ...(e.data() as EmpleadoCartera) })),
      };
    }),
  );
  return clientes;
}

/**
 * El catálogo del backend, en la forma de la cartera.
 *
 * Es el camino **probado** —E-02 y E-03 corren sobre él y tiene tests— y por eso
 * es el fallback y también la semilla.
 */
export async function carteraDelBackend(): Promise<ClienteCartera[]> {
  const resumenes = await obtenerClientes();
  return Promise.all(
    resumenes.map(async (r: ClienteResumen) => {
      const [ficha, empleados] = await Promise.all([
        obtenerCliente(r.id),
        obtenerEmpleadosSemilla(r.id),
      ]);
      return {
        id: r.id,
        nombre: r.nombre,
        giro: r.giro,
        origen: r.origen,
        prima_riesgo: r.prima_riesgo,
        clase_riesgo: r.clase_riesgo,
        clave_periodicidad: r.clave_periodicidad,
        zona: r.zona,
        periodo_sugerido: ficha.periodo_sugerido,
        empleados: empleados.empleados,
      };
    }),
  );
}

/**
 * La cartera del despacho, con el backend como red.
 *
 * **Nunca lanza.** Si algo sale mal en el camino de Firestore, devuelve la
 * cartera del backend y el motivo. Que la pantalla decida qué decir.
 */
export async function cargarCartera(uid: string | null): Promise<CarteraCargada> {
  const respaldo = async (motivo: string): Promise<CarteraCargada> => ({
    clientes: await carteraDelBackend(),
    origen: 'backend',
    motivoFallback: motivo,
  });

  if (!uid) return respaldo('No hay sesión: se muestra el catálogo de demostración.');

  try {
    const clientes = await conTimeout(leerDeFirestore(uid), 'La cartera de Firestore');
    if (clientes.length === 0) {
      // NO es lo mismo que un error, y por eso se trata igual: unas reglas que
      // permitan leer y nieguen escribir dejan la cartera vacía sin lanzar
      // nada, y una app que se ve bien y no tiene clientes es peor que un error.
      return respaldo('Tu cartera está vacía: se muestra el catálogo de demostración.');
    }
    return { clientes, origen: 'firestore', motivoFallback: null };
  } catch (e) {
    const detalle = e instanceof Error ? e.message : 'error desconocido';
    return respaldo(`No se pudo leer tu cartera (${detalle}).`);
  }
}

// ── Siembra ──

/**
 * Copia los tres clientes de demostración a la cartera del uid.
 *
 * **Idempotente y en segundo plano.** No es precondición de que la pantalla
 * pinte: si falla, el usuario ya está viendo la cartera del backend.
 * Devuelve `true` sólo si escribió algo.
 */
export async function sembrarDemo(uid: string): Promise<boolean> {
  const existentes = await getDocs(clientesRef(uid));
  if (!existentes.empty) return false;

  const semilla = await carteraDelBackend();
  const lote = writeBatch(db);
  for (const cliente of semilla) {
    const { empleados, ...datos } = cliente;
    lote.set(clienteRef(uid, cliente.id), datos);
    for (const e of empleados) {
      lote.set(empleadoRef(uid, cliente.id, e.empleado_no), e);
    }
  }
  await lote.commit();
  return true;
}

// ── Escritura ──

export async function guardarCliente(
  uid: string,
  cliente: Omit<ClienteCartera, 'empleados'>,
): Promise<void> {
  await setDoc(clienteRef(uid, cliente.id), cliente, { merge: true });
}

export async function borrarCliente(uid: string, clienteId: string): Promise<void> {
  // Firestore no borra subcolecciones en cascada: sin esto los empleados
  // quedarían huérfanos y reaparecerían al recrear un cliente con el mismo id.
  const empleados = await getDocs(empleadosRef(uid, clienteId));
  const lote = writeBatch(db);
  empleados.docs.forEach((d) => lote.delete(d.ref));
  lote.delete(clienteRef(uid, clienteId));
  await lote.commit();
}

export async function guardarEmpleado(
  uid: string,
  clienteId: string,
  empleado: EmpleadoCartera,
): Promise<void> {
  await setDoc(empleadoRef(uid, clienteId, empleado.empleado_no), empleado, { merge: true });
}

export async function borrarEmpleado(
  uid: string,
  clienteId: string,
  empleadoNo: string,
): Promise<void> {
  await deleteDoc(empleadoRef(uid, clienteId, empleadoNo));
}
