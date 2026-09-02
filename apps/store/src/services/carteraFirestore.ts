/**
 * La cartera del despacho en Firestore, por uid (G-03, R-06).
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
 *
 * R-06: EL CATÁLOGO DEL BACKEND DEJA DE HACERSE PASAR POR LA CARTERA
 * ------------------------------------------------------------------
 * G-03 puso aquí un fallback deliberado: si Firestore fallaba **o devolvía
 * vacío**, se mostraba el catálogo de demostración del backend para que la demo
 * nunca se rompiera. Este archivo lo declaraba, con todas sus letras: *"el
 * fallback DERROTA el criterio de G-03 — dos cuentas distintas ven los mismos
 * tres clientes"*.
 *
 * La demo pasó y R-01 desplegó las reglas, así que la razón de aquel fallback ya
 * no existe y su costo sí. Ahora:
 *
 * - **Cero clientes es cero clientes.** Una cartera vacía se devuelve como
 *   vacía y ESCRIBIBLE (`origen: 'firestore'`), para que la pantalla diga "aún
 *   no tienes clientes, crea el primero". Confundir "no tienes" con "hubo un
 *   error" era lo que impedía que una cuenta nueva pudiera empezar.
 * - **Un fallo es un fallo.** Si Firestore niega, tarda o revienta, se devuelve
 *   el error para que la pantalla lo diga y ofrezca reintentar. **No se
 *   sustituye por datos de otra persona**, que es lo que hacía antes.
 * - `carteraDelBackend()` **no se borra**: pasa a ser exclusivamente la fuente
 *   de la SIEMBRA, y sembrar es un botón visible sólo en cuentas de desarrollo.
 *
 * LAS COTAS SE QUEDAN, Y NO SON DECORACIÓN
 * ----------------------------------------
 * Ningún `await` sin tope. El modo de falla peligroso de Firestore no es
 * reventar —eso se atrapa— sino **colgarse**: sin cota, el proveedor no resuelve
 * nunca, `loading` se queda en `true` para siempre y la pantalla no llega ni a
 * poder decir que algo salió mal.
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
import { CLIENTE_DEMO } from './nominaDemoApi';
import {
  obtenerEmpleadosSemilla,
  type EmpleadoCartera,
  type ClienteCartera,
} from './carteraApi';

/** Ninguna lectura de Firestore puede colgar el primer pintado más que esto. */
const TIMEOUT_MS = 2500;

/**
 * El respaldo lleva **su propio tope, más holgado**.
 *
 * `carteraDelBackend()` dispara 1 + 3×2 = **siete** requests. Con los mismos
 * 2500 ms de Firestore, un backend lento pero VIVO —un arranque en frío— caía
 * en el timeout y devolvía `clientes: []`, o sea la pantalla vacía que todo este
 * archivo existe para evitar, con el fallback puesto y todo. Cotarlo sigue
 * siendo obligatorio: sin cota, colgado es para siempre.
 */
const TIMEOUT_RESPALDO_MS = 8000;

/** De dónde salió lo que se está viendo. La pantalla lo dice, no lo esconde. */
export type OrigenCartera = 'firestore' | 'backend';

export interface CarteraCargada {
  clientes: ClienteCartera[];
  origen: OrigenCartera;
  /**
   * Por qué no se pudo leer la cartera. `null` = se leyó bien (aunque esté
   * vacía: **vacía no es un error**, y confundirlos fue lo que impidió que una
   * cuenta nueva pudiera empezar).
   */
  error: string | null;
}

