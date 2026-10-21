/**
 * Contabilidad electrónica — Anexo 24 (P2-07). El backend arma, sella y valida
 * los XML contra el XSD oficial; aquí sólo se piden. Contrato:
 * `docs/api-contract.md`, sección "Contabilidad electrónica".
 */

import { apiArchivo, apiFetch } from './api';

export type DocumentoAnexo24 = 'catalogo' | 'balanza' | 'polizas' | 'auxiliar_cuentas' | 'auxiliar_folios';
export type TipoSolicitud = '' | 'AF' | 'FC' | 'DE' | 'CO';

export interface SolicitudAnexo24 {
  documento: DocumentoAnexo24;
  anio: number;
  mes: number;
  tipo_envio: 'N' | 'C';
  fecha_mod_bal: string | null;
  tipo_solicitud: TipoSolicitud;
  num_orden: string;
  num_tramite: string;
  sellar: boolean;
}

export interface InfoDocumentos {
  documentos: { clave: DocumentoAnexo24; nombre: string; sufijo: string; a_solicitud: boolean }[];
  instrucciones_portal: string[];
}

export interface ResultadoValidacion {
  nombre: string; valido: boolean; errores: string[]; advertencias: string[]; sellado: boolean; xml: string;
}

function base(clave: string): string {
  return `/contabilidad-electronica/clientes/${encodeURIComponent(clave)}`;
}

export function obtenerDocumentos(): Promise<InfoDocumentos> {
  return apiFetch('/contabilidad-electronica/documentos');
}

export function validarAnexo24(clave: string, s: SolicitudAnexo24): Promise<ResultadoValidacion> {
  return apiFetch(`${base(clave)}/validar`, { method: 'POST', json: s });
}

export function descargarZipAnexo24(clave: string, s: SolicitudAnexo24): Promise<Blob> {
  return apiArchivo(`${base(clave)}/zip`, { method: 'POST', json: s });
}

export function enviarAnexo24(
  clave: string, s: SolicitudAnexo24,
): Promise<{ via: string; acuse: { folio: string; estado: string; mensaje: string } }> {
  return apiFetch(`${base(clave)}/enviar`, { method: 'POST', json: s });
}
