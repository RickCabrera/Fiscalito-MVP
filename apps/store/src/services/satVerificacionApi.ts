/**
 * Verificaciones contra el SAT (plan P, P1-03/04/05).
 *
 * Contrato: `docs/api-contract.md` §Verificación SAT. Estatus de CFDI (vigente/cancelado),
 * listas 69-B (EFOS) y opinión de cumplimiento / constancia de situación fiscal.
 */

import { apiArchivo, apiFetch } from './api';
import type { OrigenOpinion, ResultadoOpinion, Semaforo, SemaforoCliente } from './semaforoSat';

export type { OrigenOpinion, ResultadoOpinion, Semaforo, SemaforoCliente } from './semaforoSat';
export { COLOR_SEMAFORO, ETIQUETA_SEMAFORO } from './semaforoSat';
export type TipoDocumento = 'opinion' | 'constancia';

export interface TrabajoEncolado {
  id: number;
  tipo: string;
  estado: string;
}

export interface DocumentoCumplimiento {
  id: number;
  tipo: TipoDocumento;
  fecha: string;
  resultado: ResultadoOpinion;
  folio: string;
  origen: OrigenOpinion;
  lectura: string;
  tamano: number;
  creado_en: string | null;
  aviso: string | null;
}

export interface HistorialCumplimiento {
  exito: boolean;
  tipo: TipoDocumento;
  ultimo: DocumentoCumplimiento | null;
  semaforo: Semaforo;
  /** Origen de la última (`falso` = simulada) y su advertencia; null sin documento. */
  origen: OrigenOpinion | null;
  marca: string | null;
  historial: DocumentoCumplimiento[];
  via: string | null;
  dias_vigencia: number;
  config: { automatico: boolean; dia_del_mes: number; constancia: boolean };
}

export interface Riesgo69b {
  rfc: string;
  nombre: string;
  lista: string;
  situacion: string;
  situacion_texto: string;
  relacion: 'proveedor' | 'cliente' | 'propio';
  nivel: 'alto' | 'medio' | 'info';
  rojo: boolean;
  comprobantes: number;
  total: string;
  fecha_publicacion_sat: string | null;
  fecha_publicacion_dof: string | null;
}

export interface EstadoLista {
  lista: string;
  descripcion: string;
  registros: number;
  cargada_en: string | null;
  revisada_en: string | null;
  url: string;
  error: string | null;
}

export interface RiesgosCliente {
  exito: boolean;
  riesgos: Riesgo69b[];
  en_rojo: number;
  alertas: {
    id: number; tipo: string; rfc: string; nombre: string; lista: string; situacion: string;
    relacion: string; nivel: string; atendida: boolean; creada_en: string | null;
  }[];
  listas: EstadoLista[];
}

function base(clave: string): string {
  return `/sat/clientes/${encodeURIComponent(clave)}`;
}

/** Encola la verificación de estatus ante el SAT de los CFDI del rango. */
export function verificarEstatus(
  clave: string, desde: string, hasta: string,
): Promise<{ exito: boolean; trabajo: TrabajoEncolado; comprobantes: number }> {
  return apiFetch(`${base(clave)}/verificar-estatus`, { method: 'POST', json: { desde, hasta } });
}

export function riesgos69b(clave: string): Promise<RiesgosCliente> {
  return apiFetch(`${base(clave)}/riesgos-69b`);
}

export function atenderAlerta(clave: string, alertaId: number): Promise<{ exito: boolean }> {
  return apiFetch(`${base(clave)}/alertas/${alertaId}/atender`, { method: 'POST' });
}

export function estadoListas(): Promise<{ exito: boolean; listas: EstadoLista[] }> {
  return apiFetch('/sat/listas/estado');
}

export function historialCumplimiento(
  clave: string, tipo: TipoDocumento,
): Promise<HistorialCumplimiento> {
  return apiFetch(`${base(clave)}/${tipo === 'opinion' ? 'opinion' : 'constancia'}`);
}

/** "Obtener ahora": encola la consulta con la vía configurada en el servidor. */
export function obtenerAhora(
  clave: string, tipo: TipoDocumento,
): Promise<{ exito: boolean; trabajo: TrabajoEncolado }> {
  return apiFetch(`${base(clave)}/opinion/obtener?tipo=${tipo}`, { method: 'POST' });
}

export function subirPdfCumplimiento(
  clave: string, tipo: TipoDocumento, archivo: File, resultado?: ResultadoOpinion,
): Promise<{ exito: boolean; documento: DocumentoCumplimiento; semaforo: Semaforo | null; marca: string | null }> {
  const datos = new FormData();
  datos.append('archivo', archivo, archivo.name);
  datos.append('tipo', tipo);
  if (resultado) datos.append('resultado', resultado);
  return apiFetch(`${base(clave)}/opinion/pdf`, { method: 'POST', body: datos, timeoutMs: 120000 });
}

export function descargarPdfCumplimiento(clave: string, docId: number): Promise<Blob> {
  return apiArchivo(`${base(clave)}/opinion/${docId}/pdf`);
}

export function guardarConfigCumplimiento(
  clave: string, config: HistorialCumplimiento['config'],
): Promise<{ exito: boolean }> {
  return apiFetch(`${base(clave)}/opinion/config`, { method: 'PUT', json: config });
}

/** Semáforo de opinión y riesgos 69-B de toda la cartera visible. */
export async function semaforoCartera(): Promise<SemaforoCliente[]> {
  const r = await apiFetch<{ clientes: SemaforoCliente[] }>('/sat/cartera/semaforo');
  return r.clientes;
}
