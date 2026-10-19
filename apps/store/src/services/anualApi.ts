/**
 * Personas morales y anual del cliente (P3-01, P3-06).
 *
 * Contrato: `docs/api-contract.md`, sección "Personas morales y anual". El front
 * no calcula: manda año/mes y los datos capturados, y pinta lo que devuelve el
 * motor. Los importes llegan como texto con dos decimales.
 */

import { apiArchivo, apiFetch } from './api';

/** Un renglón del cálculo (también es un renglón de la hoja "Cálculo ISR"). */
export interface RenglonAnual {
  clave: string;
  concepto: string;
  importe: string;
  fundamento: string;
}

export interface PagoProvisionalPM {
  mes: number;
  ingresos_mes: string;
  ingresos_acumulados: string;
  deducciones_acumuladas: string;
  coeficiente: string;
  utilidad_estimada: string;
  ptu_disminuida: string;
  estimulos: string;
  perdidas: string;
  base: string;
  isr_causado: string;
  pagos_anteriores: string;
  retenciones: string;
  pago_determinado: string;
  pago_efectuado: string;
  pago_capturado: boolean;
  a_pagar_pesos: string;
  /** O12: el pago usa un INPC de fuente secundaria (pérdidas actualizadas). */
  por_confirmar?: boolean;
}

export interface ResultadoPagosPM {
  exito: boolean;
  anio: number;
  mes: number;
  tipo: 'pm' | 'resico_pm';
  fuente: string;
  coeficiente: string;
  origen_coeficiente: string;
  tasa: string;
  fecha_limite: string;
  pagos: PagoProvisionalPM[];
  notas: string[];
  por_confirmar?: boolean;
  fuentes_por_confirmar?: string[];
}

export interface PerdidaPM {
  ejercicio: number;
  remanente: string;
  actualizada_a?: string | null;
}

/** Datos del ejercicio que no salen de la bóveda (subconjunto que edita la pantalla). */
export interface DatosAnualesPM {
  coeficiente_utilidad?: string | null;
  ptu_pagada?: string;
  mes_pago_ptu?: number;
  perdidas?: PerdidaPM[];
  retenciones_bancarias?: Record<string, string>;
  pagos_efectuados?: Record<string, string>;
  deduccion_inversiones?: string;
  fuente?: 'auto' | 'contabilidad' | 'boveda';
  /** Art. 28 fr. XXX para la renta gravable de PTU (Art. 9). Vacío = derivarlo. */
  no_deducibles_art28_xxx?: string | null;
  [otro: string]: unknown;
}

/** Fila mes a mes de la anual: los campos dependen del tipo (PF o PM). */
export type MesAnual = Record<string, string | number | boolean>;

export interface ResultadoAnual {
  exito: boolean;
  tipo: 'pf' | 'pm' | 'resico_pm';
  anio: number;
  regimen: string;
  fuente: string;
  renglones: RenglonAnual[];
  meses: MesAnual[];
  notas: string[];
  coeficiente?: Record<string, string>;
  ptu?: Record<string, string>;
  por_confirmar?: boolean;
  fuentes_por_confirmar?: string[];
}

const enc = encodeURIComponent;
const base = (clave: string) => `/impuestos/clientes/${enc(clave)}`;

export function obtenerDatosPM(clave: string, anio: number): Promise<{ datos: DatosAnualesPM }> {
  return apiFetch(`${base(clave)}/pm/datos/${anio}`);
}

export function guardarDatosPM(
  clave: string, anio: number, datos: DatosAnualesPM,
): Promise<{ datos: DatosAnualesPM }> {
  return apiFetch(`${base(clave)}/pm/datos/${anio}`, { method: 'PUT', json: datos });
}

/** Pagos provisionales de enero al mes (Art. 14 LISR / Art. 211 RESICO PM). */
export function pagosProvisionalesPM(
  clave: string, anio: number, mes: number,
): Promise<ResultadoPagosPM> {
  return apiFetch(`${base(clave)}/pm/pagos-provisionales`, { method: 'POST', json: { anio, mes } });
}

/** Cálculo anual del cliente según su régimen. */
export function calcularAnual(
  clave: string, anio: number, pagos: Record<string, string> = {},
): Promise<ResultadoAnual> {
  return apiFetch(`${base(clave)}/anual`, {
    method: 'POST', json: { anio, pagos_provisionales: pagos },
  });
}

/** El mismo cálculo como papeles de trabajo (Excel). */
export function papelesAnual(
  clave: string, anio: number, pagos: Record<string, string> = {},
): Promise<Blob> {
  return apiArchivo(`${base(clave)}/anual/papeles`, {
    method: 'POST', json: { anio, pagos_provisionales: pagos },
  });
}
