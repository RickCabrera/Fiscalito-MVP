/**
 * Cliente de los endpoints de la cartera del despacho (E-02).
 *
 * DEMO — se borra en F2 junto con el resto de la épica.
 *
 * NINGUNA CONSTANTE FISCAL VIVE AQUÍ, igual que en `nominaDemoApi.ts`: ni los
 * empleados, ni la prima de riesgo, ni el periodo. Todo sale del backend, que
 * es quien tiene el fundamento legal y los tests que lo verifican.
 */

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
 */
async function leer<T>(res: Response, queFallo: string): Promise<T> {
  if (!res.ok) {
    let detalle = `HTTP ${res.status}`;
    try {
      const cuerpo = await res.json();
      if (typeof cuerpo?.error === 'string') detalle = cuerpo.error;
      else if (typeof cuerpo?.detail === 'string') detalle = cuerpo.detail;
    } catch {
      // Cuerpo no-JSON: nos quedamos con el código.
    }
    throw new Error(`${queFallo}: ${detalle}`);
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
