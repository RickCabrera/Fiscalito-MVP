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
 * **Qué vale como "encendido"** lo decide `flagEncendido`, igual que
 * `VITE_MODO_EMPRESA_UNICA`: `1`, `true`, `on`, `yes`, `si` y `sí`. Hasta T2
 * esto comparaba `=== '1'` y nada más, así que un `.env` con
 * `VITE_CARTERA_BACKEND=true` dejaba el backend apagado **sin decirlo** — y eso
 * no se ve como un error de configuración, se ve como un backend que "no hace
 * nada" cuando en realidad nadie lo llamó.
 *
 * NO HAY MIGRACIÓN DE DATOS. Las rutas de Firestore son las mismas de los dos
 * lados (`users/{uid}/clientes/{id}/empleados/{id}`), así que encender el
 * interruptor no mueve un solo documento y apagarlo tampoco.
 */

import * as firestore from './carteraFirestore';
import * as backend from './carteraBackend';
import { flagEncendido } from './flagEncendido';

/**
 * `true` si el backend es el dueño del dato. Default: **no**.
 *
 * **Es una `const`, no una función, y eso NO es un descuido**: el dueño del dato
 * se decide una vez por proceso, porque dos pantallas leyendo dueños distintos
 * en la misma sesión sería peor que cualquiera de los dos. Comparte la lectura
 * con `modoEmpresaUnica()` desde T2, pero no la forma: aquél se consulta en
 * cada render y sí es función. La consecuencia práctica es que `vi.stubEnv` no
 * puede voltear este flag dentro de un test —se congela al importar el módulo—,
 * así que `cartera.test.ts` sólo puede pinnear el default.
 */
export const BACKEND_ES_DUENO = flagEncendido(import.meta.env.VITE_CARTERA_BACKEND);

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
