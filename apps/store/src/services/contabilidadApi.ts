/**
 * Contabilidad del cliente (plan P, P2-01 a P2-04): catálogo, configuración de
 * pólizas automáticas, pólizas y balanza. El backend es el dueño del dato y de
 * cada importe; esta capa sólo arma URLs. Contrato: `docs/api-contract.md`,
 * sección "Contabilidad".
 */

import { apiFetch } from './api';
import type {
  Auxiliar, Balanza, CodigoAgrupador, ConfigContable, Cuenta, FiltroBalanza, FiltrosPolizas,
  NuevaCuenta, NuevaPoliza, Poliza, Regla, RespuestaGenerar,
} from './contabilidadTipos';

export type * from './contabilidadTipos';

function base(clave: string): string {
  return `/contabilidad/clientes/${encodeURIComponent(clave)}`;
}

function consulta(params: Record<string, string | number | undefined | null>): string {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== '') q.set(k, String(v));
  }
  const s = q.toString();
  return s ? `?${s}` : '';
}

// ── P2-01: catálogo ──

export function listarCuentas(clave: string): Promise<{ cuentas: Cuenta[] }> {
  return apiFetch(`${base(clave)}/cuentas`);
}

export function sembrarCatalogo(clave: string): Promise<{ creadas: number }> {
  return apiFetch(`${base(clave)}/cuentas/sembrar`, { method: 'POST' });
}

export function crearCuenta(clave: string, cuenta: NuevaCuenta): Promise<{ cuenta: Cuenta }> {
  return apiFetch(`${base(clave)}/cuentas`, { method: 'POST', json: cuenta });
}

export function editarCuenta(
  clave: string, id: number, cambio: Partial<Pick<Cuenta, 'numero' | 'nombre' | 'codigo_agrupador'>>,
): Promise<{ cuenta: Cuenta }> {
  return apiFetch(`${base(clave)}/cuentas/${id}`, { method: 'PATCH', json: cambio });
}

export function borrarCuenta(clave: string, id: number): Promise<{ exito: boolean }> {
  return apiFetch(`${base(clave)}/cuentas/${id}`, { method: 'DELETE' });
}

export function obtenerAgrupador(): Promise<{ fuente: string; codigos: CodigoAgrupador[] }> {
  return apiFetch('/contabilidad/codigo-agrupador');
}

// ── P2-02: configuración ──

export function obtenerConfigContable(clave: string): Promise<{ config: ConfigContable }> {
  return apiFetch(`${base(clave)}/config`);
}

export function guardarConfigContable(
  clave: string, cambio: Partial<Omit<ConfigContable, 'roles' | 'reglas' | 'cuentas_personalizadas'>>,
): Promise<{ config: ConfigContable }> {
  return apiFetch(`${base(clave)}/config`, { method: 'PUT', json: cambio });
}

export function crearRegla(clave: string, regla: Omit<Regla, 'id'>): Promise<{ regla: Regla }> {
  return apiFetch(`${base(clave)}/reglas`, { method: 'POST', json: regla });
}

export function editarRegla(clave: string, id: number, cambio: Partial<Omit<Regla, 'id'>>): Promise<{ regla: Regla }> {
  return apiFetch(`${base(clave)}/reglas/${id}`, { method: 'PATCH', json: cambio });
}

export function borrarRegla(clave: string, id: number): Promise<{ exito: boolean }> {
  return apiFetch(`${base(clave)}/reglas/${id}`, { method: 'DELETE' });
}

// ── P2-03: pólizas ──

export function generarPolizas(
  clave: string, desde: string, hasta: string, segundoPlano?: boolean,
): Promise<RespuestaGenerar> {
  return apiFetch(`${base(clave)}/polizas/generar`, {
    method: 'POST', json: { desde, hasta, segundo_plano: segundoPlano ?? null }, timeoutMs: 120000,
  });
}

export function listarPolizas(
  clave: string, f: FiltrosPolizas = {},
): Promise<{ total: number; pagina: number; por_pagina: number; polizas: Poliza[] }> {
  return apiFetch(`${base(clave)}/polizas${consulta({ ...f })}`);
}

export function obtenerPoliza(clave: string, id: number): Promise<{ poliza: Poliza }> {
  return apiFetch(`${base(clave)}/polizas/${id}`);
}

export function crearPoliza(clave: string, poliza: NuevaPoliza): Promise<{ poliza: Poliza }> {
  return apiFetch(`${base(clave)}/polizas`, { method: 'POST', json: poliza });
}

export function editarPoliza(
  clave: string, id: number, cambio: Partial<NuevaPoliza>,
): Promise<{ poliza: Poliza }> {
  return apiFetch(`${base(clave)}/polizas/${id}`, { method: 'PATCH', json: cambio });
}

export function cancelarPoliza(clave: string, id: number, motivo: string): Promise<{ poliza: Poliza }> {
  return apiFetch(`${base(clave)}/polizas/${id}/cancelar`, { method: 'POST', json: { motivo } });
}

export function listarPeriodosCerrados(
  clave: string,
): Promise<{ periodos: { anio: number; mes: number; cerrado_en: string }[] }> {
  return apiFetch(`${base(clave)}/periodos-cerrados`);
}

export function cerrarPeriodo(clave: string, anio: number, mes: number): Promise<{ exito: boolean }> {
  return apiFetch(`${base(clave)}/periodos-cerrados`, { method: 'POST', json: { anio, mes } });
}

export function abrirPeriodo(clave: string, anio: number, mes: number): Promise<{ exito: boolean }> {
  return apiFetch(`${base(clave)}/periodos-cerrados/${anio}/${mes}`, { method: 'DELETE' });
}

// ── P2-04: balanza y auxiliar ──

export function obtenerBalanza(
  clave: string, desde: string, hasta: string, nivel?: number | null, solo?: FiltroBalanza,
): Promise<Balanza> {
  return apiFetch(`${base(clave)}/balanza${consulta({ desde, hasta, nivel, solo })}`);
}

export function obtenerAuxiliar(
  clave: string, cuentaId: number, desde: string, hasta: string,
): Promise<Auxiliar> {
  return apiFetch(`${base(clave)}/cuentas/${cuentaId}/auxiliar${consulta({ desde, hasta })}`);
}

export function listarSaldosIniciales(
  clave: string,
): Promise<{ saldos: { cuenta_id: number; numero: string; nombre: string; deudor: string; acreedor: string }[] }> {
  return apiFetch(`${base(clave)}/saldos-iniciales`);
}

export function guardarSaldosIniciales(
  clave: string, saldos: { cuenta_id: number; deudor: string; acreedor: string }[],
): Promise<{ totales: { deudor: string; acreedor: string; cuadra: boolean } }> {
  return apiFetch(`${base(clave)}/saldos-iniciales`, { method: 'PUT', json: { saldos } });
}
