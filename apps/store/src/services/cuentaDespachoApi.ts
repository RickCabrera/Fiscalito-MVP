/**
 * Cuenta del despacho (P6-01): exportar todos los datos (ZIP en segundo plano) y borrar la
 * cuenta. Sólo el rol dueño. Contrato: `docs/api-contract.md` §"Cuenta del despacho".
 */

import { apiFetch } from './api';

export const FRASE_BORRADO = 'BORRAR MI DESPACHO';

export interface Exportacion {
  id: number;
  estado: 'pendiente' | 'corriendo' | 'hecho' | 'fallido' | 'cancelado';
  error: string | null;
  creado_en: string | null;
  bytes: number | null;
  tablas: Record<string, number> | null;
  archivos: number | null;
  /** Enlace firmado de descarga (sólo con estado `hecho`). */
  url: string | null;
  vence_en: string | null;
}

export async function solicitarExportacion(): Promise<Exportacion> {
  return (await apiFetch<{ trabajo: Exportacion }>('/despacho/exportar', { method: 'POST' }))
    .trabajo;
}

export async function estadoExportacion(id: number): Promise<Exportacion> {
  return (await apiFetch<{ trabajo: Exportacion }>(`/despacho/exportar/${id}`)).trabajo;
}

export async function borrarDespacho(confirmacion: string): Promise<Record<string, number>> {
  const r = await apiFetch<{ borrado: Record<string, number> }>('/despacho/borrar', {
    method: 'POST',
    json: { confirmacion },
  });
  return r.borrado;
}
