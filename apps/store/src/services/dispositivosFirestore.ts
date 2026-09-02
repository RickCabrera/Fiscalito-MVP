/**
 * Los dispositivos del cliente en Firestore, por uid. (R-04)
 *
 * `users/{uid}/clientes/{clienteId}/dispositivos/{id}` — cuelga del mismo árbol
 * que la cartera, así que lo cubre la **misma regla** ya desplegada en R-01
 * (`match /users/{uid}/{document=**}`). Se verificó con el evaluador oficial de
 * Firebase antes de escribir este archivo: el caso "dispositivo propio" sale
 * ALLOW y el de otro uid sale DENY.
 *
 * MISMAS COTAS QUE `carteraFirestore.ts`, Y POR LA MISMA RAZÓN
 * ------------------------------------------------------------
 * Ningún `await` sin tope. Un Firestore que **cuelga** en vez de negar deja al
 * operador clickeando un botón que no hace nada, para siempre y sin mensaje —
 * es el agujero que la corrida G tuvo que cerrar dos veces en el archivo de al
 * lado. Aquí se cierra desde el principio.
 *
 * LO QUE ESTE ARCHIVO **NO** HACE
 * -------------------------------
 * No habla con ningún aparato. La IP y el puerto se guardan como ficha para que
 * el técnico sepa dónde está el equipo; conectarse por ISAPI es D-08, necesita
 * el dispositivo enfrente, y desde el navegador significaría mandar las
 * credenciales del aparato al cliente.
 */

import {
  collection,
  deleteDoc,
  doc,
  getDocs,
  setDoc,
} from 'firebase/firestore';
import { db } from './firebase';
import type { DispositivoChecador } from './dispositivosApi';

/** El mismo tope que usa la cartera para sus lecturas. */
const TIMEOUT_MS = 2500;

function conTimeout<T>(promesa: Promise<T>, que: string, ms = TIMEOUT_MS): Promise<T> {
  let temporizador: ReturnType<typeof setTimeout>;
  return Promise.race([
    promesa,
    new Promise<T>((_, rechazar) => {
      temporizador = setTimeout(() => rechazar(new Error(`${que} tardó más de ${ms} ms`)), ms);
    }),
  ]).finally(() => clearTimeout(temporizador));
}

const dispositivosRef = (uid: string, clienteId: string) =>
  collection(db, 'users', uid, 'clientes', clienteId, 'dispositivos');

const dispositivoRef = (uid: string, clienteId: string, id: string) =>
  doc(db, 'users', uid, 'clientes', clienteId, 'dispositivos', id);

export async function listarDispositivos(
  uid: string,
  clienteId: string,
): Promise<DispositivoChecador[]> {
  const snap = await conTimeout(
    getDocs(dispositivosRef(uid, clienteId)),
    'La lista de dispositivos',
  );
  return snap.docs.map((d) => ({
    ...(d.data() as Omit<DispositivoChecador, 'id'>),
    id: d.id,
  }));
}

/**
 * Crea o actualiza un dispositivo.
 *
 * El id lo genera Firestore en el alta (`doc()` sin ruta) en vez de derivarlo
 * del nombre o del serial: los dos son editables y los dos pueden repetirse, y
 * un id derivado convertiría un cambio de nombre en un documento nuevo con el
 * anterior huérfano.
 */
export async function guardarDispositivo(
  uid: string,
  clienteId: string,
  dispositivo: DispositivoChecador,
): Promise<string> {
  const id = dispositivo.id || doc(dispositivosRef(uid, clienteId)).id;
  // El `id` no se escribe DENTRO del documento: ya es el nombre del documento,
  // y guardarlo dos veces deja dos verdades que se pueden separar.
  const datos: Omit<DispositivoChecador, 'id'> = {
    nombre: dispositivo.nombre,
    ip: dispositivo.ip,
    puerto: dispositivo.puerto,
    marca: dispositivo.marca,
    modelo: dispositivo.modelo,
    serial: dispositivo.serial,
    employee_nos: dispositivo.employee_nos,
    notas: dispositivo.notas,
  };
  await conTimeout(
    setDoc(dispositivoRef(uid, clienteId, id), datos, { merge: true }),
    'El guardado del dispositivo',
  );
  return id;
}

export async function borrarDispositivo(
  uid: string,
  clienteId: string,
  id: string,
): Promise<void> {
  // Sin subcolecciones debajo, así que no hay cascada que hacer — a diferencia
  // de `borrarCliente`, que sí tiene que borrar sus empleados a mano.
  await conTimeout(
    deleteDoc(dispositivoRef(uid, clienteId, id)),
    'El borrado del dispositivo',
  );
}
