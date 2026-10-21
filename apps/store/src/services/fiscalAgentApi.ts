/** Servicio para comunicación con el Fiscal Agent API */

import type { ContributorType } from './contributorProfiles';

import { API_URL as BASE_URL, encabezadoAuth } from './api';

// ── Interfaces de request (coinciden con OpenAPI schemas) ──

export interface PerfilContribuyente {
  rfc: string;
  regimen: string;
  nombre?: string;
  tipo_persona?: string;
  actividad_economica?: string;
  periodicidad?: 'mensual' | 'bimestral' | 'anual';
  tiene_empleados?: boolean;
  retenedor_iva?: boolean;
  fecha_inicio_actividades?: string | null;
  contributor_type?: 'asalariado' | 'independiente' | 'arrendamiento' | 'plataformas' | 'pyme' | null;
}

// ── Frontera de tipos front → API ──────────────────────────────────────────
//
// `PerfilContribuyente.contributor_type` espeja a mano el enum de Python
// (`app/schemas/fiscal.py:49`). NO se ensancha: si se pusiera `string`, agregar
// un tipo nuevo en el front dejaria de romper el build y pasaria a romperse en
// vivo con un 422 de Pydantic. Estas dos funciones son el unico paso permitido
// de `ContributorType` (front) a lo que el backend acepta.

/** Los 5 tipos que el backend conoce. */
export type ApiContributorType = NonNullable<PerfilContribuyente['contributor_type']>;

/** Mapa exhaustivo a proposito: un tipo nuevo en `ContributorType` rompe el
 *  build aqui y obliga a decidir que se le manda al backend. */
const TIPO_API: Record<ContributorType, ApiContributorType | null> = {
  // Un despacho NO es el sujeto del calculo, sus clientes lo son: se omite.
  contador: null,
  asalariado: 'asalariado',
  independiente: 'independiente',
  arrendamiento: 'arrendamiento',
  plataformas: 'plataformas',
  pyme: 'pyme',
};

/** Tipo de contribuyente tal como viaja en los requests de calculo. */
export function tipoParaApi(tipo: ContributorType | null): ApiContributorType | null {
  return tipo ? TIPO_API[tipo] : null;
}

/** `/calendario` exige un tipo concreto (400 si no esta en su set), a diferencia
 *  de los calculos, donde el campo es opcional. El calendario que ve un despacho
 *  es el de SUS PROPIAS obligaciones como persona fisica con regimen 612 o 626,
 *  o sea las de un independiente.
 *
 *  DECISION PROVISIONAL (E-01, ver docs/decisiones-nomina.md D21): si lo que se
 *  quiere mostrar es el calendario PATRONAL de sus clientes (dia 17 IMSS,
 *  bimestral, avisos de variables), eso es F1-06 y todavia no existe. */
const TIPO_CALENDARIO: Record<ContributorType, ApiContributorType> = {
  contador: 'independiente',
  asalariado: 'asalariado',
  independiente: 'independiente',
  arrendamiento: 'arrendamiento',
  plataformas: 'plataformas',
  pyme: 'pyme',
};

export function tipoParaCalendario(tipo: ContributorType | null): ApiContributorType {
  return tipo ? TIPO_CALENDARIO[tipo] : 'independiente';
}

/**
 * El tipo que `/calendario` recibe para un CLIENTE del despacho (C-02).
 *
 * Desde T1 el calendario que ve un contador es el de su cliente activo, y
 * `tipoParaCalendario('contador')` le mandaba siempre `independiente`: a una
 * persona moral (601, alcanzable por `TABS_601`) le pintaba obligaciones de
 * persona física. El cliente no tiene "tipo de contribuyente" capturado —sólo
 * régimen—, así que se deduce de él, con la misma equivalencia que el
 * onboarding usa para ofrecer cada régimen (`contributorProfiles.ts`).
 *
 * DECISIÓN PROVISIONAL (nocturno): 601 → `pyme` (el tipo que ofrece el 601),
 * 605 → `asalariado`, 606 → `arrendamiento`, 625 → `plataformas`; 612, 626 y
 * cualquier otro → `independiente`, que es lo que ya se mandaba. Extiende a los
 * clientes del despacho lo que §D21 decidía para el calendario propio del
 * despacho; pendiente de confirmar con la contadora.
 */
export function tipoCalendarioDeRegimen(regimen: string): ApiContributorType {
  switch (regimen) {
    case '601': return 'pyme';
    case '605': return 'asalariado';
    case '606': return 'arrendamiento';
    case '625': return 'plataformas';
    default: return 'independiente';
  }
}

