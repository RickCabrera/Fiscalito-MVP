/** Servicio para comunicación con el Fiscal Agent API */

import type { ContributorType } from './contributorProfiles';

const BASE_URL = import.meta.env.VITE_FISCAL_AGENT_URL || 'http://localhost:8000';

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

export interface PreDeclaracionRequest {
  contribuyente: PerfilContribuyente;
  facturas: CFDIFiscal[];
  periodo_year: number;
  periodo_month?: number | null;
  periodo_bimestre?: number | null;
  incluir_explicacion?: boolean;
  pagos_provisionales_anteriores?: number;
  predial_pagado?: number;
  ingresos_acumulados_anteriores?: number;
  deducciones_acumuladas_anteriores?: number;
}

export interface DeduccionesPersonalesRequest {
  ingresos_anuales: number;
  gastos_medicos?: number;
  colegiaturas?: number;
  nivel_educativo?: string;
  intereses_hipotecarios?: number;
  donativos?: number;
  aportaciones_voluntarias_retiro?: number;
  seguros_gastos_medicos?: number;
  transporte_escolar?: number;
  funeral?: number;
  incluir_explicacion?: boolean;
}

export interface CalendarioRequest {
  contributor_type: string;
  regimen: string;
  rfc: string;
  year?: number;
}

export interface CompararRegimenRequest {
  ingresos_mensuales_estimados: number;
  gastos_mensuales_estimados: number;
  predial_mensual?: number;
  tipo_actividad?: string;
  incluir_explicacion?: boolean;
}

export interface ResultadoRegimen {
  regimen: string;
  nombre: string;
  isr_anual: number;
  isr_mensual: number;
  disponible: boolean;
  notas: string[];
}

// ── Interfaces de response (coinciden con OpenAPI schemas) ──

export interface DesgloseFiscal {
  total_ingresos_facturados: number;
  total_ingresos_gravados: number;
  cantidad_facturas_ingreso?: number;
  total_egresos?: number;
  total_deducciones_autorizadas?: number;
  cantidad_facturas_egreso?: number;
  base_isr: number;
  tasa_isr: number;
  isr_causado: number;
  isr_retenido?: number;
  isr_a_pagar: number;
  iva_trasladado_cobrado?: number;
  iva_trasladado_pagado?: number;
  iva_retenido?: number;
  iva_a_pagar: number;
  deduccion_ciega_aplicada?: boolean;
  comparacion_deduccion?: string | null;
  retenciones_definitivas?: boolean;
  ingreso_anualizado_estimado?: number;
  gastos_personales_excluidos?: number;
  cantidad_gastos_personales?: number;
  pagos_provisionales_anteriores?: number;
  total_a_pagar: number;
}

export interface PreDeclaracionResponse {
  exito?: boolean;
  tipo_declaracion: string;
  periodo: string;
  regimen: string;
  desglose: DesgloseFiscal;
  explicacion?: string | null;
  advertencias?: string[];
  recomendaciones?: string[];
}

export interface DeduccionDetalle {
  concepto: string;
  monto_solicitado: number;
  tope_aplicable: number | null;
  monto_aceptado: number;
}

export interface DeduccionesPersonalesResponse {
  exito?: boolean;
  desglose: DeduccionDetalle[];
  total_solicitado: number;
  total_antes_tope: number;
  tope_global: number;
  tope_tipo: string;
  total_deducible: number;
  excedente_no_aprovechado: number;
  saldo_a_favor_estimado: number;
  explicacion?: string | null;
}

export interface ObligacionFiscal {
  nombre: string;
  descripcion: string;
  fecha_limite: string;
  periodicidad: string;
  completada?: boolean;
}

export interface CalendarioResponse {
  exito?: boolean;
  contributor_type: string;
  total_obligaciones: number;
  obligaciones: ObligacionFiscal[];
}

export interface CompararRegimenResponse {
  exito?: boolean;
  resultados: ResultadoRegimen[];
  regimen_recomendado: string;
  nombre_recomendado: string;
  ahorro_maximo: number;
  recomendacion: string;
  explicacion?: string | null;
}

