/**
 * Calendario de vencimientos de la cartera y agenda semanal del despacho (P3-10).
 *
 * Contrato: `docs/api-contract.md`, sección "Calendario de la cartera y agenda". Las fechas
 * (prórroga por sexto dígito, día 17 inhábil, reglas del IMSS) las calcula el backend.
 */

import { apiFetch } from './api';

export type TipoObligacion = 'fiscal' | 'patronal' | 'credencial';
export type EstadoObligacion = 'pendiente' | 'presentada' | 'vencida';
export type EstadoTarea = 'pendiente' | 'en_proceso' | 'hecha';

export interface ObligacionCartera {
  clave: string;
  cliente: string;
  cliente_nombre: string;
  tipo: TipoObligacion;
  nombre: string;
  periodo: string;
  fecha_limite: string;
  fundamento: string;
  condicional: boolean;
  nota: string;
  estado: EstadoObligacion;
  origen_estado: string;
  fecha_presentacion: string | null;
  responsable_uid: string;
}

export interface TareaAgenda {
  id: number;
  titulo: string;
  descripcion: string;
  cliente: string | null;
  cliente_nombre: string;
  responsable_uid: string;
  fecha: string;
  estado: EstadoTarea;
  origen: 'manual' | 'obligacion';
  obligacion_clave: string | null;
}

export interface UsuarioDespacho {
  uid: string;
  nombre: string;
  rol: string;
}

export interface FiltrosCalendario {
  desde: string;
  hasta: string;
  cliente?: string;
  tipo?: string;
  responsable?: string;
}

export interface CalendarioCartera {
  obligaciones: ObligacionCartera[];
  tareas: TareaAgenda[];
}

function consulta(f: FiltrosCalendario): string {
  const q = new URLSearchParams({ desde: f.desde, hasta: f.hasta });
  if (f.cliente) q.set('cliente', f.cliente);
  if (f.tipo) q.set('tipo', f.tipo);
  if (f.responsable) q.set('responsable', f.responsable);
  return q.toString();
}

export function obtenerCalendario(f: FiltrosCalendario): Promise<CalendarioCartera> {
  return apiFetch(`/calendario/cartera?${consulta(f)}`);
}

export function marcarObligacion(
  cliente: string, clave: string, estado: 'presentada' | 'pendiente',
): Promise<{ estado: string }> {
  return apiFetch(`/clientes/${encodeURIComponent(cliente)}/obligaciones/estado`, {
    method: 'PUT', json: { clave, estado },
  });
}

export function usuariosDespacho(): Promise<{ usuarios: UsuarioDespacho[] }> {
  return apiFetch('/agenda/usuarios');
}

export interface TareaNueva {
  titulo: string;
  fecha: string;
  cliente?: string | null;
  responsable_uid?: string;
  descripcion?: string;
}

export function crearTarea(t: TareaNueva): Promise<{ tarea: TareaAgenda }> {
  return apiFetch('/agenda/tareas', { method: 'POST', json: t });
}

export function actualizarTarea(
  id: number, cambios: Partial<Pick<TareaAgenda, 'titulo' | 'fecha' | 'estado' | 'responsable_uid'>>,
): Promise<{ tarea: TareaAgenda }> {
  return apiFetch(`/agenda/tareas/${id}`, { method: 'PUT', json: cambios });
}

export function borrarTarea(id: number): Promise<{ exito: boolean }> {
  return apiFetch(`/agenda/tareas/${id}`, { method: 'DELETE' });
}

export function generarTareas(
  f: { desde: string; hasta: string; cliente?: string; responsable_uid?: string },
): Promise<{ creadas: number }> {
  return apiFetch('/agenda/tareas/desde-obligaciones', { method: 'POST', json: f });
}

/** Lunes de la semana de `fecha` (ISO, sin zona: las fechas del calendario son días). */
export function lunesDe(fecha: Date): Date {
  const d = new Date(fecha.getFullYear(), fecha.getMonth(), fecha.getDate());
  const dia = (d.getDay() + 6) % 7;
  d.setDate(d.getDate() - dia);
  return d;
}

export function iso(d: Date): string {
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  return `${d.getFullYear()}-${m}-${dd}`;
}

export function sumarDias(d: Date, n: number): Date {
  const r = new Date(d);
  r.setDate(r.getDate() + n);
  return r;
}

export type Vista = 'semana' | 'mes' | 'agenda';

/** Rango de días que pinta cada vista alrededor de `ancla`. */
export function rangoDe(vista: Vista, ancla: Date): { desde: Date; hasta: Date } {
  if (vista === 'semana') {
    const l = lunesDe(ancla);
    return { desde: l, hasta: sumarDias(l, 6) };
  }
  const primero = new Date(ancla.getFullYear(), ancla.getMonth(), 1);
  const ultimo = new Date(ancla.getFullYear(), ancla.getMonth() + 1, 0);
  if (vista === 'agenda') return { desde: primero, hasta: ultimo };
  return { desde: lunesDe(primero), hasta: sumarDias(lunesDe(ultimo), 6) };
}
