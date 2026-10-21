/**
 * Dispersión bancaria (P4-12) y envío de recibos (P4-13). Contrato: `docs/api-contract.md`
 * §"Nómina — dispersión bancaria" y §"Nómina — envío de recibos".
 *
 * El front no arma ningún archivo bancario: el backend lo genera desde la nómina CERRADA,
 * lo relee y lo cuadra al centavo. Aquí sólo se decodifica el base64 para descargarlo.
 */

import { apiFetch } from './api';

export interface DatoBanco {
  clave: string; etiqueta: string; patron: string; obligatorio: boolean; default: string;
}

export interface LayoutDispersion {
  id: string; nombre: string; banco: string | null;
  estado: 'verificado' | 'por_confirmar'; fuente: string; interbancario: boolean;
  datos_requeridos: DatoBanco[];
}

export interface Layouts {
  layouts: LayoutDispersion[];
  columnas_genericas: Record<string, string>;
  columnas_default: string[];
  bancos: Record<string, string>;
  datos_guardados: Record<string, Record<string, string>>;
}

export interface PedidoDispersion {
  layout: string;
  cuenta_cargo_id?: number | null;
  fecha_aplicacion?: string | null;
  datos_banco?: Record<string, string>;
  columnas?: string[];
  separador?: string;
  formato?: 'csv' | 'xlsx';
}

export interface ResultadoDispersion {
  layout: LayoutDispersion;
  archivo: { nombre: string; mime: string; base64: string; sha256: string } | null;
  incluidos: { empleado_no: string; nombre: string; importe: string; banco: string; banco_nombre: string;
    tipo_cuenta: string; cuenta: string; interbancario: boolean }[];
  excluidos: { empleado_no: string; nombre: string; neto: string; causa: string; motivo: string }[];
  total_nomina: string; total_archivo: string; total_excluidos: string; cuadra: boolean;
  advertencias: string[];
}

const periodo = (cliente: string, id: number) =>
  `/nomina/clientes/${encodeURIComponent(cliente)}/periodos/${id}`;

export function listarLayouts(cliente: string): Promise<Layouts> {
  return apiFetch(`/nomina/dispersion/layouts?cliente=${encodeURIComponent(cliente)}`);
}

export function generarDispersion(cliente: string, periodoId: number, p: PedidoDispersion): Promise<ResultadoDispersion> {
  return apiFetch(`${periodo(cliente, periodoId)}/dispersion`, { method: 'POST', json: p });
}

export function bytesDeBase64(b64: string): Uint8Array {
  const bin = atob(b64);
  return Uint8Array.from(bin, (c) => c.charCodeAt(0));
}

// ── P4-13 ──

export type Canal = 'correo' | 'whatsapp';
export type EstadoEnvio = 'pendiente' | 'enviado' | 'fallido' | 'rebotado';

export interface EstadoEnvios {
  canal: Canal;
  envios: { id: number; empleado_no: string; destino: string; estado: EstadoEnvio; intentos: number;
    error: string; timbrado: boolean; enviado_en: string | null }[];
  omitidos: { empleado_no: string; nombre: string; motivo: string }[];
  resumen: Record<EstadoEnvio, number>;
  trabajo: { id: number; estado: string; error: string | null } | null;
}

export interface PlantillaRecibo {
  canal: Canal; asunto: string; cuerpo: string; plantilla_whatsapp: string; idioma: string;
  personalizada: boolean;
}

export function enviarRecibos(cliente: string, periodoId: number, canal: Canal): Promise<EstadoEnvios> {
  return apiFetch(`${periodo(cliente, periodoId)}/envios`, { method: 'POST', json: { canal } });
}

export function estadoEnvios(cliente: string, periodoId: number, canal: Canal): Promise<EstadoEnvios> {
  return apiFetch(`${periodo(cliente, periodoId)}/envios?canal=${canal}`);
}

export function reenviarRecibo(cliente: string, periodoId: number, envioId: number): Promise<EstadoEnvios> {
  return apiFetch(`${periodo(cliente, periodoId)}/envios/${envioId}/reenviar`, { method: 'POST' });
}

export function listarPlantillasRecibo(): Promise<{ variables: string[]; plantillas: PlantillaRecibo[] }> {
  return apiFetch('/nomina/recibos/plantillas');
}

export function guardarPlantillaRecibo(canal: Canal, p: Omit<PlantillaRecibo, 'canal' | 'personalizada'>): Promise<PlantillaRecibo> {
  return apiFetch(`/nomina/recibos/plantillas/${canal}`, { method: 'PUT', json: p });
}
