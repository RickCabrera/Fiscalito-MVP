/**
 * DIOT con el layout de carga masiva 2025 del SAT (P3-05).
 *
 * Contrato: `docs/api-contract.md`, sección "DIOT con layout 2025". Los cortes por tasa salen
 * de los conceptos de cada CFDI de la bóveda y el `.txt` lo arma y lo valida el backend contra
 * el instructivo vigente; el front ya no serializa nada.
 */

import { apiArchivo, apiFetch } from './api';

export interface ConfigProveedorDiot {
  tipo_tercero: '04' | '05' | '15' | null;
  tipo_operacion: '02' | '03' | '06' | '07' | '08' | '85' | '87' | null;
  region_8: 'norte' | 'sur';
  importacion: 'tangibles' | 'intangibles';
  asignacion_iva: 'gravadas' | 'proporcion';
  iva_no_acreditable: '' | 'proporcion' | 'requisitos' | 'exentas' | 'no_objeto';
  id_fiscal: string;
  nombre_extranjero: string;
  pais: string;
  jurisdiccion: string;
  efectos_fiscales: '01' | '02';
}

export interface ProveedorDiot {
  rfc: string;
  nombre: string;
  tipo_tercero: string;
  tipo_operacion: string;
  clasificacion_capturada: boolean;
  config: ConfigProveedorDiot;
  campos: Record<string, number>;
  cantidad_cfdi: number;
  advertencias: string[];
  linea: string;
}

export interface DiotMes {
  anio: number;
  mes: number;
  total_proveedores: number;
  proveedores: ProveedorDiot[];
  advertencias: string[];
  errores_layout: string[];
  layout: string;
}

export const TIPOS_TERCERO: Record<string, string> = {
  '04': 'Nacional', '05': 'Extranjero', '15': 'Global',
};

export const TIPOS_OPERACION: Record<string, string> = {
  '02': 'Enajenación de bienes', '03': 'Servicios profesionales',
  '06': 'Uso o goce temporal (arrendamiento)', '07': 'Importación',
  '08': 'Importación por transferencia virtual', '85': 'Otros', '87': 'Operaciones globales',
};

const enc = encodeURIComponent;

export function obtenerDiot(clave: string, anio: number, mes: number): Promise<DiotMes> {
  return apiFetch(`/clientes/${enc(clave)}/diot/${anio}/${mes}`);
}

export function descargarDiotTxt(clave: string, anio: number, mes: number): Promise<Blob> {
  return apiArchivo(`/clientes/${enc(clave)}/diot/${anio}/${mes}/txt`);
}

export function guardarConfigProveedor(
  clave: string, rfc: string, config: ConfigProveedorDiot,
): Promise<{ exito: boolean }> {
  return apiFetch(`/clientes/${enc(clave)}/diot/proveedores/${enc(rfc)}`, {
    method: 'PUT', json: config,
  });
}
