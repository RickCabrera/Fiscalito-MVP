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
  /** El nombre completo, que es lo que se pinta en todas las pantallas. */
  nombre: string;
  /**
   * Los tres campos del layout del IMSS (O-04): apellidos y nombre de pila por
   * separado, 27 posiciones cada uno.
   *
   * **Se capturan; no se parten.** Partir "MARIA DE LOS ANGELES SANTA CRUZ
   * RIVERA" a la adivina produce un movimiento afiliatorio con el apellido
   * equivocado, y en español el apellido compuesto es la norma. Opcionales para
   * no romper una cartera escrita antes de O-04; quien los tenga vacíos no se
   * exporta, y el exportador lo dice con su razón.
   */
  apellido_paterno?: string;
  apellido_materno?: string;
  nombres?: string;
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

/** El horario contra el que el checador mide retardos y faltas. (O-03) */
export interface HorarioLaboral {
  /** `HH:MM`. */
  hora_entrada: string;
  hora_salida: string;
  tolerancia_minutos: number;
  /** Convención de `Date.getDay()` corrida: 0 = lunes, como `datetime.weekday()`. */
  dias_laborables: number[];
}

/**
 * Las prestaciones del patrón, que alimentan el factor de integración. (O-03)
 *
 * **Lo que NO está aquí es tan importante como lo que sí**: las tablas de ISR,
 * las cuotas del IMSS, la UMA y el salario mínimo no se configuran. Son de ley,
 * viven en el motor con su fuente publicada y se actualizan con el DOF.
 */
export interface ParametrosSalariales {
  /** Mínimo 15 (Art. 87 LFT). */
  dias_aguinaldo: number;
  /** Proporción, no porcentaje. Mínimo 0.25 (Art. 80 LFT). */
  prima_vacacional: string;
  /** Escala propia `[[años, días], ...]`. Vacía = manda la ley (Art. 76 LFT). */
  tabla_vacaciones: [number, number][];
  horario: HorarioLaboral;
}

export const PARAMETROS_DE_LEY: ParametrosSalariales = {
  dias_aguinaldo: 15,
  prima_vacacional: '0.25',
  tabla_vacaciones: [],
  horario: {
    hora_entrada: '08:00',
    hora_salida: '17:00',
    tolerancia_minutos: 15,
    dias_laborables: [0, 1, 2, 3, 4],
  },
};

export interface ClienteCartera {
  id: string;
  nombre: string;
  giro: string;
  origen: string;
  /**
   * RFC del patrón. **Opcional**: los tres clientes de demostración no lo
   * traen, y una cartera escrita antes de O-01 tampoco. Lo captura la
   * Configuración de empresa (O-01) y lo consume el exportador de O-04.
   */
  rfc?: string;
  /**
   * Registro patronal del IMSS, **11 caracteres** (10 + dígito verificador).
   * Opcional por la misma razón que `rfc`. Sin él no se pueden emitir
   * movimientos afiliatorios: son las posiciones 01-11 del layout.
   */
  registro_patronal?: string;
  /**
   * Número de guía de la subdelegación del IMSS (O-04). Va en las posiciones
   * 134-138 de cada movimiento afiliatorio. Lo asigna la subdelegación: no se
   * calcula ni se deduce.
   */
  guia_subdelegacion?: string;
  prima_riesgo: string;
  clase_riesgo: number | null;
  clave_periodicidad: string;
  zona: string;
  /**
   * Prestaciones y horario del patrón (O-03). **Opcional**: una cartera escrita
   * antes de O-03 no lo trae, y exigirlo dejaría al operador sin sus empleados
   * por un campo de más — el mismo modo de falla que `ilegibles[]` documenta.
   * Quien lo lee cae a `PARAMETROS_DE_LEY`, que es lo que la app aplicaba.
   */
  parametros?: ParametrosSalariales;
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
    headers: { 'Content-Type': 'application/json' },
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
  const res = await fetch(`${V1}/despacho/primas-de-riesgo?fecha=${encodeURIComponent(fecha)}`);
  return leer<PrimasDeRiesgo>(res, 'No se pudieron cargar las primas de riesgo');
}
