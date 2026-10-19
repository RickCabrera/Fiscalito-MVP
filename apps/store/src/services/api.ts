/**
 * Cliente HTTP de la API (plan P).
 *
 * Toda pantalla nueva habla con el backend por aquí: adjunta el ID token de Firebase, pone
 * un tiempo límite y convierte las respuestas de error en mensajes legibles. Las rutas se
 * pasan relativas a `/api/v1` (p. ej. `apiFetch('/boveda/clientes/taller/cfdi')`).
 */

import { auth } from './firebase';
import { cuerpoDeError, detalleDelError } from './errorApi';

export const API_URL = import.meta.env.VITE_FISCAL_AGENT_URL || 'http://localhost:8000';
export const V1 = `${API_URL}/api/v1`;

const TIMEOUT_MS = 30000;

/**
 * Encabezado de autorización con la sesión actual (P0-02: todo `/api/v1` lo exige).
 *
 * Todo módulo que habla con el backend pasa por aquí, así que importa `./firebase`, que
 * sin llaves LANZA al importarse (ver `sinLlavesDeFirebase.test.ts`). En tests lo dobla
 * `src/test/setup.ts` para toda la suite.
 */
export async function encabezadoAuth(): Promise<Record<string, string>> {
  const usuario = auth.currentUser;
  if (!usuario) throw new Error('Hace falta iniciar sesión.');
  return { Authorization: `Bearer ${await usuario.getIdToken()}` };
}

export interface OpcionesApi extends Omit<RequestInit, 'body'> {
  /** Objeto que se manda como JSON. */
  json?: unknown;
  /** Cuerpo crudo (FormData para archivos). */
  body?: BodyInit;
  /** Milisegundos antes de abortar. */
  timeoutMs?: number;
}

async function pedir(ruta: string, opciones: OpcionesApi = {}): Promise<Response> {
  const { json, body, timeoutMs = TIMEOUT_MS, headers, ...resto } = opciones;
  const control = new AbortController();
  const temporizador = setTimeout(() => control.abort(), timeoutMs);
  try {
    const res = await fetch(`${V1}${ruta}`, {
      ...resto,
      headers: {
        ...(json !== undefined ? { 'Content-Type': 'application/json' } : {}),
        ...(await encabezadoAuth()),
        ...(headers as Record<string, string> | undefined),
      },
      body: json !== undefined ? JSON.stringify(json) : body,
      signal: control.signal,
    });
    if (!res.ok) throw new Error(detalleDelError(res, await cuerpoDeError(res)));
    return res;
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') {
      throw new Error('El servidor tardó demasiado en responder. Intenta de nuevo.');
    }
    throw e;
  } finally {
    clearTimeout(temporizador);
  }
}

/** Petición que devuelve JSON. */
export async function apiFetch<T>(ruta: string, opciones: OpcionesApi = {}): Promise<T> {
  const res = await pedir(ruta, opciones);
  return (await res.json()) as T;
}

/** Petición que devuelve un archivo (Blob) — XML, PDF, Excel, ZIP. */
export async function apiArchivo(ruta: string, opciones: OpcionesApi = {}): Promise<Blob> {
  const res = await pedir(ruta, opciones);
  return res.blob();
}
