/**
 * De dónde salen las facturas de un cálculo (P1-06): la bóveda del cliente (por
 * defecto) o archivos sueltos subidos a mano.
 *
 * Es la ÚNICA decisión de fuente de Fiscalito y Contabilito. Cada tab le dice su
 * cliente, su periodo y su lista manual, y recibe:
 *
 * - `paraCalcular` — lo que va a los endpoints de cálculo. Desde la bóveda ya viene
 *   sin cancelados ni nómina (lo filtra el backend); de archivos sueltos se filtra
 *   con `facturasFiscales`, como siempre.
 * - `delPeriodo` — lo que se enseña en pantalla o se contabiliza (sin los PPD de
 *   otros periodos que la bóveda manda sólo para cruzar pagos).
 * - `motivoVacio` — el texto honesto de por qué no hay con qué calcular.
 *
 * Sin cliente activo (o sin la bóveda a la mano) la fuente es archivos sueltos, igual
 * que antes de P1-06.
 */

import { useState } from 'react';
import { facturasFiscales, type CFDI, type CFDIFiscal } from '../../services/fiscalAgentApi';
import {
  periodoDeAnio,
  periodoDeMes,
  useFacturasDeBoveda,
  type EstadoBoveda,
} from './useFacturasDeBoveda';

export type ModoFuente = 'boveda' | 'archivos';

const MESES = [
  'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
  'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre',
];

export interface OpcionesFuente {
  /** Clave del cliente activo; `null` = no hay bóveda que leer. */
  clave: string | null;
  anio: number;
  /** Sin mes = el ejercicio completo. */
  mes?: number;
  /** La lista que el tab ya lleva de archivos sueltos. */
  manual: CFDI[];
  /**
   * Manda también los originales PPD de otros periodos que los pagos del periodo
   * liquidan (pre-declaración, anual, multi-periodo, estado de cuenta: el motor cruza
   * el pago con su factura). DIOT, retenciones y Contabilito NO: contarían una
   * factura de otro mes como si fuera de éste.
   */
  conRelacionados?: boolean;
  /** Empieza en archivos sueltos (p. ej. el asistente ya cargó XML de demostración). */
  preferirArchivos?: boolean;
}

export interface FuenteFacturas {
  modo: ModoFuente;
  setModo: (m: ModoFuente) => void;
  /** `true` si hay cliente y por tanto se puede elegir la bóveda. */
  hayBoveda: boolean;
  boveda: EstadoBoveda & { recargar: () => void };
  etiqueta: string;
  paraCalcular: CFDIFiscal[];
  delPeriodo: CFDI[];
  motivoVacio: string;
}

export function useFuenteFacturas(o: OpcionesFuente): FuenteFacturas {
  const hayBoveda = Boolean(o.clave);
  const [elegido, setModo] = useState<ModoFuente>(o.preferirArchivos ? 'archivos' : 'boveda');
  const modo: ModoFuente = hayBoveda ? elegido : 'archivos';
  const periodo = o.mes ? periodoDeMes(o.anio, o.mes) : periodoDeAnio(o.anio);
  const boveda = useFacturasDeBoveda(o.clave, periodo, modo === 'boveda');
  const etiqueta = o.mes ? `${MESES[o.mes - 1]} ${o.anio}` : `el ejercicio ${o.anio}`;

  let paraCalcular: CFDIFiscal[];
  let delPeriodo: CFDI[];
  let motivoVacio: string;
  if (modo === 'archivos') {
    paraCalcular = facturasFiscales(o.manual);
    delPeriodo = o.manual;
    motivoVacio = 'Sube al menos una factura XML.';
  } else if (boveda.estado === 'listo') {
    delPeriodo = boveda.datos.facturas;
    paraCalcular = o.conRelacionados
      ? [...boveda.datos.facturas, ...boveda.datos.relacionados]
      : boveda.datos.facturas;
    motivoVacio = `La bóveda de este cliente no tiene CFDI vigentes de ${etiqueta}. `
      + 'Cárgalos en la Bóveda o con la Descarga SAT, o usa archivos sueltos.';
  } else {
    paraCalcular = [];
    delPeriodo = [];
    motivoVacio = boveda.estado === 'error'
      ? boveda.error
      : 'Todavía se está leyendo la bóveda del cliente.';
  }
  // Un PPD de otro periodo solo no es "algo con qué calcular": sin facturas del periodo, vacío.
  if (delPeriodo.length === 0) paraCalcular = [];

  return { modo, setModo, hayBoveda, boveda, etiqueta, paraCalcular, delPeriodo, motivoVacio };
}
