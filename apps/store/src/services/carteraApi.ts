/**
 * Cliente REST del modelo canónico de la cartera (G-01, G-02).
 *
 * NINGUNA CONSTANTE FISCAL VIVE AQUÍ, igual que en `despachoApi.ts`: ni el
 * factor de integración, ni el piso, ni el tope. **El SBC lo calcula el motor**
 * (`POST /nomina/sbc`); reimplementar el Art. 27 en TypeScript sería una segunda
 * verdad sin ningún test que la cuide.
 */

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

export type TipoContrato = 'indeterminado' | 'determinado' | 'obra_determinada' | 'prueba';
export type EstatusEnrolamiento = 'pendiente' | 'enrolado';

export interface Prestaciones {
  dias_aguinaldo: number;
  /** 0 = los de ley que le tocan a su antigüedad (Art. 76 LFT). */
  dias_vacaciones: number;
  /** Proporción, no porcentaje: 0.25 es el mínimo de ley. */
  prima_vacacional: string;
}

export interface EmpleadoCartera {
  /** Llave del CÁLCULO. Nunca vacía, única dentro del cliente. */
  empleado_no: string;
  nombre: string;
  puesto: string;
  salario_diario: string;
  salario_diario_integrado: string;
  zona: string;
  fecha_alta: string | null;
  tipo_contrato: TipoContrato;
  prestaciones: Prestaciones;
  /** Vacío cuando no se conoce. **Nunca se inventa.** */
  nss: string;
  /**
   * Llave del CHECADOR (`employeeNoString` del Hikvision). `null` = el empleado
   * **no está vinculado**: sus checadas no se pueden atribuir a nadie.
   * Es distinta de `empleado_no`, que es la del cálculo y nunca es nula.
   */
  employee_no: string | null;
  enrolamiento: EstatusEnrolamiento;
}

export interface ClienteCartera {
  id: string;
  nombre: string;
  giro: string;
  origen: string;
  prima_riesgo: string;
  clase_riesgo: number | null;
  clave_periodicidad: string;
  zona: string;
  periodo_sugerido: { inicio: string; fin: string; fecha_pago: string | null };
  empleados: EmpleadoCartera[];
}

export interface EmpleadosSemilla {
  cliente_id: string;
  origen: string;
  total: number;
  /** Cuántos NO tienen `employee_no`. Lo cuenta el backend, no la UI. */
  sin_vincular: number;
  empleados: EmpleadoCartera[];
}

/** `true` si sus checadas no tienen con qué casarse. */
export function estaVinculado(e: EmpleadoCartera): boolean {
  return Boolean(e.employee_no);
}

export function contarSinVincular(empleados: EmpleadoCartera[]): number {
  return empleados.filter((e) => !estaVinculado(e)).length;
}

// ── Llamadas ──

export async function obtenerEmpleadosSemilla(clienteId: string): Promise<EmpleadosSemilla> {
  const res = await fetch(`${V1}/despacho/clientes/${encodeURIComponent(clienteId)}/empleados`);
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
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });
  return leer<SBCResponse>(res, 'No se pudo integrar el salario');
}
