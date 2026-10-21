/**
 * Cuentas por cobrar del despacho (P5-03). Contrato: `docs/api-contract.md`, "Cobranza".
 * Los importes viajan como texto decimal ("5000.00"): nunca se suman como `number` aquí.
 */

import { apiArchivo, apiFetch } from './api';

export type Tramo = '0_30' | '31_60' | '61_90' | 'mas_90';

export const NOMBRE_TRAMO: Record<Tramo, string> = {
  '0_30': '0-30 días', '31_60': '31-60', '61_90': '61-90', mas_90: '+90',
};

export interface SaldoCliente {
  total_cargos: string;
  total_pagos: string;
  saldo: string;
  vencido: string;
  antiguedad: Record<Tramo, string>;
  /** Fecha del cargo más viejo con saldo: "desde cuándo debe". */
  desde: string | null;
  vencido_desde: string | null;
}

export interface FilaResumen extends SaldoCliente {
  cliente: string;
  cliente_nombre: string;
  iguala_mensual: string | null;
}

export interface ResumenCobranza {
  hoy: string;
  clientes: FilaResumen[];
  totales: SaldoCliente;
}

export interface Honorarios {
  iguala_mensual: string;
  concepto: string;
  dia_cargo: number;
  dias_credito: number;
  activo: boolean;
  facturar: boolean;
  correo: string;
  telefono: string;
  recordatorio_automatico: boolean;
  canal_recordatorio: 'correo' | 'whatsapp';
  dias_entre_recordatorios: number;
}

/** Defaults del backend (`app/routes/cobranza.Honorarios`) para un cliente sin iguala. */
export const HONORARIOS_VACIOS: Honorarios = {
  iguala_mensual: '0', concepto: 'Honorarios contables', dia_cargo: 1, dias_credito: 10,
  activo: true, facturar: false, correo: '', telefono: '', recordatorio_automatico: false,
  canal_recordatorio: 'correo', dias_entre_recordatorios: 7,
};

export interface Movimiento {
  fecha: string;
  tipo: 'cargo' | 'pago';
  id: number;
  concepto: string;
  cargo: string;
  abono: string;
  saldo: string;
  vencimiento: string | null;
  uuid: string | null;
}

export interface Recordatorio {
  id: number;
  canal: 'correo' | 'whatsapp';
  destino: string;
  estado: string;
  origen: string;
  programado_para: string;
  enviado_en: string | null;
  saldo: string;
  error: string;
}

export interface DetalleCobranza extends SaldoCliente {
  hoy: string;
  cliente: string;
  cliente_nombre: string;
  movimientos: Movimiento[];
  honorarios: Honorarios | null;
  recordatorios: Recordatorio[];
}

const enc = encodeURIComponent;
const base = (clave: string) => `/cobranza/clientes/${enc(clave)}`;

export function resumenCobranza(): Promise<ResumenCobranza> {
  return apiFetch('/cobranza/resumen');
}

export function detalleCobranza(clave: string): Promise<DetalleCobranza> {
  return apiFetch(base(clave));
}

export function guardarHonorarios(clave: string, h: Honorarios): Promise<{ honorarios: Honorarios }> {
  return apiFetch(`${base(clave)}/honorarios`, { method: 'PUT', json: h });
}

export function nuevoCargo(clave: string, c: { concepto: string; importe: string; fecha: string;
  facturar: boolean }): Promise<{ exito: boolean }> {
  return apiFetch(`${base(clave)}/cargos`, { method: 'POST', json: c });
}

export function cancelarCargo(clave: string, id: number): Promise<{ exito: boolean }> {
  return apiFetch(`${base(clave)}/cargos/${id}`, { method: 'DELETE' });
}

export function nuevoPago(clave: string, p: { fecha: string; importe: string; forma_pago: string;
  referencia: string; cfdi_uuid: string | null }): Promise<{ exito: boolean }> {
  return apiFetch(`${base(clave)}/pagos`, { method: 'POST', json: p });
}

export function borrarPago(clave: string, id: number): Promise<{ exito: boolean }> {
  return apiFetch(`${base(clave)}/pagos/${id}`, { method: 'DELETE' });
}

export function generarIgualas(periodo?: string): Promise<{ periodo: string; cargos: number }> {
  return apiFetch('/cobranza/cargos/generar', { method: 'POST', json: periodo ? { periodo } : {} });
}

export function enviarRecordatorio(clave: string, canal: 'correo' | 'whatsapp',
  programadoPara?: string): Promise<{ recordatorio: Recordatorio }> {
  return apiFetch(`${base(clave)}/recordatorios`, {
    method: 'POST', json: { canal, programado_para: programadoPara ?? null },
  });
}

export function estadoDeCuenta(clave: string, formato: 'pdf' | 'xlsx'): Promise<Blob> {
  return apiArchivo(`${base(clave)}/estado-cuenta?formato=${formato}`);
}

/** "$5,000.00" a partir del texto decimal del backend. Sólo para pintar. */
export function pesos(valor: string | null | undefined): string {
  const n = Number(valor ?? 0);
  return n.toLocaleString('es-MX', { style: 'currency', currency: 'MXN' });
}
