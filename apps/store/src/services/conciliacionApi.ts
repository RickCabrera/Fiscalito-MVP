/**
 * Conciliación bancaria (P2-06). El backend lee el estado de cuenta, empareja y
 * arma el reporte; esta capa sólo arma URLs. Contrato: `docs/api-contract.md`,
 * sección "Conciliación bancaria". Importes como texto con dos decimales.
 */

import { apiArchivo, apiFetch } from './api';

export interface CuentaBancaria {
  id: number; banco: string; nombre: string; numero: string; clabe: string; moneda: string;
  cuenta_contable_id: number; cuenta_contable: string; ventana_dias: number; umbral: number;
  activa: boolean;
}

export type NuevaCuentaBancaria = Omit<CuentaBancaria, 'id' | 'cuenta_contable' | 'moneda' | 'activa'>;

export interface Plantilla {
  id: number; nombre: string; banco: string; formato: 'csv' | 'xlsx'; mapeo: Record<string, unknown>;
}

export interface EstadoImportado {
  id: number; archivo: string; formato: string; desde: string | null; hasta: string | null;
  saldo_inicial: string | null; saldo_final: string | null; nuevos: number; duplicados: number;
  advertencias: string[];
}

export interface MovBanco {
  clave: string; id: number; fecha: string; concepto: string; referencia: string;
  cargo: string; abono: string; saldo: string | null; conciliacion_id: number | null;
}

export interface MovLibros {
  clave: string; id: number; origen: 'poliza' | 'cfdi'; poliza_id: number | null; folio: string;
  fecha: string; concepto: string; cargo: string; abono: string; uuid: string; rfc: string;
  conciliacion_id: number | null;
}

export interface VistaConciliacion {
  cuenta: CuentaBancaria; banco: MovBanco[]; libros: MovLibros[];
  pendientes_banco: number; pendientes_libros: number;
}

export interface ResultadoConciliar {
  conciliados: number; uno_a_varios: number; ambiguos: string[];
  pendientes_banco: number; pendientes_libros: number;
}

export interface PartidaReporte { fecha: string; folio: string; concepto: string; importe: string }

export interface ReporteConciliacion {
  corte: string; saldo_banco: string; saldo_libros: string;
  depositos_en_transito: PartidaReporte[]; retiros_en_transito: PartidaReporte[];
  abonos_banco_no_registrados: PartidaReporte[]; cargos_banco_no_registrados: PartidaReporte[];
  totales: Record<string, string>; saldo_banco_conciliado: string; saldo_libros_conciliado: string;
  diferencia: string; cuadra: boolean; advertencias: string[];
}

function base(clave: string): string {
  return `/conciliacion/clientes/${encodeURIComponent(clave)}`;
}

function rango(desde?: string, hasta?: string): string {
  const q = new URLSearchParams();
  if (desde) q.set('desde', desde);
  if (hasta) q.set('hasta', hasta);
  const s = q.toString();
  return s ? `?${s}` : '';
}

export function listarBancos(): Promise<{ bancos: { clave: string; nombre: string }[] }> {
  return apiFetch('/conciliacion/bancos');
}

export function listarCuentasBancarias(clave: string): Promise<{ cuentas: CuentaBancaria[] }> {
  return apiFetch(`${base(clave)}/cuentas`);
}

export function crearCuentaBancaria(clave: string, c: NuevaCuentaBancaria): Promise<{ cuenta: CuentaBancaria }> {
  return apiFetch(`${base(clave)}/cuentas`, { method: 'POST', json: c });
}

export function editarCuentaBancaria(
  clave: string, id: number, cambio: Partial<NuevaCuentaBancaria & { activa: boolean }>,
): Promise<{ cuenta: CuentaBancaria }> {
  return apiFetch(`${base(clave)}/cuentas/${id}`, { method: 'PATCH', json: cambio });
}

