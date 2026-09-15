/**
 * Cliente de los endpoints de la cartera del despacho (E-02).
 *
 * DEMO — se borra en F2 junto con el resto de la épica.
 *
 * NINGUNA CONSTANTE FISCAL VIVE AQUÍ, igual que en `nominaDemoApi.ts`: ni los
 * empleados, ni la prima de riesgo, ni el periodo. Todo sale del backend, que
 * es quien tiene el fundamento legal y los tests que lo verifican.
 */

import { cuerpoDeError, detalleDelError } from './errorApi';

const BASE_URL = import.meta.env.VITE_FISCAL_AGENT_URL || 'http://localhost:8000';
const V1 = `${BASE_URL}/api/v1`;

/** Empleado tal como lo devuelve la ficha del cliente. */
export interface EmpleadoCliente {
  empleado_no: string;
  nombre: string;
  puesto: string;
  /** Los cuatro campos que `POST /nomina/calcular-periodo` espera, con el mismo
   *  nombre y tipo: la pantalla los manda tal cual, sin remapear. */
  salario_diario: string;
  salario_diario_integrado: string;
  zona: string;
  /** `null` cuando no se conoce: en el caso real el CFDI timbrado no la trae. */
  fecha_alta: string | null;
  antiguedad_anios: number | null;
  factor: string;
  /** `true` = cociente observado (SDI ÷ SD), no el factor de ley del Art. 27.
   *  Puede incluir prestaciones superiores que el CFDI no desglosa. */
  factor_implicito: boolean;
}

export interface ClienteResumen {
  id: string;
  nombre: string;
  giro: string;
  /** `fixtures-s04` (caso real anonimizado) o `sintetico` (inventado). */
  origen: string;
  num_empleados: number;
  prima_riesgo: string;
  clase_riesgo: number | null;
  clave_periodicidad: string;
  zona: string;
  /**
   * Régimen fiscal del cliente (T1). Opcional por la misma razón que en
   * `ClienteCartera`: el catálogo de demostración del backend no lo trae.
   */
  regimen?: string;
}

export interface ClienteDetalle extends ClienteResumen {
  empleados: EmpleadoCliente[];
  periodo_sugerido: { inicio: string; fin: string; fecha_pago: string | null };
  /** Fecha contra la que se midieron antigüedad y factor. NO es hoy. */
  fecha_referencia: string;
}

/**
 * Lee el error del cuerpo si el backend lo mandó en su sobre habitual
 * (`{exito: false, error}`). El 404 de la ficha usa ese mismo sobre a
 * propósito, así que aquí hay un solo camino para todos los errores.
 *
 * La traducción vive en `errorApi.ts` porque `nominaDemoApi.ts` necesita la
 * misma y un mensaje con dos redacciones distintas es un mensaje que nadie
 * mantiene. Ahí está documentado por qué un 404 con `detail` string no es el
 * mismo 404 que uno con sobre propio.
 */
async function leer<T>(res: Response, queFallo: string): Promise<T> {
  if (!res.ok) {
    throw new Error(`${queFallo}: ${detalleDelError(res, await cuerpoDeError(res))}`);
  }
  return res.json() as Promise<T>;
}

export async function obtenerClientes(): Promise<ClienteResumen[]> {
  const res = await fetch(`${V1}/despacho/clientes`);
  const cuerpo = await leer<{ clientes: ClienteResumen[] }>(res, 'No se pudo cargar la cartera');
  return cuerpo.clientes;
}

export async function obtenerCliente(clienteId: string): Promise<ClienteDetalle> {
  const res = await fetch(`${V1}/despacho/clientes/${encodeURIComponent(clienteId)}`);
  return leer<ClienteDetalle>(res, `No se pudo cargar el cliente ${clienteId}`);
}

/**
 * Qué regla de cómputo produjo la fecha límite. **No es adorno.**
 *
 * `knowledge_base/nomina/25_calendario_laboral_2026.md` §4 advierte que juntar
 * obligaciones del IMSS y del SAT en una vista sin distinguir su regla "es un
 * bug esperando": el viernes es inhábil para el IMSS y hábil para el SAT, así
 * que el mismo mes puede tener dos fechas. `imss_sin_prorroga` NO es `imss`:
 * etiquetar así la prima de RT prometería una prórroga que no ocurre (§D23).
 */
export type RegimenDePlazo = 'imss' | 'imss_sin_prorroga' | 'imss_aviso' | 'sat' | 'lft';

