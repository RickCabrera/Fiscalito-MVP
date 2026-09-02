/**
 * La cartera pedida al BACKEND, no a Firestore. (R-07)
 *
 * Misma forma que `carteraFirestore.ts` —a propósito— para que
 * `cartera.ts` pueda elegir entre las dos sin que ninguna pantalla se entere.
 *
 * QUÉ RESUELVE, QUE NO ES MOVER LAS LLAMADAS DE LADO
 * ---------------------------------------------------
 * Hoy hay **dos dueños del mismo dato**: el front escribe Firestore directo y
 * el backend calcula sobre la plantilla que el front le manda en el body. Con la
 * plantilla viajando por el cliente, "afirmar un cliente y calcular otro" cabe
 * en un JSON, y el guard del backend no puede atraparlo. Con un dueño, el
 * backend lee la plantilla él mismo y deja de creerle al navegador.
 *
 * EL TOKEN VA EN CADA REQUEST, Y NO SE CACHEA A MANO
 * --------------------------------------------------
 * `getIdToken()` ya cachea y refresca solo; guardarlo en una variable sería
 * reimplementar peor el manejo de expiración y garantizar un 401 espurio una
 * hora después de entrar.
 */

import { auth } from './firebase';
import { conPeriodoAlDia } from './carteraFirestore';
import { cuerpoDeError, detalleDelError } from './errorApi';
import type { EmpleadoCartera, ClienteCartera } from './carteraApi';
import type { CarteraCargada } from './carteraFirestore';

const BASE_URL = import.meta.env.VITE_FISCAL_AGENT_URL || 'http://localhost:8000';
const V1 = `${BASE_URL}/api/v1`;

/** El mismo tope que la lectura de Firestore. Ningún `await` sin cota. */
const TIMEOUT_MS = 8000;

async function encabezados(): Promise<HeadersInit> {
  const usuario = auth.currentUser;
  if (!usuario) throw new Error('Hace falta una sesión para leer tu cartera.');
  return {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${await usuario.getIdToken()}`,
  };
}

async function pedir<T>(ruta: string, init: RequestInit = {}): Promise<T> {
  const control = new AbortController();
  const temporizador = setTimeout(() => control.abort(), TIMEOUT_MS);
  try {
    const res = await fetch(`${V1}${ruta}`, {
      ...init,
      headers: await encabezados(),
      signal: control.signal,
    });
    if (!res.ok) {
      throw new Error(detalleDelError(res, await cuerpoDeError(res)));
    }
    return (await res.json()) as T;
  } finally {
    clearTimeout(temporizador);
  }
}

/**
 * La cartera del despacho desde el backend.
 *
 * **Nunca lanza**, igual que la de Firestore, y con la misma semántica que R-06
 * fijó: vacía es vacía (y escribible), un fallo es un fallo, y **nunca** se
 * sustituye por datos de otra persona.
 */
export async function cargarCartera(uid: string | null): Promise<CarteraCargada> {
  if (!uid) return { clientes: [], origen: 'firestore', error: null };
  try {
    const { clientes } = await pedir<{ clientes: Omit<ClienteCartera, 'empleados'>[] }>(
      '/cartera/clientes',
    );
    // Los empleados van en su propia llamada por cliente. Es una petición por
    // cliente, igual que hace hoy la lectura de Firestore: son subcolecciones y
    // no hay forma de traerlas en la misma consulta.
    const conEmpleados = await Promise.all(
      clientes.map(async (c) => {
        const { empleados } = await pedir<{ empleados: EmpleadoCartera[] }>(
          `/cartera/clientes/${encodeURIComponent(c.id)}/empleados`,
        );
        return { ...c, empleados } as ClienteCartera;
      }),
    );
    // **El mismo refresco de periodo que hace el camino de Firestore.** Sin
    // esto los dos caminos NO producían el mismo `ClienteCartera[]`: el backend
    // devolvía el snapshot guardado, y `periodo_sugerido` alimenta la
    // `fecha_pago` que va al motor — de la que dependen UMA, salario mínimo, la
    // tarifa del Anexo 8 y el transitorio de enero del subsidio (§D18). Dos
    // semanas después de sembrar, cada cliente arrancaría con una quincena
    // vencida. `carteraFirestore` documenta ese modo de falla y lo repara al
    // leer; este camino lo reintroducía. Lo midió el revisor de motor.
    return { clientes: await conPeriodoAlDia(conEmpleados), origen: 'firestore', error: null };
  } catch (e) {
    const detalle = e instanceof Error ? e.message : 'error desconocido';
    return { clientes: [], origen: 'firestore', error: `No se pudo leer tu cartera: ${detalle}` };
  }
}

export async function guardarCliente(
  _uid: string,
  cliente: Omit<ClienteCartera, 'empleados'>,
): Promise<void> {
  // El uid NO viaja: lo resuelve el backend del ID token. Se acepta el
  // parámetro para que la firma sea la misma que la de Firestore y el
  // despachador no tenga que saber cuál está activa.
  await pedir(`/cartera/clientes/${encodeURIComponent(cliente.id)}`, {
    method: 'PUT',
    body: JSON.stringify(cliente),
  });
}

export async function borrarCliente(_uid: string, clienteId: string): Promise<void> {
  await pedir(`/cartera/clientes/${encodeURIComponent(clienteId)}`, { method: 'DELETE' });
}

export async function guardarEmpleado(
  _uid: string,
  clienteId: string,
  empleado: EmpleadoCartera,
): Promise<void> {
  await pedir(
    `/cartera/clientes/${encodeURIComponent(clienteId)}/empleados/${encodeURIComponent(empleado.empleado_no)}`,
    { method: 'PUT', body: JSON.stringify(empleado) },
  );
}

export async function borrarEmpleado(
  _uid: string,
  clienteId: string,
  empleadoNo: string,
): Promise<void> {
  await pedir(
    `/cartera/clientes/${encodeURIComponent(clienteId)}/empleados/${encodeURIComponent(empleadoNo)}`,
    { method: 'DELETE' },
  );
}

/**
 * La siembra **no existe en el backend**, y es deliberado.
 *
 * Copiar los tres clientes de demostración es una función de desarrollo (R-06),
 * y darle al backend un endpoint que escribe salarios de terceros en la cuenta
 * de quien llame sería regalar exactamente la escalada que R-06 vino a cerrar.
 * Con el backend como dueño, sembrar es dar de alta los clientes uno por uno.
 */
export async function sembrarDemo(uid: string): Promise<boolean> {
  // El parámetro se nombra y se usa en el mensaje —en vez de silenciarlo con un
  // `_`— para que la firma cuadre con la de Firestore sin pelearse con el lint.
  // La aridad importa: el despachador intercambia las dos implementaciones sin
  // que TypeScript compare sus formas, así que una que sobre o falte sería
  // `undefined` en producción el día que alguien encienda el flag. Lo cazó un
  // test que compara `.length`.
  throw new Error(
    'La siembra de demostración no está disponible con el backend como dueño de la ' +
      `cartera (cuenta ${uid}). Da de alta los clientes desde la pantalla.`,
  );
}