export function borrarCuentaBancaria(clave: string, id: number): Promise<{ exito: boolean }> {
  return apiFetch(`${base(clave)}/cuentas/${id}`, { method: 'DELETE' });
}

export function listarPlantillas(clave: string): Promise<{ plantillas: Plantilla[] }> {
  return apiFetch(`${base(clave)}/plantillas`);
}

export function guardarPlantilla(clave: string, p: Omit<Plantilla, 'id'>): Promise<{ plantilla: Plantilla }> {
  return apiFetch(`${base(clave)}/plantillas`, { method: 'PUT', json: p });
}

export function borrarPlantilla(clave: string, id: number): Promise<{ exito: boolean }> {
  return apiFetch(`${base(clave)}/plantillas/${id}`, { method: 'DELETE' });
}

export function importarEstado(
  clave: string, cuentaId: number, archivo: File,
  opciones: { plantillaId?: number | null; mapeo?: Record<string, unknown> | null } = {},
): Promise<{ estado: EstadoImportado; banco_pdf: string | null }> {
  const form = new FormData();
  form.append('archivo', archivo);
  if (opciones.plantillaId) form.append('plantilla_id', String(opciones.plantillaId));
  if (opciones.mapeo) form.append('mapeo', JSON.stringify(opciones.mapeo));
  return apiFetch(`${base(clave)}/cuentas/${cuentaId}/estados`, { method: 'POST', body: form, timeoutMs: 120000 });
}

export function listarEstados(clave: string, cuentaId: number): Promise<{ estados: EstadoImportado[] }> {
  return apiFetch(`${base(clave)}/cuentas/${cuentaId}/estados`);
}

export function obtenerVista(
  clave: string, cuentaId: number, desde?: string, hasta?: string,
): Promise<VistaConciliacion> {
  return apiFetch(`${base(clave)}/cuentas/${cuentaId}/movimientos${rango(desde, hasta)}`);
}

export function conciliarAutomatico(
  clave: string, cuentaId: number, desde?: string, hasta?: string,
): Promise<{ resultado: ResultadoConciliar }> {
  return apiFetch(`${base(clave)}/cuentas/${cuentaId}/conciliar`, {
    method: 'POST', json: { desde: desde || null, hasta: hasta || null },
  });
}

export function conciliarManual(
  clave: string, cuentaId: number, banco: string[], libros: string[], motivo = '',
): Promise<{ conciliacion_id: number }> {
  return apiFetch(`${base(clave)}/cuentas/${cuentaId}/conciliaciones`, {
    method: 'POST', json: { banco, libros, motivo },
  });
}

export function deshacerConciliacion(clave: string, cuentaId: number, id: number): Promise<{ exito: boolean }> {
  return apiFetch(`${base(clave)}/cuentas/${cuentaId}/conciliaciones/${id}`, { method: 'DELETE' });
}

export function sugerirCuenta(
  clave: string, cuentaId: number, movId: number,
): Promise<{ sugerida: { cuenta_id: number; numero: string; nombre: string } | null }> {
  return apiFetch(`${base(clave)}/cuentas/${cuentaId}/movimientos/${movId}/sugerencia`);
}

export function polizaDesdeBanco(
  clave: string, cuentaId: number, movId: number,
  contrapartidas: { cuenta_id: number; importe: string }[], concepto: string,
): Promise<{ conciliacion_id: number }> {
  return apiFetch(`${base(clave)}/cuentas/${cuentaId}/movimientos/${movId}/poliza`, {
    method: 'POST', json: { contrapartidas, concepto },
  });
}

export function obtenerReporte(clave: string, cuentaId: number, corte: string): Promise<{ reporte: ReporteConciliacion }> {
  return apiFetch(`${base(clave)}/cuentas/${cuentaId}/reporte?corte=${corte}`);
}

export function descargarReporte(clave: string, cuentaId: number, corte: string): Promise<Blob> {
  return apiArchivo(`${base(clave)}/cuentas/${cuentaId}/reporte?corte=${corte}&formato=xlsx`);
}