// ── DIOT ──

export interface DIOTRequest {
  contribuyente: PerfilContribuyente;
  facturas: CFDIFiscal[];
  periodo_year: number;
  periodo_month: number;
  incluir_explicacion?: boolean;
}

export interface DIOTProveedor {
  rfc: string;
  nombre: string;
  total_operaciones: number;
  iva_pagado: number;
  cantidad_facturas: number;
}

export interface DIOTResponse {
  exito?: boolean;
  periodo: string;
  proveedores: DIOTProveedor[];
  total_proveedores: number;
  total_operaciones: number;
  total_iva: number;
  explicacion?: string | null;
}

// ── Retenciones a terceros ──

export interface RetencionesRequest {
  contribuyente: PerfilContribuyente;
  facturas: CFDIFiscal[];
  periodo_year: number;
  periodo_month: number;
  incluir_explicacion?: boolean;
}

export interface RetencionTercero {
  rfc: string;
  nombre: string;
  total_pagado: number;
  isr_retenido: number;
  iva_retenido: number;
  cantidad_facturas: number;
}

export interface RetencionesResponse {
  exito?: boolean;
  periodo: string;
  terceros: RetencionTercero[];
  total_isr_retenido: number;
  total_iva_retenido: number;
  explicacion?: string | null;
}

// ── Multi-periodo ──

export interface MultiPeriodoRequest {
  contribuyente: PerfilContribuyente;
  facturas: CFDIFiscal[];
  periodo_year: number;
  periodos: number[];
  incluir_explicacion?: boolean;
}

export interface PeriodoResultado {
  periodo: string;
  desglose: DesgloseFiscal;
}

export interface AcumuladoMultiPeriodo {
  total_isr_pagado: number;
  total_iva_pagado: number;
  total_general_pagado: number;
  promedio_mensual: number;
  tendencia: string;
}

export interface MultiPeriodoResponse {
  exito?: boolean;
  year: number;
  resultados: PeriodoResultado[];
  acumulado: AcumuladoMultiPeriodo;
  explicacion?: string | null;
}

// ── Estado de cuenta ──

export interface EstadoCuentaRequest {
  contribuyente: PerfilContribuyente;
  facturas: CFDIFiscal[];
  periodo_year: number;
  incluir_explicacion?: boolean;
}

export interface EstadoCuentaResponse {
  exito?: boolean;
  year: number;
  ingresos_acumulados: number;
  egresos_acumulados: number;
  isr_retenido_acumulado: number;
  isr_anual_estimado: number;
  isr_faltante: number;
  iva_cobrado_acumulado: number;
  iva_pagado_acumulado: number;
  iva_retenido_acumulado: number;
  proyeccion_ingresos_anuales: number;
  proporcion_gastos_ingresos: number;
  mes_mayor_ingreso: string;
  mes_mayor_gasto: string;
  advertencias: string[];
  explicacion?: string | null;
}

// ── Funciones de API ──

async function fetchAPI<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${endpoint}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
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
    throw new Error(errorMsg);
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

// ── Agente conversacional de pre-declaraciones ──

export interface DeclaracionHistorialItem {
  periodo: string;
  tipo: string;
  fecha_calculo: string;
  total_a_pagar: number;
  isr_a_pagar: number;
  iva_a_pagar: number;
  regimen: string;
}

export interface AgentePreDeclaracionRequest {
  mensaje: string;
  contribuyente: PerfilContribuyente;
  facturas: CFDIFiscal[];
  historial: DeclaracionHistorialItem[];
  periodo_year: number;
  periodo_month?: number | null;
}

export interface AgentePreDeclaracionResponse {
  respuesta: string;
  predeclaracion?: PreDeclaracionResponse | null;
  herramientas_usadas: string[];
}

export async function llamarAgentePreDeclaracion(
  data: AgentePreDeclaracionRequest
): Promise<AgentePreDeclaracionResponse> {
  return apiCall('/api/v1/agente/predeclaracion', data, 'Error al consultar al agente fiscal.');
}
