/**
 * Cliente REST del modelo canónico de la cartera (G-01, G-02).
 *
 * NINGUNA CONSTANTE FISCAL VIVE AQUÍ, igual que en `despachoApi.ts`: ni el
 * factor de integración, ni el piso, ni el tope. **El SBC lo calcula el motor**
 * (`POST /nomina/sbc`); reimplementar el Art. 27 en TypeScript sería una segunda
 * verdad sin ningún test que la cuide.
 */

import { encabezadoAuth } from './api';
import { cuerpoDeError, detalleDelError } from './errorApi';

const BASE_URL = import.meta.env.VITE_FISCAL_AGENT_URL || 'http://localhost:8000';
const V1 = `${BASE_URL}/api/v1`;

async function leer<T>(res: Response, queFallo: string): Promise<T> {
  if (!res.ok) {
    throw new Error(`${queFallo}: ${detalleDelError(res, await cuerpoDeError(res))}`);
  }
  return res.json() as Promise<T>;
}
// ── El modelo ──
// Vive en `carteraModelo.ts` desde P4 (tope de 300 líneas). Se re-exporta aquí para que
// nadie tenga que cambiar sus imports.
export * from './carteraModelo';
import type { EmpleadosSemilla } from './carteraModelo';

// ── Llamadas ──

export async function obtenerEmpleadosSemilla(clienteId: string): Promise<EmpleadosSemilla> {
  const res = await fetch(`${V1}/despacho/clientes/${encodeURIComponent(clienteId)}/empleados`, {
    headers: await encabezadoAuth(),
  });
  return leer<EmpleadosSemilla>(res, `No se pudieron cargar los empleados de ${clienteId}`);
}

// ── SBC en vivo ──

export interface SBCRequest {
  salario_diario: string;
  /** Obligatoria: piso y tope se mueven en fechas distintas (1-ene y 1-feb). */
  fecha: string;
  zona?: string;
  anios_servicio_cumplidos?: number;
  dias_aguinaldo?: number;
  dias_vacaciones?: number;
  prima_vacacional?: string;
  /**
   * Escala de vacaciones del PATRÓN (O-03). Vacía o ausente = manda la ley.
   *
   * Se manda **entera**, con `anios_servicio_cumplidos`, y el backend devuelve
   * `dias_vacaciones_aplicados`. El front **no busca el renglón**: sería una
   * segunda implementación de la misma búsqueda, y el centinela
   * `dias_vacaciones: 0` ("los de ley") sería ambiguo con una tabla presente.
   */
  tabla_vacaciones?: [number, number][];
}

export interface SBCResponse {
  factor: string;
  dias_vacaciones_aplicados: number;
  sbc_sin_acotar: string;
  sbc: string;
  /** El único camino por el que un SBC llega a ser 1 SM (Art. 36 LSS). */
  piso_aplicado: boolean;
  tope_aplicado: boolean;
  piso: string;
  tope: string;
  fundamento: string;
}

/**
 * Integra un salario diario a SBC **llamando al motor**.
 *
 * El front no calcula el factor ni acota: pregunta. Es lo que pide G-01 y es lo
 * que evita que el Art. 27 tenga dos implementaciones.
 */
export async function integrarSBC(req: SBCRequest): Promise<SBCResponse> {
  const res = await fetch(`${V1}/nomina/sbc`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(await encabezadoAuth()) },
    body: JSON.stringify(req),
  });
  return leer<SBCResponse>(res, 'No se pudo integrar el salario');
}

// ── Primas de riesgo ──

export interface PrimasDeRiesgo {
  fecha: string;
  /** Art. 72 LSS. */
  minima: string;
  maxima: string;
  /** Clase (1-5) → prima media. Aplica a EMPRESA NUEVA (Art. 73 LSS). */
  medias_por_clase: Record<string, string>;
  fundamento: string;
}

/**
 * Primas medias por clase, **con su vigencia**, desde el motor.
 *
 * No se copian a TypeScript. Una tabla fiscal sin año, sin fuente y sin test
 * propone en silencio las primas del año pasado en cuanto cambia el año — y la
 * del Art. 73 es por año, leída en el motor con función de vigencia.
 */
export async function obtenerPrimasDeRiesgo(fecha: string): Promise<PrimasDeRiesgo> {
  const res = await fetch(`${V1}/despacho/primas-de-riesgo?fecha=${encodeURIComponent(fecha)}`, {
    headers: await encabezadoAuth(),
  });
  return leer<PrimasDeRiesgo>(res, 'No se pudieron cargar las primas de riesgo');
}
