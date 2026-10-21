/**
 * CFDI de retenciones e información de pagos 2.0 (P3-04).
 *
 * Contrato: `docs/api-contract.md`, sección "CFDI de retenciones". El backend sella con el
 * CSD del cliente, valida contra el XSD y timbra con el PAC configurado; aquí sólo se pide.
 */

import { apiArchivo, apiFetch } from './api';

export interface TerceroRetencion {
  rfc: string;
  nombre: string;
  regimen: string;
  domicilio_fiscal: string;
  monto_operacion: string;
  isr_retenido: string;
  iva_retenido: string;
  cantidad_cfdi: number;
  cve_retenc_sugerida: string;
  uuids: string[];
}

export interface CfdiRetencion {
  uuid: string;
  rfc_tercero: string;
  nombre_tercero: string;
  ejercicio: number;
  mes_ini: number;
  mes_fin: number;
  cve_retenc: string;
  monto_operacion: string;
  isr_retenido: string;
  iva_retenido: string;
  estado: 'timbrado' | 'cancelacion_en_proceso' | 'cancelado';
  pac: string;
  es_prueba: boolean;
  fecha_timbrado: string;
  motivo_cancelacion: string;
}

export interface PeriodoRetencion {
  ejercicio: number;
  mes_ini: number;
  mes_fin: number;
}

const enc = encodeURIComponent;
const base = (clave: string) => `/clientes/${enc(clave)}/retenciones-cfdi`;

export function obtenerTerceros(
  clave: string, p: PeriodoRetencion,
): Promise<{ terceros: TerceroRetencion[]; emitidos: CfdiRetencion[] }> {
  const q = new URLSearchParams({
    ejercicio: String(p.ejercicio), mes_ini: String(p.mes_ini), mes_fin: String(p.mes_fin),
  });
  return apiFetch(`${base(clave)}/terceros?${q}`);
}

export function emitirCfdiRetencion(
  clave: string, rfcTercero: string, p: PeriodoRetencion,
  extra: { cve_retenc?: string; domicilio_fiscal?: string } = {},
): Promise<{ cfdi: CfdiRetencion }> {
  return apiFetch(base(clave), {
    method: 'POST', json: { rfc_tercero: rfcTercero, ...p, ...extra },
    // Sellar, validar y timbrar puede tardar más que una consulta.
    timeoutMs: 90000,
  });
}

export function cancelarCfdiRetencion(
  clave: string, uuid: string, motivo: string, folioSustitucion?: string,
): Promise<{ cfdi: CfdiRetencion }> {
  return apiFetch(`${base(clave)}/${enc(uuid)}/cancelar`, {
    method: 'POST', json: { motivo, folio_sustitucion: folioSustitucion || null },
  });
}

export function descargarCfdiRetencion(clave: string, uuid: string, tipo: 'xml' | 'pdf'): Promise<Blob> {
  return apiArchivo(`${base(clave)}/${enc(uuid)}/${tipo}`);
}
