/**
 * Alertas fiscales del despacho (P3-09).
 *
 * Contrato: `docs/api-contract.md`, sección "Alertas fiscales". Las genera un trabajo diario
 * del backend; el front lista, cuenta y marca resueltas.
 */

import { apiFetch } from './api';

export type Severidad = 'alta' | 'media' | 'baja';

export interface AlertaFiscal {
  id: number;
  cliente: string;
  cliente_nombre: string;
  tipo: string;
  severidad: Severidad;
  titulo: string;
  detalle: string;
  fecha: string;
  enlace: string;
  resuelta: boolean;
  resuelta_por: string;
  resuelta_en: string | null;
}

export interface ConteoAlertas {
  total: number;
  alta: number;
  por_cliente: Record<string, { total: number; alta: number; media: number; baja: number }>;
}

export interface FiltrosAlertas {
  cliente?: string;
  tipo?: string;
  severidad?: string;
  resuelta?: boolean;
}

export const NOMBRE_TIPO_ALERTA: Record<string, string> = {
  tope_resico: 'Tope RESICO', efos: 'Lista 69-B', cfdi_cancelado: 'CFDI cancelado',
  credencial: 'e.firma / CSD', opinion: 'Opinión de cumplimiento', descarga_sat: 'Descarga SAT',
  vencimiento: 'Vencimiento', diferencia_declarado: 'Declarado vs. bóveda',
  sin_polizas: 'Sin pólizas',
};

export function listarAlertas(f: FiltrosAlertas = {}): Promise<{ alertas: AlertaFiscal[] }> {
  const q = new URLSearchParams();
  if (f.cliente) q.set('cliente', f.cliente);
  if (f.tipo) q.set('tipo', f.tipo);
  if (f.severidad) q.set('severidad', f.severidad);
  if (f.resuelta) q.set('resuelta', 'true');
  const s = q.toString();
  return apiFetch(`/alertas${s ? `?${s}` : ''}`);
}

export function conteoAlertas(): Promise<ConteoAlertas> {
  return apiFetch('/alertas/conteo');
}

export function resolverAlerta(id: number): Promise<{ alerta: AlertaFiscal }> {
  return apiFetch(`/alertas/${id}/resolver`, { method: 'POST' });
}

export function evaluarAlertas(cliente?: string): Promise<{ exito: boolean }> {
  const q = cliente ? `?cliente=${encodeURIComponent(cliente)}` : '';
  return apiFetch(`/alertas/evaluar${q}`, { method: 'POST', timeoutMs: 90000 });
}
