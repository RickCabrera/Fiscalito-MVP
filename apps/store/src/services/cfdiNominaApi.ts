/**
 * Cliente de `POST /api/v1/nomina/cfdi`: el CFDI de nómina **sin timbrar** (T4).
 *
 * LO QUE SALE DE AQUÍ NO ES UN CFDI FISCALMENTE VÁLIDO
 * -----------------------------------------------------
 * Es un pre-recibo: estructuralmente válido contra los XSD del SAT y
 * fiscalmente nada. No lleva Timbre Fiscal Digital y sus atributos de sello son
 * centinelas. **El timbrado con un PAC está fuera de alcance** por el
 * `CLAUDE.md` de la raíz, así que la pantalla lo dice en el badge y el archivo
 * lo lleva en el nombre. La respuesta trae `timbrado: false` y no se deriva de
 * nada del front: lo afirma el backend.
 *
 * NINGÚN IMPORTE SE CALCULA NI SE ARMA AQUÍ
 * ------------------------------------------
 * El recibo viaja **tal como lo devolvió el motor** en `/nomina/calcular-periodo`.
 * Este módulo no suma, no redondea y no parte gravado/exento: si lo hiciera,
 * sería una segunda verdad sobre los mismos números, que es justo lo que
 * `nominaDemoApi.ts` y `carteraApi.ts` declaran en sus encabezados.
 *
 * LO QUE SÍ DECIDE ESTE MÓDULO: EL MAPA DE CATÁLOGOS
 * ---------------------------------------------------
 * `tipo_contrato` del modelo de la cartera (`indeterminado`, `prueba`…) a las
 * claves de `c_TipoContrato`. Es la misma frontera que `tipoParaApi` en
 * `fiscalAgentApi.ts`, y por la misma razón: un `Record` exhaustivo rompe el
 * build cuando alguien agrega un tipo de contrato, en vez de mandar una clave
 * inventada que el SAT rechazaría.
 *
 * Y LO QUE NO DECIDE: LAS IDENTIDADES
 * ------------------------------------
 * RFC, CURP, NSS y códigos postales **no se inventan ni se derivan**. El modelo
 * de la cartera no los guarda todavía (los tres clientes de demostración no
 * traen ni el RFC del patrón), así que `faltantesParaCFDI` los enumera y la
 * pantalla los pide. Un XML con una CURP de relleno lleva el nombre de una
 * persona real y los datos de nadie.
 */

import { cuerpoDeError, detalleDelError } from './errorApi';
import type { ReciboNomina } from './nominaDemoApi';
import type { TipoContrato } from './carteraApi';

const BASE_URL = import.meta.env.VITE_FISCAL_AGENT_URL || 'http://localhost:8000';
const V1 = `${BASE_URL}/api/v1`;

/**
 * El mapa a `c_TipoContrato` del complemento de nómina 1.2.
 *
 * Fuente: catálogo `c_TipoContrato` del Anexo 20, tal como lo transcribe
 * `apps/api/knowledge_base/nomina/24_cfdi_nomina_12.md` §3. Exhaustivo a
 * propósito: agregar un tipo de contrato al modelo rompe el build aquí y obliga
 * a decidir su clave, en vez de mandar una que el PAC rechace.
 */
export const CLAVE_TIPO_CONTRATO: Record<TipoContrato, string> = {
  indeterminado: '01',
  obra_determinada: '02',
  determinado: '03',
  prueba: '05',
};

/** El subconjunto del recibo que el CFDI usa. Espeja `ReciboCFDISchema`. */
export type ReciboParaCFDI = Pick<
  ReciboNomina,
  'empleado_no' | 'nombre' | 'dias_pagados' | 'percepciones' | 'deducciones' | 'otros_pagos'
>;

export interface PatronCFDI {
  rfc: string;
  nombre: string;
  regimen_fiscal: string;
  registro_patronal: string;
  codigo_postal: string;
  clave_entidad: string;
}

