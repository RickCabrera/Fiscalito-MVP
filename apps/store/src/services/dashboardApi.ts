/**
 * Dashboard del despacho (P5-02): una sola llamada con todas las tarjetas.
 * Contrato: `docs/api-contract.md`, sección "Dashboard del despacho".
 */

import { apiFetch } from './api';
import type { Semaforo } from './semaforoSat';

interface ConEnlace { enlace: string }

export interface RenglonVencimiento extends ConEnlace {
  clave: string;
  cliente: string;
  cliente_nombre: string;
  nombre: string;
  periodo: string;
  fecha_limite: string;
  estado: string;
}

export interface Dashboard {
  hoy: string;
  rol: string;
  clientes: number;
  vencimientos: ConEnlace & { semana: number; vencidas: number; renglones: RenglonVencimiento[] };
  credenciales: ConEnlace & {
    total: number; vencidas: number;
    renglones: (ConEnlace & { cliente: string; cliente_nombre: string; nombre: string;
      tipo: string; vence: string; dias: number; vencida: boolean })[];
  };
  alertas: ConEnlace & { total: number; alta: number; media: number; baja: number;
    enlaces: Record<string, string> };
  descarga_sat: ConEnlace & {
    resumen: Record<string, number>;
    renglones: (ConEnlace & { cliente: string; cliente_nombre: string; estado: string;
      ultima_descarga: string | null; alertas: number })[];
  };
  opinion: ConEnlace & Record<Semaforo, number> & {
    renglones: (ConEnlace & { cliente: string; cliente_nombre: string; semaforo: Semaforo;
      fecha: string | null; resultado: string | null })[];
  };
  nominas: {
    por_cerrar: number; por_timbrar: number;
    renglones: (ConEnlace & { id: number; cliente: string; cliente_nombre: string;
      inicio: string; fin: string; fecha_pago: string; estado: string;
      accion: 'cerrar' | 'timbrar' })[];
  };
  agenda: ConEnlace & {
    total: number; atrasadas: number;
    renglones: (ConEnlace & { id: number; titulo: string; fecha: string; atrasada: boolean;
      cliente_nombre: string })[];
  };
  /** `null` para el auxiliar: los honorarios no son suyos. */
  cobranza: (ConEnlace & {
    vencido: string; clientes: number;
    renglones: (ConEnlace & { cliente: string; cliente_nombre: string; vencido: string;
      vencido_desde: string | null })[];
  }) | null;
}

export function obtenerDashboard(): Promise<Dashboard> {
  return apiFetch('/dashboard');
}