function conTimeout<T>(promesa: Promise<T>, que: string, ms = TIMEOUT_MS): Promise<T> {
  let temporizador: ReturnType<typeof setTimeout>;
  return Promise.race([
    promesa,
    new Promise<T>((_, rechazar) => {
      temporizador = setTimeout(() => rechazar(new Error(`${que} tardó más de ${ms} ms`)), ms);
    }),
    // Se limpia el timer gane quien gane: sin esto queda uno colgado por
    // llamada. Inofensivo con topes cortos, sucio en cuanto alguien llame esto
    // en bucle.
  ]).finally(() => clearTimeout(temporizador));
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
 * **Desde R-06 es SÓLO la semilla.** Dejó de ser el respaldo de `cargarCartera`:
 * un catálogo con los clientes de otra persona no puede sustituir a una cartera
 * que no se pudo leer. Se sigue usando —lo dispara el botón de sembrar, visible
 * sólo en cuentas de desarrollo— porque es el camino probado, con tests de E-02
 * y E-03 encima.
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
  const vacia = (error: string | null): CarteraCargada => ({
    clientes: [],
    // `firestore` aunque esté vacía: es la cartera del usuario, y por lo tanto
    // ESCRIBIBLE. `CarteraContext` deriva `soloLectura` de este campo, así que
    // devolver `backend` aquí haría que el botón "crea tu primer cliente"
    // rebotara con "esta cartera es el catálogo de demostración". Es una
    // palabra, y es la tarea entera.
    origen: 'firestore',
    error,
  });

  if (!uid) return vacia(null);

  try {
    const guardados = await conTimeout(leerDeFirestore(uid), 'La cartera de Firestore');
    // Cero clientes NO es un error, y ya no se trata como tal. Antes se caía al
    // catálogo del backend "por si acaso", y el resultado era que una cuenta
    // nueva nunca podía verse a sí misma vacía.
    const clientes = await conPeriodoAlDia(guardados);
    return { clientes, origen: 'firestore', error: null };
  } catch (e) {
    const detalle = e instanceof Error ? e.message : 'error desconocido';
    // **No se sustituye por el catálogo de demostración.** Enseñar los clientes
    // de otra persona cuando falla la lectura de los tuyos es peor que una
    // pantalla vacía con un botón de reintentar: se ve bien, y es mentira.
    return vacia(`No se pudo leer tu cartera: ${detalle}`);
  }
}

/**
 * Refresca el periodo sugerido de la cartera contra el backend.
 *
 * **El periodo sugerido es DERIVADO, no dato del cliente.** Es
 * `quincena(hoy)` —la última quincena ya terminada— y el backend lo reevalúa en
 * cada request. Lo que quedó escrito en Firestore es un snapshot del momento de
 * sembrar: dos semanas después, cada cliente nacería con una quincena vencida,
 * el panel saldría vacío y `sinChecadasEnElPeriodo` pediría confirmación por una
 * razón que nadie entendería.
 *
 * Se refresca al leer y **nunca se rompe por esto**: si el backend no responde
 * —o se cuelga, de ahí el `conTimeout`— se queda el snapshot, que es peor que
 * estar al día pero mejor que no tener cartera. Sin la cota, una API colgada
 * dejaba `cargarCartera` sin resolver nunca: spinner eterno en la lista y, peor,
 * `deLaCartera` en `null` para siempre, que rompe la auto-sanación del error de
 * carga. Es el mismo agujero que se acababa de cerrar en `sembrarDemo`.
 */
async function conPeriodoAlDia(clientes: ClienteCartera[]): Promise<ClienteCartera[]> {
  if (clientes.length === 0) return clientes;
  try {
    const { periodo_sugerido } = await conTimeout(
      obtenerCliente(CLIENTE_DEMO),
      'El periodo sugerido',
    );
    return clientes.map((c) => ({ ...c, periodo_sugerido }));
  } catch {
    return clientes;
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
  // Quién puede llamar aquí lo decide la PANTALLA (`esCuentaDeDesarrollo`), no
  // este módulo: la comprobación necesita el email de la sesión y esto es un
  // servicio sin contexto. Se dice para que quede claro que no es un descuido.
  // Con cota, como todo lo demás de este archivo. Sin ella, unas reglas que
  // cuelguen en vez de negar dejaban al contador clickeando un botón que no
  // hacía nada, para siempre y sin mensaje.
  const existentes = await conTimeout(getDocs(clientesRef(uid)), 'La lectura de tu cartera');
  if (!existentes.empty) return false;

  const semilla = await conTimeout(
    carteraDelBackend(),
    'El catálogo de demostración',
    TIMEOUT_RESPALDO_MS,
  );
  const lote = writeBatch(db);
  for (const cliente of semilla) {
    const { empleados, ...datos } = cliente;
    lote.set(clienteRef(uid, cliente.id), datos);
    for (const e of empleados) {
      lote.set(empleadoRef(uid, cliente.id, e.empleado_no), e);
    }
  }
  await conTimeout(lote.commit(), 'La escritura de tu cartera');
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