/**
 * Los cuatro tipos de comprobante que el MOTOR acepta. Espeja `TipoFactura` de
 * `app/schemas/fiscal.py`: mandarle cualquier otro es un 422 de Pydantic.
 */
export type TipoComprobanteFiscal = 'I' | 'E' | 'T' | 'P';

/**
 * `'NOMINA'` es un recibo de nómina (`TipoDeComprobante="N"`), y **no es una
 * letra del catálogo del SAT a propósito** (T4).
 *
 * Antes de T4 el parser hacía `['I','E','T','P'].includes(tipo) ? tipo : 'I'`:
 * un CFDI de nómina entraba como **ingreso**, y los sueldos que el patrón le
 * pagó a su gente se sumaban a sus ingresos gravables sin que nada avisara. Es
 * la peor forma de estar mal — un número creíble y equivocado hacia arriba.
 *
 * El centinela es una palabra y no `'N'` para que no pueda confundirse con una
 * clave del catálogo en ninguna comparación, y para que cualquier `switch` que
 * lo ignore salte a la vista.
 */
export type TipoComprobante = TipoComprobanteFiscal | 'NOMINA';

export interface CFDI {
  uuid: string;
  fecha: string;
  tipo: TipoComprobante;
  rfc_emisor: string;
  rfc_receptor: string;
  subtotal: number;
  total: number;
  iva_trasladado?: number;
  iva_retenido?: number;
  isr_retenido?: number;
  descuento?: number;
  uso_cfdi?: string;
  descripcion?: string;
  metodo_pago?: string;
  uuid_relacionado?: string;
  monto_pago?: number;
  clave_prod_serv?: string;
  /** Sólo en `tipo: 'NOMINA'`: `TotalPercepciones` del complemento nomina12. */
  total_percepciones?: number;
  /** Sólo en `tipo: 'NOMINA'`: `TotalDeducciones` del complemento nomina12. */
  total_deducciones?: number;
}

/**
 * Un CFDI que el motor fiscal puede recibir. **El tipo es la guarda**, no un
 * `filter` que alguien recuerde escribir (T4).
 *
 * Todos los requests que llevan `facturas` piden `CFDIFiscal[]`, así que pasar
 * una lista cruda del uploader **rompe el build** y obliga a decidir qué se
 * hace con los recibos de nómina. La alternativa —confiar en que las seis
 * pantallas que suben XMLs se acuerden de filtrar— es exactamente el modo de
 * falla que T4 vino a cerrar, sólo que movido de lugar.
 */
export interface CFDIFiscal extends CFDI {
  tipo: TipoComprobanteFiscal;
}

/** `true` si es un recibo de nómina y no una factura del contribuyente. */
export function esNomina(factura: CFDI): boolean {
  return factura.tipo === 'NOMINA';
}

/**
 * Las facturas que sí van al motor: todo menos los recibos de nómina.
 *
 * **Por qué se excluyen y no se convierten:** un CFDI de nómina es un
 * comprobante que el PATRÓN emite a su TRABAJADOR. En la declaración del
 * patrón no es un ingreso —es una deducción, ya contenida en su contabilidad—
 * y en la del trabajador asalariado su ISR ya viene retenido. Ninguno de los
 * dos casos lo suma como factura: el motor no tiene dónde ponerlo, y el
 * backend lo rechaza con 422 (`TipoFactura` no conoce `N`).
 */
export function facturasFiscales(facturas: CFDI[]): CFDIFiscal[] {
  return facturas.filter((f): f is CFDIFiscal => f.tipo !== 'NOMINA');
}

/** Cuántos recibos de nómina hay en la lista. Para el contador informativo. */
export function contarNomina(facturas: CFDI[]): number {
  return facturas.filter(esNomina).length;
}

// Tipos de request/response: `fiscalAgentTipos.ts` (P6-05, tope de 300 líneas).
export type {
  DeclaracionHistorialItem, AgentePreDeclaracionRequest, AgentePreDeclaracionResponse,
  PreDeclaracionRequest, DeduccionesPersonalesRequest, CalendarioRequest, CompararRegimenRequest,
  ResultadoRegimen, DesgloseFiscal, PreDeclaracionResponse, DeduccionDetalle,
  DeduccionesPersonalesResponse, ObligacionFiscal, CalendarioResponse, CompararRegimenResponse,
  DIOTRequest, DIOTProveedor, DIOTResponse, RetencionesRequest, RetencionTercero,
  RetencionesResponse, MultiPeriodoRequest, PeriodoResultado, AcumuladoMultiPeriodo,
  MultiPeriodoResponse, EstadoCuentaRequest, EstadoCuentaResponse,
} from './fiscalAgentTipos';
import type {
  AgentePreDeclaracionRequest, AgentePreDeclaracionResponse,
  PreDeclaracionRequest, DeduccionesPersonalesRequest, CalendarioRequest, CompararRegimenRequest,
  PreDeclaracionResponse, DeduccionesPersonalesResponse, CalendarioResponse,
  CompararRegimenResponse, DIOTRequest, DIOTResponse, RetencionesRequest, RetencionesResponse,
  MultiPeriodoRequest, MultiPeriodoResponse, EstadoCuentaRequest, EstadoCuentaResponse,
} from './fiscalAgentTipos';
// ── Funciones de API ──

