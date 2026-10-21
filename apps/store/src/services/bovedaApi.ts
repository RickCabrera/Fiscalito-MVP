/**
 * Bóveda de CFDI del cliente (plan P, P0-03).
 *
 * Contrato: `docs/api-contract.md`, sección "Bóveda de CFDI". Todo va por
 * `apiFetch`/`apiArchivo` de `api.ts`, que adjunta el token y traduce errores.
 */

import { apiArchivo, apiFetch } from './api';
import type { CFDIFiscal } from './fiscalAgentApi';

export type TipoCfdi = 'I' | 'E' | 'P' | 'N' | 'T';
export type DireccionCfdi = 'emitido' | 'recibido';
export type EstatusSat = 'vigente' | 'cancelado' | 'desconocido';

export interface ComprobanteBoveda {
  uuid: string;
  version: string;
  tipo: TipoCfdi;
  fecha: string;
  serie: string;
  folio: string;
  rfc_emisor: string;
  nombre_emisor: string;
  rfc_receptor: string;
  nombre_receptor: string;
  direccion: DireccionCfdi;
  subtotal: string;
  descuento: string;
  total: string;
  moneda: string;
  metodo_pago: string;
  forma_pago: string;
  uso_cfdi: string;
  iva_trasladado: string;
  iva_retenido: string;
  isr_retenido: string;
  ieps: string;
  estatus_sat: EstatusSat;
  origen: 'manual' | 'sat';
  /** P1-03: cuándo se consultó el SAT y si hay una cancelación "En proceso". */
  fecha_estatus?: string | null;
  estatus_cancelacion?: string;
  /** P1-04: la contraparte está en un listado del SAT (69-B o 69). */
  art_69b?: { lista: string; situacion: string; nivel: 'alto' | 'medio' | 'info' } | null;
}

export interface ReporteImportacion {
  exito: boolean;
  rfc_cliente: string;
  rfc_deducido: boolean;
  importados: number;
  duplicados: number;
  rechazados: { archivo: string; razon: string }[];
  importados_detalle: { archivo: string; uuid: string; direccion: DireccionCfdi; tipo: TipoCfdi }[];
  duplicados_detalle: { archivo: string; uuid: string; razon: string }[];
}

export interface PaginaBoveda {
  exito: boolean;
  total: number;
  pagina: number;
  por_pagina: number;
  comprobantes: ComprobanteBoveda[];
}

export interface RenglonResumen {
  periodo: string;
  tipo: TipoCfdi;
  direccion: DireccionCfdi;
  cantidad: number;
  total: string;
}

export interface FiltrosBoveda {
  desde?: string;
  hasta?: string;
  tipo?: TipoCfdi | '';
  direccion?: DireccionCfdi | '';
  rfc?: string;
  estatus?: EstatusSat | '';
  pagina?: number;
  por_pagina?: number;
}

function base(clave: string): string {
  return `/boveda/clientes/${encodeURIComponent(clave)}`;
}

/** Query string sin los filtros vacíos. */
export function consultaDeFiltros(f: FiltrosBoveda): string {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(f)) {
    if (v !== undefined && v !== null && v !== '') q.set(k, String(v));
  }
  const s = q.toString();
  return s ? `?${s}` : '';
}

/** Sube XML y/o ZIP. Una carga grande puede tardar: el límite es de 5 minutos. */
export function importarCfdi(clave: string, archivos: File[]): Promise<ReporteImportacion> {
  const datos = new FormData();
  for (const a of archivos) datos.append('archivos', a, a.name);
  return apiFetch<ReporteImportacion>(`${base(clave)}/cfdi`, {
    method: 'POST',
    body: datos,
    timeoutMs: 300000,
  });
}

export function listarCfdi(clave: string, filtros: FiltrosBoveda = {}): Promise<PaginaBoveda> {
  return apiFetch<PaginaBoveda>(`${base(clave)}/cfdi${consultaDeFiltros(filtros)}`);
}

/** El XML original, tal como se subió. */
export function descargarXml(clave: string, uuid: string): Promise<Blob> {
  return apiArchivo(`${base(clave)}/cfdi/${encodeURIComponent(uuid)}/xml`);
}

export function borrarCfdi(clave: string, uuid: string): Promise<{ exito: boolean; uuid: string }> {
  return apiFetch(`${base(clave)}/cfdi/${encodeURIComponent(uuid)}`, { method: 'DELETE' });
}

export function resumenBoveda(
  clave: string,
  filtros: Pick<FiltrosBoveda, 'desde' | 'hasta'> = {},
): Promise<{ exito: boolean; renglones: RenglonResumen[] }> {
  return apiFetch(`${base(clave)}/resumen${consultaDeFiltros(filtros)}`);
}

// ── P1-06: los módulos leen la bóveda ──

/** Qué se tomó de la bóveda para un cálculo y qué se dejó fuera. */
export interface ResumenFacturasCalculo {
  comprobantes: number;
  emitidos: number;
  recibidos: number;
  por_tipo: Partial<Record<TipoCfdi, number>>;
  cancelados_excluidos: number;
  nomina_excluidos: number;
  relacionados_fuera_del_periodo: number;
}

export interface FacturasDeBoveda {
  /** Los CFDI vigentes del periodo, sin nómina, en la forma que piden los cálculos. */
  facturas: CFDIFiscal[];
  /** Originales PPD de OTROS periodos que los pagos del periodo liquidan (sólo para el motor). */
  relacionados: CFDIFiscal[];
  resumen: ResumenFacturasCalculo;
  advertencias: string[];
}

type CfdiCrudo = Omit<CFDIFiscal, 'uuid_relacionado' | 'monto_pago'> & {
  uuid_relacionado?: string | null;
  monto_pago?: number | null;
};

/** El backend manda `null` donde el tipo del front usa "ausente". */
function aCfdi({ uuid_relacionado, monto_pago, ...resto }: CfdiCrudo): CFDIFiscal {
  return {
    ...resto,
    ...(uuid_relacionado ? { uuid_relacionado } : {}),
    ...(monto_pago !== null && monto_pago !== undefined ? { monto_pago } : {}),
  };
}

/**
 * Los CFDI del periodo listos para los endpoints de cálculo
 * (`GET /boveda/clientes/{clave}/facturas-calculo`). El backend ya quitó
 * cancelados y nómina; el tipo `CFDIFiscal` lo dice también aquí.
 */
export async function facturasParaCalculo(
  clave: string,
  periodo: { desde: string; hasta: string; tipos?: TipoCfdi[] },
): Promise<FacturasDeBoveda> {
  const q = new URLSearchParams({ desde: periodo.desde, hasta: periodo.hasta });
  if (periodo.tipos?.length) q.set('tipos', periodo.tipos.join(','));
  const r = await apiFetch<{
    facturas: CfdiCrudo[]; relacionados: CfdiCrudo[];
    resumen: ResumenFacturasCalculo; advertencias?: string[];
  }>(`${base(clave)}/facturas-calculo?${q.toString()}`);
  return {
    facturas: r.facturas.map(aCfdi),
    relacionados: (r.relacionados ?? []).map(aCfdi),
    resumen: r.resumen,
    advertencias: r.advertencias ?? [],
  };
}
