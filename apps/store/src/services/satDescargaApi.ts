/**
 * Descarga masiva del SAT por cliente (P1-01, P1-02).
 *
 * Contrato: `docs/api-contract.md`, sección "Descarga masiva del SAT". Todo va
 * por `apiFetch`, que adjunta el token y traduce los errores a español.
 */

import { apiFetch } from './api';

export type EstadoDia = 'completo' | 'en_proceso' | 'sin_movimientos' | 'fallido' | 'no_solicitado';

export type EstadoSolicitud =
  | 'pendiente' | 'solicitada' | 'en_proceso' | 'descargando'
  | 'terminada' | 'sin_datos' | 'fallida' | 'dividida';

export interface ConfigDescarga {
  activa: boolean;
  emitidos: boolean;
  recibidos: boolean;
  metadata: boolean;
  cancelados: boolean;
  desde: string | null;
  hora: string;
  pausada_por: string | null;
  ultimo_dia_encolado: string | null;
}

export interface EstadoEfirma {
  vigente: boolean;
  valido_hasta: string | null;
  mensaje: string;
}

export interface AlertaSat {
  id: number;
  tipo: string;
  mensaje: string;
  solicitud_id: number | null;
  creado_en: string | null;
}

export interface RespuestaConfig {
  exito: boolean;
  config: ConfigDescarga;
  efirma: EstadoEfirma;
  alertas: AlertaSat[];
}

export interface SolicitudSat {
  id: number;
  direccion: 'emitidos' | 'recibidos';
  tipo: 'cfdi' | 'metadata';
  estado_comprobante: string;
  fecha_inicial: string;
  fecha_final: string;
  origen: string;
  id_solicitud: string;
  estado: EstadoSolicitud;
  codigo: string;
  mensaje: string;
  paquetes: number;
  paquetes_procesados: number;
  xml_importados: number;
  duplicados: number;
  metadata_registros: number;
  proxima_verificacion: string | null;
  creado_en: string | null;
}

export interface PaginaSolicitudes {
  exito: boolean;
  total: number;
  pagina: number;
  por_pagina: number;
  solicitudes: SolicitudSat[];
}

export interface DiaBitacora {
  fecha: string;
  estado: EstadoDia;
  solicitudes: number;
  emitidos: number;
  recibidos: number;
  metadata: number;
  cancelados: number;
  mensaje: string;
}

export interface Seleccion {
  emitidos: boolean;
  recibidos: boolean;
  metadata: boolean;
  cancelados: boolean;
}

export interface Encolado {
  trabajo_id: number;
  inicio: string;
  fin: string;
}

const base = (clave: string) => `/sat/clientes/${encodeURIComponent(clave)}`;

export function obtenerConfigSat(clave: string): Promise<RespuestaConfig> {
  return apiFetch<RespuestaConfig>(`${base(clave)}/config`);
}

export function guardarConfigSat(
  clave: string,
  cambios: Partial<Omit<ConfigDescarga, 'pausada_por' | 'ultimo_dia_encolado'>>,
): Promise<RespuestaConfig> {
  return apiFetch<RespuestaConfig>(`${base(clave)}/config`, { method: 'PUT', json: cambios });
}

export async function descargarAhora(
  clave: string, desde: string, hasta: string, seleccion?: Seleccion,
): Promise<Encolado[]> {
  const r = await apiFetch<{ encolados: Encolado[] }>(`${base(clave)}/descargar`, {
    method: 'POST', json: { desde, hasta, seleccion },
  });
  return r.encolados ?? [];
}

export async function descargaHistorica(
  clave: string, desde: string, hasta?: string, seleccion?: Seleccion,
): Promise<Encolado[]> {
  const r = await apiFetch<{ encolados: Encolado[] }>(`${base(clave)}/historica`, {
    method: 'POST', json: { desde, hasta, seleccion },
  });
  return r.encolados ?? [];
}

export function listarSolicitudesSat(
  clave: string, pagina = 1, porPagina = 20,
): Promise<PaginaSolicitudes> {
  return apiFetch<PaginaSolicitudes>(
    `${base(clave)}/solicitudes?pagina=${pagina}&por_pagina=${porPagina}`,
  );
}

export async function obtenerBitacoraSat(
  clave: string, anio: number, mes: number,
): Promise<DiaBitacora[]> {
  const r = await apiFetch<{ dias: DiaBitacora[] }>(
    `${base(clave)}/bitacora?anio=${anio}&mes=${mes}`,
  );
  return r.dias ?? [];
}
