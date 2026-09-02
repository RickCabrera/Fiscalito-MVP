/**
 * Quién es el dueño de la cartera: el interruptor de R-07.
 *
 * POR QUÉ HAY UN INTERRUPTOR Y NO UN CAMBIO SECO
 * ----------------------------------------------
 * R-07 mueve la propiedad del dato de Firestore-desde-el-navegador al backend.
 * El backend ya está construido, probado contra un doble **y contra el emulador
 * de Firestore**, y con el contrato en `docs/api-contract.md`. Lo que le falta
 * para funcionar en producción no es código: son **credenciales**
 * (`GOOGLE_APPLICATION_CREDENTIALS` o Application Default Credentials), y en la
 * máquina donde se escribió esto no había ninguna — ni forma de crearlas sin
 * tocar producción, que la sesión nocturna tiene prohibido.
 *
 * Encender esto sin credenciales daría **503 en todo el CRUD**: una app rota a
 * sabiendas. Así que el default es `firestore`, la tarea queda ABIERTA en el
 * backlog, y lo que falta es una línea de `.env` más una corrida de
 * verificación.
 *
 * CÓMO SE ENCIENDE
 * ----------------
 * 1. En `apps/api`: `GOOGLE_APPLICATION_CREDENTIALS=<ruta al service account>`
 *    (o `gcloud auth application-default login`).
 * 2. `curl -H "Authorization: Bearer <ID token>" .../api/v1/cartera/clientes`
 *    → 200. Si da **503**, el mensaje dice exactamente qué falta.
 * 3. En `apps/store/.env`: `VITE_CARTERA_BACKEND=1`.
 *
 * NO HAY MIGRACIÓN DE DATOS. Las rutas de Firestore son las mismas de los dos
 * lados (`users/{uid}/clientes/{id}/empleados/{id}`), así que encender el
 * interruptor no mueve un solo documento y apagarlo tampoco.
 */

import * as firestore from './carteraFirestore';
import * as backend from './carteraBackend';

/** `true` si el backend es el dueño del dato. Default: **no**. */
export const BACKEND_ES_DUENO = import.meta.env.VITE_CARTERA_BACKEND === '1';

/**
 * La implementación activa.
 *
 * Se elige una vez, al importar, y no por llamada: dos pantallas leyendo dueños
 * distintos en la misma sesión sería peor que cualquiera de los dos.
 */
const activa = BACKEND_ES_DUENO ? backend : firestore;

export const cargarCartera = activa.cargarCartera;
export const guardarCliente = activa.guardarCliente;
export const borrarCliente = activa.borrarCliente;
export const guardarEmpleado = activa.guardarEmpleado;
export const borrarEmpleado = activa.borrarEmpleado;
export const sembrarDemo = activa.sembrarDemo;

export type { CarteraCargada, OrigenCartera } from './carteraFirestore';