export interface TrabajadorCFDI {
  rfc: string;
  nombre: string;
  curp: string;
  numero_seguridad_social: string;
  codigo_postal: string;
  fecha_inicio_relacion_laboral: string;
  tipo_contrato: string;
  numero_empleado: string;
  puesto: string;
  riesgo_puesto: string;
  periodicidad_pago: string;
  salario_base_cotizacion: string;
  salario_diario_integrado: string;
  /** Vacía = el backend la deriva en semanas completas hasta el fin del periodo. */
  antiguedad?: string;
  departamento?: string;
}

export interface CFDINominaRequest {
  recibo: ReciboParaCFDI;
  patron: PatronCFDI;
  trabajador: TrabajadorCFDI;
  periodo: { inicio: string; fin: string; fecha_pago?: string | null };
  tipo_nomina?: 'O' | 'E';
  serie?: string;
  folio?: string;
}

export interface CFDINominaResponse {
  exito: boolean;
  xml: string;
  /** Siempre `false`. Lo afirma el backend; el front no lo deriva. */
  timbrado: boolean;
  nombre_archivo: string;
  advertencia: string;
}

/**
 * Los campos del CFDI que este empleado o su patrón **no tienen capturados**.
 *
 * Devuelve etiquetas para pintar, no claves: el operador tiene que leer qué le
 * falta. Lista vacía = se puede generar.
 *
 * **La guarda de verdad es el 422 del backend**, que valida los mismos campos
 * sin confiar en esta función. Ésta existe para que la pantalla lo diga ANTES
 * de mandar, no para sustituirla — el modo de falla que evita es el del botón
 * que parece listo y truena.
 */
export function faltantesParaCFDI(
  patron: Partial<PatronCFDI>,
  trabajador: Partial<TrabajadorCFDI>,
): string[] {
  const falta: string[] = [];
  const pide = (valor: string | undefined, etiqueta: string) => {
    if (!valor || !valor.trim()) falta.push(etiqueta);
  };

  pide(patron.rfc, 'RFC del patrón');
  pide(patron.nombre, 'Razón social del patrón');
  pide(patron.regimen_fiscal, 'Régimen fiscal del patrón');
  pide(patron.registro_patronal, 'Registro patronal');
  pide(patron.codigo_postal, 'CP del patrón');
  pide(patron.clave_entidad, 'Entidad federativa del patrón');

  pide(trabajador.rfc, 'RFC del trabajador');
  pide(trabajador.curp, 'CURP');
  pide(trabajador.numero_seguridad_social, 'NSS');
  pide(trabajador.codigo_postal, 'CP del trabajador');
  pide(trabajador.fecha_inicio_relacion_laboral, 'Fecha de alta');
  pide(trabajador.riesgo_puesto, 'Clase de riesgo del puesto');
  pide(trabajador.puesto, 'Puesto');

  return falta;
}

/**
 * Pide el XML al backend. **No lo descarga**: eso lo decide quien llama.
 *
 * El XML lleva RFC, CURP, NSS y salarios de una persona. No se loguea, no se
 * guarda y no se manda a ninguna otra parte — la misma regla que
 * `SelectorExportacion` ya declara para los TXT del IMSS.
 */
export async function generarCFDINomina(
  req: CFDINominaRequest,
): Promise<CFDINominaResponse> {
  const res = await fetch(`${V1}/nomina/cfdi`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    throw new Error(
      `No se pudo generar el CFDI de nómina: ${detalleDelError(res, await cuerpoDeError(res))}`,
    );
  }
  return res.json() as Promise<CFDINominaResponse>;
}

/**
 * El recibo recortado a lo que el CFDI usa.
 *
 * **Las partidas viajan como llegaron del motor**: es un `Pick`, no un armado.
 * El recorte no es por ahorrar bytes sino para que el cuerpo diga qué se usa de
 * verdad — el backend ignora los campos de más, así que mandar el recibo entero
 * también funcionaría y escondería el contrato.
 */
export function reciboParaCFDI(recibo: ReciboNomina): ReciboParaCFDI {
  return {
    empleado_no: recibo.empleado_no,
    nombre: recibo.nombre,
    dias_pagados: recibo.dias_pagados,
    percepciones: recibo.percepciones,
    deducciones: recibo.deducciones,
    otros_pagos: recibo.otros_pagos,
  };
}