export interface ObligacionPatronal {
  cliente_id: string;
  cliente_nombre: string;
  /** Id estable del TIPO de obligación. Es lo que se agrupa, nunca el nombre. */
  clave: string;
  nombre: string;
  descripcion: string;
  fecha_limite: string;
  periodicidad: string;
  /** Qué periodo REPORTA, que no es el de su vencimiento. */
  periodo_cubierto: string;
  fundamento: string;
  regimen_de_plazo: RegimenDePlazo;
  /** `true` = puede no aplicarle a este patrón y el modelo no alcanza para saberlo. */
  condicional: boolean;
  nota: string;
}

export interface CalendarioPatronal {
  anio_de_las_cuotas: number;
  /** Primer vencimiento. NO es el 1 de enero: las cuotas de enero vencen en
   *  febrero. `null` sólo con la lista vacía. */
  cubre_desde: string | null;
  /** Último vencimiento, en enero del año siguiente. `null` con la lista vacía. */
  cubre_hasta: string | null;
  total_obligaciones: number;
  obligaciones: ObligacionPatronal[];
  /** Lo que la respuesta no cubre, redactado por el backend. */
  advertencias: string[];
}

/**
 * Calendario patronal de toda la cartera.
 *
 * `anio` es el año **de las cuotas**, no el del vencimiento. Se manda siempre
 * explícito: el default del backend es el año en curso, y una pantalla cuyo
 * contenido cambia solo al pasar de año es justo lo que `despacho_demo.py`
 * evita en el resto de la demo.
 */
/**
 * El calendario patronal.
 *
 * `empresaUnica` no tiene default y se pasa siempre desde la pantalla, a
 * propósito: un default silencioso aquí decidiría por su cuenta si el backend
 * hace fan-out sobre el catálogo de demostración, y ese es justo el tipo de
 * decisión que O-01 saca de los servicios y sube a un solo lugar
 * (`modoEmpresaUnica`).
 */
export async function obtenerCalendarioPatronal(
  anio: number,
  empresaUnica: boolean,
): Promise<CalendarioPatronal> {
  const res = await fetch(
    `${V1}/despacho/calendario?anio_de_las_cuotas=${anio}&empresa_unica=${empresaUnica}`,
  );
  return leer<CalendarioPatronal>(res, 'No se pudo cargar el calendario patronal');
}

/** Etiqueta legible del origen, para no enseñar el slug crudo en pantalla. */
export function etiquetaOrigen(origen: string): string {
  if (origen === 'fixtures-s04') return 'Caso real anonimizado';
  if (origen === 'sintetico') return 'Datos sintéticos';
  return origen;
}

/** La prima viaja como fracción (0.0113065) y se muestra como porcentaje. */
export function primaComoPorcentaje(prima: string): string {
  const n = Number(prima);
  if (!Number.isFinite(n)) return prima;
  return `${(n * 100).toFixed(5)} %`;
}

// ── Periodo sugerido por periodicidad (O-03) ──

export interface PeriodoSugerido {
  clave_periodicidad: string;
  periodo: { inicio: string; fin: string; fecha_pago: string | null };
  dias_naturales: number;
}

/**
 * El último periodo terminado, **según la periodicidad del patrón**.
 *
 * POR QUÉ NO SE CALCULA AQUÍ
 * --------------------------
 * De la `fecha_pago` que sale de aquí dependen la UMA, el salario mínimo, la
 * tarifa del Anexo 8 y el transitorio de enero del subsidio (§D18). Replicar la
 * regla en TypeScript sería una segunda verdad sobre con qué valores se calcula
 * la nómina — es la misma razón por la que `CarteraContext` ya se niega a
 * reimplementar `quincena(hoy)`.
 *
 * Y hay una razón nueva de O-03: el backend **valida lo que propone** contra
 * `duracion_periodo`, así que nunca devuelve un periodo que su propio motor
 * vaya a rechazar. Un cálculo hecho aquí no tendría esa garantía.
 */
export async function obtenerPeriodoSugerido(
  clavePeriodicidad: string,
): Promise<PeriodoSugerido> {
  const res = await fetch(
    `${V1}/nomina/periodo-sugerido?clave_periodicidad=${encodeURIComponent(clavePeriodicidad)}`,
  );
  return leer<PeriodoSugerido>(res, 'No se pudo obtener el periodo sugerido');
}
