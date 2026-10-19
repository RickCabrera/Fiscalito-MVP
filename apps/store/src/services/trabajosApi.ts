/**
 * Trabajos en segundo plano (P0-04) y bitácora de auditoría (P0-07).
 *
 * Contrato: `docs/api-contract.md` §Trabajos y §Auditoría.
 */

import { apiFetch } from './api';

export type EstadoTrabajo = 'pendiente' | 'corriendo' | 'hecho' | 'fallido' | 'cancelado';

export interface Trabajo {
  id: number;
  tipo: string;
  estado: EstadoTrabajo;
  cliente: string | null;
  intentos: number;
  max_intentos: number;
  ejecutar_en: string;
  iniciado_en: string | null;
  terminado_en: string | null;
  creado_en: string;
  error: string | null;
  resultado: Record<string, unknown> | null;
  carga: Record<string, unknown>;
}

export interface FiltrosTrabajos {
  cliente?: string;
  estado?: EstadoTrabajo;
  tipo?: string;
  limite?: number;
}

function consulta(params: Record<string, string | number | undefined>): string {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== '') q.set(k, String(v));
  }
  const texto = q.toString();
  return texto ? `?${texto}` : '';
}

export async function listarTrabajos(filtros: FiltrosTrabajos = {}): Promise<Trabajo[]> {
  const r = await apiFetch<{ trabajos: Trabajo[] }>(`/trabajos${consulta({ ...filtros })}`);
  return r.trabajos;
}

export async function obtenerTrabajo(id: number): Promise<Trabajo> {
  return (await apiFetch<{ trabajo: Trabajo }>(`/trabajos/${id}`)).trabajo;
}

export async function reintentarTrabajo(id: number): Promise<Trabajo> {
  return (await apiFetch<{ trabajo: Trabajo }>(`/trabajos/${id}/reintentar`, { method: 'POST' }))
    .trabajo;
}

export async function cancelarTrabajo(id: number): Promise<Trabajo> {
  return (await apiFetch<{ trabajo: Trabajo }>(`/trabajos/${id}/cancelar`, { method: 'POST' }))
    .trabajo;
}

/** Encola el trabajo de prueba de la ficha (`diagnostico.cliente`). */
export async function encolarDiagnostico(cliente: string, fallarIntentos = 0): Promise<Trabajo> {
  const r = await apiFetch<{ trabajo: Trabajo }>(
    `/trabajos/clientes/${encodeURIComponent(cliente)}/diagnostico`,
    { method: 'POST', json: { fallar_intentos: fallarIntentos } },
  );
  return r.trabajo;
}

// ── Auditoría ──

export interface EventoAuditoria {
  id: number;
  fecha: string;
  uid: string;
  cliente: string | null;
  accion: string;
  entidad: string;
  entidad_id: string;
  detalle: Record<string, unknown>;
  ip: string;
}

export interface PaginaAuditoria {
  eventos: EventoAuditoria[];
  total: number;
  pagina: number;
  por_pagina: number;
}

export interface FiltrosAuditoria {
  usuario?: string;
  cliente?: string;
  accion?: string;
  /** AAAA-MM-DD, día en hora de Ciudad de México. */
  desde?: string;
  hasta?: string;
  pagina?: number;
  por_pagina?: number;
}

export async function listarAuditoria(filtros: FiltrosAuditoria = {}): Promise<PaginaAuditoria> {
  return apiFetch<PaginaAuditoria>(`/auditoria${consulta({ ...filtros })}`);
}

/** Etiqueta legible del estado de un trabajo. */
export function etiquetaEstado(estado: EstadoTrabajo): string {
  return {
    pendiente: 'En cola',
    corriendo: 'Corriendo',
    hecho: 'Listo',
    fallido: 'Falló',
    cancelado: 'Cancelado',
  }[estado];
}
