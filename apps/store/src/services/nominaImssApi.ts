/**
 * IMSS y timbrado de nómina del cliente (P4-09, P4-10, P4-11). Siempre autenticado.
 *
 * Ningún importe se calcula aquí: los layouts, las cuotas, la conciliación y el CFDI los arma
 * el backend. El front pide, pinta y descarga.
 */

import { apiArchivo, apiFetch } from './api';

const base = (cliente: string) => `/nomina/clientes/${encodeURIComponent(cliente)}`;

export type TipoMovimiento = '08' | '07' | '02';
export type EstadoMovimiento = 'pendiente' | 'generado' | 'enviado' | 'acuse' | 'cancelado';
export type DestinoArchivo = 'idse_08' | 'idse_07' | 'idse_02' | 'sua_trabajadores' | 'sua_movimientos';

export interface MovimientoImss {
  id: number;
  empleado_no: string;
  nombre: string;
  tipo: TipoMovimiento;
  fecha: string;
  sbc: string | null;
  tipo_salario: string;
  causa_baja: string;
  estado: EstadoMovimiento;
  lote_id: number | null;
  acuse: string;
  origen: string;
}

export interface LoteImss {
  id: number;
  tipo: string;
  nombre_archivo: string;
  registros: number;
}

export interface ArchivoGenerado {
  lote: LoteImss;
  no_exportables: { empleado_no: string; motivo: string }[];
  transliterados: string[];
}

export function listarMovimientos(cliente: string): Promise<{ movimientos: MovimientoImss[]; pendientes: number }> {
  return apiFetch(`${base(cliente)}/movimientos-imss`);
}

export function generarArchivo(
  cliente: string,
  cuerpo: { destino: DestinoArchivo; ids?: number[]; al?: string; desde?: string; hasta?: string },
): Promise<ArchivoGenerado> {
  return apiFetch(`${base(cliente)}/movimientos-imss/archivo`, { method: 'POST', json: cuerpo });
}

export function descargarLote(cliente: string, loteId: number): Promise<Blob> {
  return apiArchivo(`${base(cliente)}/movimientos-imss/lotes/${loteId}/archivo`);
}

export function marcarMovimientos(
  cliente: string,
  ids: number[],
  estado: 'enviado' | 'acuse' | 'cancelado',
  acuse = '',
): Promise<{ movimientos: MovimientoImss[] }> {
  return apiFetch(`${base(cliente)}/movimientos-imss/marcar`, { method: 'POST', json: { ids, estado, acuse } });
}

// ── P4-10 ──

export interface CuotaTrabajador {
  empleado_no: string;
  nss: string;
  nombre: string;
  dias: number;
  dias_ausentismo: number;
  dias_incapacidad: number;
  sbc: string;
  total: string;
}

export interface CuotasPeriodo {
  tipo: 'EMA' | 'EBA';
  trabajadores: CuotaTrabajador[];
  por_ramo: Record<string, string>;
  total: string;
  advertencias: string[];
}

export function calcularCuotas(
  cliente: string,
  ejercicio: number,
  periodo: { mes: number } | { bimestre: number },
): Promise<CuotasPeriodo> {
  const q = 'mes' in periodo ? `mes=${periodo.mes}` : `bimestre=${periodo.bimestre}`;
  return apiFetch(`${base(cliente)}/cuotas-imss?ejercicio=${ejercicio}&${q}`);
}

export interface DiferenciaCedula {
  campo: string;
  calculado?: string;
  cedula?: string;
  diferencia?: string;
  nota?: string;
}

export interface Conciliacion {
  trabajadores: { nss: string; empleado_no: string; nombre: string; cuadra: boolean; diferencias: DiferenciaCedula[] }[];
  con_diferencia: number;
  total_calculo: string;
  total_cedula: string;
  diferencia_total: string;
}

export interface CedulaImportada {
  id: number;
  tipo: 'EMA' | 'EBA';
  diferencias: number;
  conciliacion: Conciliacion;
}

export function importarCedula(
  cliente: string,
  archivo: File,
  datos: { tipo: 'EMA' | 'EBA'; ejercicio: number; periodo: number; configuracion?: Record<string, unknown> },
): Promise<{ cedula: CedulaImportada }> {
  const forma = new FormData();
  forma.append('archivo', archivo);
  forma.append('tipo', datos.tipo);
  forma.append('ejercicio', String(datos.ejercicio));
  forma.append('periodo', String(datos.periodo));
  forma.append('configuracion', JSON.stringify(datos.configuracion ?? {}));
  return apiFetch(`${base(cliente)}/cedulas`, { method: 'POST', body: forma });
}

export function reporteCedula(cliente: string, id: number, formato: 'csv' | 'xlsx'): Promise<Blob> {
  return apiArchivo(`${base(cliente)}/cedulas/${id}/reporte?formato=${formato}`);
}

// ── P4-11 ──

export type EstadoCfdi = 'pendiente' | 'timbrado' | 'error' | 'reintento' | 'cancelado' | 'cancelacion_en_proceso';

export interface CfdiRecibo {
  id: number;
  recibo_id: number;
  empleado_no: string;
  nombre: string;
  estado: EstadoCfdi;
  uuid: string | null;
  error: string;
  es_prueba: boolean;
  total: string;
}

export interface EstadoTimbrado {
  estado_periodo: string;
  por_estado: Record<string, number>;
  trabajo: { id: number; estado: string; error: string | null } | null;
  recibos: CfdiRecibo[];
}

const periodo = (cliente: string, id: number) => `${base(cliente)}/periodos/${id}`;

export function timbrarPeriodo(cliente: string, id: number): Promise<EstadoTimbrado> {
  return apiFetch(`${periodo(cliente, id)}/timbrar`, { method: 'POST' });
}

export function estadoTimbrado(cliente: string, id: number): Promise<EstadoTimbrado> {
  return apiFetch(`${periodo(cliente, id)}/cfdi`);
}

export function descargarCfdi(cliente: string, id: number, cfdiId: number, tipo: 'xml' | 'pdf'): Promise<Blob> {
  return apiArchivo(`${periodo(cliente, id)}/cfdi/${cfdiId}/${tipo}`);
}

export function descargarZip(cliente: string, id: number): Promise<Blob> {
  return apiArchivo(`${periodo(cliente, id)}/cfdi.zip`);
}

export function cancelarCfdi(
  cliente: string,
  id: number,
  cfdiId: number,
  motivo: string,
  folioSustitucion?: string,
): Promise<{ cfdi: CfdiRecibo }> {
  return apiFetch(`${periodo(cliente, id)}/cfdi/${cfdiId}/cancelar`, {
    method: 'POST',
    json: { motivo, folio_sustitucion: folioSustitucion || null },
  });
}
