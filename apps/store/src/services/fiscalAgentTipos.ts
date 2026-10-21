/**
 * Tipos de request y response del Fiscal Agent API (coinciden con los schemas del OpenAPI).
 *
 * Salieron de `fiscalAgentApi.ts` en P6-05 (tope de 300 líneas) sin cambiar nada;
 * `fiscalAgentApi.ts` los reexporta.
 */
import type { CFDIFiscal, PerfilContribuyente } from './fiscalAgentApi';

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