async function fetchAPI<T>(endpoint: string, options?: RequestInit): Promise<T> {
  // P0-02: todo `/api/v1` exige la sesión. `/health` no, y no debe pedir login para
  // decir si el servidor está vivo.
  const sesion = endpoint.startsWith('/api/') ? await encabezadoAuth() : {};
  const res = await fetch(`${BASE_URL}${endpoint}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...sesion },
  });

  if (!res.ok) {
    const body = await res.text().catch(() => '');
    throw new Error(
      `Error del servidor (${res.status}): ${body || 'Sin respuesta del Fiscal Agent API'}`
    );
  }

  return res.json();
}

/** Wrapper generico para llamadas POST al API con manejo de errores uniforme */
async function apiCall<T>(path: string, data: unknown, errorMsg: string): Promise<T> {
  try {
    return await fetchAPI<T>(path, { method: 'POST', body: JSON.stringify(data) });
  } catch (e) {
    if (e instanceof Error && e.message.startsWith('Error del servidor')) throw e;
    throw new Error(errorMsg, { cause: e });
  }
}

export async function healthCheck(): Promise<{ status: string }> {
  try {
    return await fetchAPI('/health');
  } catch {
    throw new Error('No se pudo conectar con el Fiscal Agent API. Verifica que esté corriendo.');
  }
}

export async function calcularPreDeclaracion(
  data: PreDeclaracionRequest
): Promise<PreDeclaracionResponse> {
  return apiCall('/api/v1/pre-declaracion', data, 'Error al calcular la pre-declaración. Verifica tu conexión e intenta de nuevo.');
}

export async function calcularPreDeclaracionAnual(
  data: PreDeclaracionRequest
): Promise<PreDeclaracionResponse> {
  return apiCall('/api/v1/pre-declaracion-anual', data, 'Error al calcular la pre-declaración anual.');
}

export async function calcularDeduccionesPersonales(
  data: DeduccionesPersonalesRequest
): Promise<DeduccionesPersonalesResponse> {
  return apiCall('/api/v1/deducciones-personales', data, 'Error al calcular deducciones personales.');
}

export async function obtenerCalendario(
  data: CalendarioRequest
): Promise<CalendarioResponse> {
  return apiCall('/api/v1/calendario', data, 'Error al obtener el calendario fiscal.');
}

export async function compararRegimenes(
  data: CompararRegimenRequest
): Promise<CompararRegimenResponse> {
  return apiCall('/api/v1/comparar-regimenes', data, 'Error al comparar regímenes fiscales.');
}

export async function generarDIOT(
  data: DIOTRequest
): Promise<DIOTResponse> {
  return apiCall('/api/v1/diot', data, 'Error al generar la DIOT.');
}

export async function obtenerRetencionesTerceros(
  data: RetencionesRequest
): Promise<RetencionesResponse> {
  return apiCall('/api/v1/retenciones-terceros', data, 'Error al obtener retenciones a terceros.');
}

export async function calcularMultiPeriodo(
  data: MultiPeriodoRequest
): Promise<MultiPeriodoResponse> {
  return apiCall('/api/v1/multi-periodo', data, 'Error al calcular multi-periodo.');
}

export async function obtenerEstadoCuenta(
  data: EstadoCuentaRequest
): Promise<EstadoCuentaResponse> {
  return apiCall('/api/v1/estado-cuenta', data, 'Error al obtener el estado de cuenta.');
}

// ── Agente conversacional de pre-declaraciones (tipos en `fiscalAgentTipos.ts`) ──

export async function llamarAgentePreDeclaracion(
  data: AgentePreDeclaracionRequest
): Promise<AgentePreDeclaracionResponse> {
  return apiCall('/api/v1/agente/predeclaracion', data, 'Error al consultar al agente fiscal.');
}
