/**
 * Facturación CFDI 4.0 (P5-04). Contrato: `docs/api-contract.md`, "Facturación CFDI 4.0".
 *
 * Los importes viajan como texto decimal y NO se calculan aquí: subtotal, impuestos y total los
 * calcula el motor del backend (`app/facturacion/calculo.py`). La pantalla sólo captura.
 */

import { apiArchivo, apiFetch } from './api';

export type TipoCfdi = 'I' | 'E' | 'P';
export type EstadoFactura = 'timbrado' | 'cancelacion_en_proceso' | 'cancelado';

export interface ImpuestoCaptura {
  tipo: 'traslado' | 'retencion';
  impuesto: '001' | '002';
  tipo_factor: 'Tasa' | 'Exento';
  tasa: string | null;
}

export interface ConceptoCaptura {
  clave_prod_serv: string;
  cantidad: string;
  clave_unidad: string;
  descripcion: string;
  valor_unitario: string;
  descuento?: string;
  objeto_imp: '01' | '02' | '03';
  impuestos: ImpuestoCaptura[];
}

export interface Relacion {
  tipo_relacion: string;
  uuids: string[];
}

export interface FacturaCaptura {
  tipo: 'I' | 'E';
  receptor: {
    clave_cliente?: string | null;
    rfc?: string;
    nombre?: string;
    regimen?: string;
    codigo_postal?: string;
    uso_cfdi: string;
  };
  conceptos: ConceptoCaptura[];
  forma_pago: string;
  metodo_pago: 'PUE' | 'PPD';
  serie?: string | null;
  relacionados: Relacion[];
  cargo_id?: number | null;
}

export interface Factura {
  id: number;
  tipo: TipoCfdi;
  serie: string;
  folio: string;
  uuid: string;
  rfc_receptor: string;
  nombre_receptor: string;
  metodo_pago: string;
  forma_pago: string;
  uso_cfdi: string;
  subtotal: string;
  descuento: string;
  traslados: string;
  retenciones: string;
  total: string;
  saldo: string | null;
  estado: EstadoFactura;
  es_prueba: boolean;
  fecha_emision: string;
  cargo_id: number | null;
  motivo_cancelacion: string;
  folio_sustitucion: string;
  relacionados: Relacion[];
}

export interface Opcion {
  clave: string;
  descripcion: string;
}

export interface Preset {
  clave: string;
  impuesto: '001' | '002';
  tipo_factor?: 'Tasa' | 'Exento';
  tasa: string | null;
  nombre: string;
}

export interface Catalogos {
  forma_pago: Opcion[];
  metodo_pago: Opcion[];
  uso_cfdi: Opcion[];
  regimen_fiscal: Opcion[];
  objeto_imp: Opcion[];
  tipo_relacion: Opcion[];
  clave_unidad: Opcion[];
  clave_prod_serv: Opcion[];
  motivo_cancelacion: Opcion[];
  presets: { traslados: Preset[]; retenciones: Preset[] };
}

export interface PagoCaptura {
  fecha_pago: string;
  forma_pago: string;
  num_operacion?: string;
  documentos: { factura_id: number; importe_pagado: string }[];
}

const base = (clave: string) => `/clientes/${encodeURIComponent(clave)}/facturas`;

export async function catalogosFacturacion(): Promise<Catalogos> {
  return apiFetch<Catalogos>('/facturacion/catalogos');
}

export async function configFacturacion(): Promise<string | null> {
  return (await apiFetch<{ cliente_propio: string | null }>('/facturacion/config')).cliente_propio;
}

export async function guardarConfigFacturacion(clave: string | null): Promise<string | null> {
  const r = await apiFetch<{ cliente_propio: string | null }>('/facturacion/config', {
    method: 'PUT', json: { cliente_propio: clave } });
  return r.cliente_propio;
}

export async function listarFacturas(clave: string): Promise<{ es_propio: boolean; facturas: Factura[] }> {
  return apiFetch(base(clave));
}

export async function emitirFactura(clave: string, f: FacturaCaptura): Promise<Factura> {
  return (await apiFetch<{ factura: Factura }>(base(clave), { method: 'POST', json: f })).factura;
}

export async function emitirPago(clave: string, p: PagoCaptura): Promise<Factura> {
  return (await apiFetch<{ factura: Factura }>(`${base(clave)}/pagos`, { method: 'POST', json: p })).factura;
}

export async function cancelarFactura(
  clave: string, id: number, motivo: string, folioSustitucion: string,
): Promise<Factura> {
  const r = await apiFetch<{ factura: Factura }>(`${base(clave)}/${id}/cancelar`, {
    method: 'POST', json: { motivo, folio_sustitucion: motivo === '01' ? folioSustitucion.trim() : null } });
  return r.factura;
}

export async function descargarFactura(clave: string, id: number, formato: 'xml' | 'pdf'): Promise<Blob> {
  return apiArchivo(`${base(clave)}/${id}/${formato}`);
}

/** Factura sugerida para un cargo de cobranza (P5-03) y su emisión desde el cliente propio. */
export async function facturarCargo(cargoId: number): Promise<Factura> {
  const { borrador } = await apiFetch<{ borrador: FacturaCaptura & { emisor: string } }>(
    `/facturacion/cargos/${cargoId}/borrador`);
  const { emisor, ...captura } = borrador;
  return emitirFactura(emisor, captura);
}
