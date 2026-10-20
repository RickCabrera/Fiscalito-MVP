/**
 * Suscripción y cobro del plan del despacho (P5-08).
 *
 * El DUEÑO del plan es el backend (`apps/api/app/planes.py` + tabla `suscripciones`): aquí
 * sólo se pide y se pinta. Los bloqueos (clientes, usuarios, módulos, solo lectura) los hace
 * cumplir el backend y llegan ya con su motivo escrito en `bloqueos`.
 * Contrato: `docs/api-contract.md`, sección "Suscripción y cobro de planes".
 */

import { apiFetch } from './api';

export type EstadoSuscripcion = 'prueba' | 'activa' | 'morosa' | 'vencida' | 'cancelada';

export interface Bloqueo {
  /** solo_lectura | clientes | usuarios | modulo:<id> */
  tipo: string;
  motivo: string;
}

export interface PlanCatalogo {
  id: string;
  nombre: string;
  max_usuarios: number;
  max_clientes: number;
  modulos: { id: string; nombre: string }[];
  /** Precio mensual configurado en el backend; `null` = aún no se publica. */
  precio_mensual: string | null;
  moneda: string;
  /** Lo que este plan bloquearía con el uso actual (no borra nada). */
  bloquearia: Bloqueo[];
}

export interface PagoSuscripcion {
  id: number;
  fecha: string;
  estado: 'pagado' | 'fallido';
  plan: string;
  monto: string | null;
  moneda: string;
  fin_periodo: string | null;
}

export interface ResumenSuscripcion {
  puede_gestionar: boolean;
  proveedor: string | null;
  suscripcion: {
    plan: string;
    plan_nombre: string;
    estado: EstadoSuscripcion;
    vigente: boolean;
    solo_lectura: boolean;
    aviso: string;
    inicio_periodo: string;
    fin_periodo: string;
    acceso_hasta: string;
    plan_pendiente: string | null;
    con_cobro: boolean;
  };
  uso: { clientes: number; usuarios: number; invitaciones_pendientes: number };
  bloqueos: Bloqueo[];
  planes: PlanCatalogo[];
  pagos: PagoSuscripcion[];
}

export interface ResultadoAlta {
  estado: EstadoSuscripcion;
  plan: string;
  plan_pendiente: string | null;
  url_pago: string | null;
}

export function obtenerSuscripcion(): Promise<ResumenSuscripcion> {
  return apiFetch('/suscripcion');
}

export function suscribirse(plan: string, correo = ''): Promise<ResultadoAlta> {
  return apiFetch('/suscripcion', { method: 'POST', json: { plan, correo } });
}

export function cambiarPlan(plan: string): Promise<{ plan: string }> {
  return apiFetch('/suscripcion/plan', { method: 'PUT', json: { plan } });
}

export function cancelarSuscripcion(): Promise<{ estado: 'cancelada'; acceso_hasta: string }> {
  return apiFetch('/suscripcion/cancelar', { method: 'POST' });
}

export const NOMBRE_ESTADO: Record<EstadoSuscripcion, string> = {
  prueba: 'En prueba',
  activa: 'Activa',
  morosa: 'Pago pendiente',
  vencida: 'Vencida',
  cancelada: 'Cancelada',
};

/** "499.00 MXN / mes", o el aviso de que el precio no se ha publicado. */
export function textoPrecio(plan: PlanCatalogo): string {
  if (plan.precio_mensual === null) return 'Precio por definir';
  const monto = Number(plan.precio_mensual).toLocaleString('es-MX', {
    minimumFractionDigits: 2, maximumFractionDigits: 2,
  });
  return `$${monto} ${plan.moneda} / mes`;
}

/** Fecha ISO → "19 nov 2026". */
export function fechaCorta(iso: string): string {
  return new Date(iso).toLocaleDateString('es-MX', {
    day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC',
  });
}
