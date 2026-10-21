/**
 * Impuestos del cliente y calculadoras fiscales (P3-02, P3-03, P3-07, P3-08).
 *
 * Contrato: `docs/api-contract.md`, sección "Impuestos del cliente y calculadoras".
 * El front no calcula nada: manda los datos y pinta lo que devuelve el motor.
 */

import { apiArchivo, apiFetch } from './api';

/** Respuesta genérica de una calculadora: importes como texto. */
export type ResultadoCalculadora = Record<string, unknown> & { exito: boolean };

export interface CapturaRenglon {
  importe_a_pagar?: string | null;
  subsidio?: string;
  compensaciones?: string;
}

export interface RenglonResumen {
  clave: string;
  grupo: string;
  concepto: string;
  aplica: boolean;
  importe_sistema: string;
  importe_a_pagar: string;
  actualizacion: string;
  recargos: string;
  subsidio: string;
  compensaciones: string;
  total: string;
  capturado: boolean;
  nota: string;
  factor: string;
  meses_recargo: number;
  /** O12: la actualización o los recargos usan un INPC o una tasa de fuente secundaria. */
  por_confirmar?: boolean;
}

export interface ResumenImpuestos {
  exito: boolean;
  anio: number;
  mes: number;
  fecha_limite: string;
  fecha_pago: string;
  renglones: RenglonResumen[];
  totales: Record<string, string>;
  total_a_pagar_ajustado: string;
  notas: string[];
  por_confirmar?: boolean;
  fuentes_por_confirmar?: string[];
}

export interface PeticionResumen {
  anio: number;
  mes: number;
  fecha_pago: string;
  fecha_limite?: string | null;
  capturas: Record<string, CapturaRenglon>;
}

const enc = encodeURIComponent;

/** Tabla de impuestos del periodo del cliente con actualización y recargos. */
export function obtenerResumen(clave: string, p: PeticionResumen): Promise<ResumenImpuestos> {
  return apiFetch(`/impuestos/clientes/${enc(clave)}/resumen`, {
    method: 'POST', json: { ...p, formato: 'json' },
  });
}

/** El mismo resumen como archivo (Excel o CSV). */
export function exportarResumen(
  clave: string, p: PeticionResumen, formato: 'xlsx' | 'csv',
): Promise<Blob> {
  return apiArchivo(`/impuestos/clientes/${enc(clave)}/resumen`, {
    method: 'POST', json: { ...p, formato },
  });
}

/** IVA de varios meses desde la bóveda (saldo a favor arrastrado). */
export function obtenerIvaPeriodos(
  clave: string, anio: number, meses: number[],
): Promise<ResultadoCalculadora> {
  return apiFetch(`/impuestos/clientes/${enc(clave)}/iva`, {
    method: 'POST', json: { anio, meses },
  });
}

/** Criterio fiscal del cliente (DP-3). */
export function obtenerConfigImpuestos(clave: string): Promise<ResultadoCalculadora> {
  return apiFetch(`/impuestos/clientes/${enc(clave)}/config`);
}

export function guardarConfigImpuestos(
  clave: string, config: Record<string, unknown>,
): Promise<ResultadoCalculadora> {
  return apiFetch(`/impuestos/clientes/${enc(clave)}/config`, { method: 'PUT', json: config });
}

/** Ids de las calculadoras sueltas, que son también el último segmento de su ruta. */
export type Calculadora =
  | 'actualizacion-recargos' | 'isr-sueldos' | 'isr-resico' | 'aguinaldo' | 'ptu'
  | 'finiquito' | 'isn';

/** Corre una calculadora con el cuerpo dado. */
export function calcular(
  calculadora: Calculadora, cuerpo: Record<string, unknown>,
): Promise<ResultadoCalculadora> {
  return apiFetch(`/calculadoras/${calculadora}`, { method: 'POST', json: cuerpo });
}

/** Catálogo de tasas ISN vigentes por entidad. */
export function tasasIsn(fecha?: string): Promise<ResultadoCalculadora> {
  return apiFetch(`/calculadoras/isn/tasas${fecha ? `?fecha=${enc(fecha)}` : ''}`);
}

/** Fecha límite del pago mensual (día 17 corrido a hábil). */
export function fechaLimite(anio: number, mes: number): Promise<ResultadoCalculadora> {
  return apiFetch(`/calculadoras/fecha-limite?anio=${anio}&mes=${mes}`);
}
