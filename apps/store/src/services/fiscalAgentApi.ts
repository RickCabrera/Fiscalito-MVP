/** Servicio para comunicación con el Fiscal Agent API */

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

export interface CFDI {
  uuid: string;
  fecha: string;
  tipo: 'I' | 'E' | 'T' | 'P';
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
}

export interface PreDeclaracionRequest {
  contribuyente: PerfilContribuyente;
  facturas: CFDI[];
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
  facturas: CFDI[];
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
  facturas: CFDI[];
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
  facturas: CFDI[];
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
  facturas: CFDI[];
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
  facturas: CFDI[];
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
