/**
 * Equipo del despacho (P5-01): usuarios, invitaciones, roles, asignaciones y plan.
 *
 * Contrato: `docs/api-contract.md`, sección "Equipo del despacho". Sólo el dueño gestiona;
 * el backend responde 403 a los demás y `puede_gestionar` le dice a la pantalla qué pintar.
 */

import { apiFetch } from './api';

export type Rol = 'dueno' | 'contador' | 'auxiliar';

export const NOMBRE_ROL: Record<Rol, string> = {
  dueno: 'Dueño', contador: 'Contador', auxiliar: 'Auxiliar',
};

export interface UsuarioEquipo {
  uid: string;
  nombre: string;
  email: string;
  rol: Rol;
  activo: boolean;
  /** Claves de los clientes asignados (lo único que ve un auxiliar). */
  clientes: string[];
}

export interface InvitacionPendiente {
  id: number;
  correo: string;
  rol: Rol;
  expira_en: string;
  creado_por: string;
}

export interface PlanDespacho {
  id: string;
  nombre: string;
  max_usuarios: number;
  max_clientes: number;
  usuarios_activos: number;
  invitaciones_pendientes: number;
  clientes: number;
}

export interface Equipo {
  yo: { uid: string; rol: Rol; despacho_id: string };
  puede_gestionar: boolean;
  plan: PlanDespacho;
  usuarios: UsuarioEquipo[];
  invitaciones: InvitacionPendiente[];
}

const enc = encodeURIComponent;

export function obtenerEquipo(): Promise<Equipo> {
  return apiFetch('/equipo');
}

export function invitar(correo: string, rol: Rol): Promise<{ invitacion: InvitacionPendiente }> {
  return apiFetch('/equipo/invitaciones', { method: 'POST', json: { correo, rol } });
}

export function revocarInvitacion(id: number): Promise<{ exito: boolean }> {
  return apiFetch(`/equipo/invitaciones/${id}`, { method: 'DELETE' });
}

export function aceptarInvitacion(token: string, nombre = ''):
  Promise<{ despacho_id: string; rol: Rol }> {
  return apiFetch('/equipo/invitaciones/aceptar', { method: 'POST', json: { token, nombre } });
}

export function cambiarRol(uid: string, rol: Rol): Promise<{ rol: Rol }> {
  return apiFetch(`/equipo/usuarios/${enc(uid)}/rol`, { method: 'PUT', json: { rol } });
}

export function cambiarActivo(uid: string, activo: boolean): Promise<{ activo: boolean }> {
  const accion = activo ? 'reactivar' : 'desactivar';
  return apiFetch(`/equipo/usuarios/${enc(uid)}/${accion}`, { method: 'POST' });
}

export function asignarCliente(uid: string, clave: string, asignar: boolean):
  Promise<{ exito: boolean }> {
  return apiFetch(`/equipo/usuarios/${enc(uid)}/clientes/${enc(clave)}`,
    { method: asignar ? 'POST' : 'DELETE' });
}

/** El plan del DESPACHO en el backend, que es quien hace cumplir los límites. */
export function cambiarPlanDespacho(plan: string): Promise<{ exito: boolean }> {
  return apiFetch('/equipo/plan', { method: 'PUT', json: { plan } });
}
