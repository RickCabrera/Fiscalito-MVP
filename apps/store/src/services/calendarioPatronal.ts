/**
 * Lógica pura del calendario patronal (E-07).
 *
 * Vive fuera de la pantalla por la misma razón que `clienteActivoStore` vive
 * fuera de su provider: un módulo que mezcla componentes con otras exportaciones
 * rompe el fast refresh de Vite (`react-refresh/only-export-components`). De
 * paso, esto se prueba sin jsdom.
 */

import type { ObligacionPatronal, RegimenDePlazo } from './despachoApi';

/** Días dentro de los cuales un vencimiento se considera "próximo". */
export const DIAS_PROXIMA = 30;

/** Etiqueta corta de la regla que produjo la fecha. Ver `RegimenDePlazo`. */
export const ETIQUETA_PLAZO: Record<RegimenDePlazo, string> = {
  imss: 'IMSS',
  imss_sin_prorroga: 'IMSS',
  imss_aviso: 'IMSS · aviso',
  sat: 'SAT',
  lft: 'LFT',
};

export type EstadoFecha = 'vencida' | 'proxima' | 'futura';

/**
 * Pura y con `hoy` explícito: lo contrario haría los tests dependientes del
 * reloj, que es justo lo que `despacho_demo.py` evita en el backend.
 *
 * El día del vencimiento **no** está vencido: todavía se puede presentar.
 */
export function estadoDeFecha(fechaLimite: string, hoy: Date): EstadoFecha {
  const limite = new Date(`${fechaLimite}T00:00:00`);
  const dia = new Date(hoy.getFullYear(), hoy.getMonth(), hoy.getDate());
  const diferencia = Math.round((limite.getTime() - dia.getTime()) / 86_400_000);
  if (diferencia < 0) return 'vencida';
  return diferencia <= DIAS_PROXIMA ? 'proxima' : 'futura';
}

/** Una obligación, con todos los clientes a los que aplica en esa fecha. */
export interface Renglon {
  obligacion: ObligacionPatronal;
  clientes: string[];
}

/**
 * Agrupa por fecha y, dentro, por obligación indistinguible.
 *
 * POR QUÉ NO UNA FILA POR CLIENTE: hoy los tres calendarios de la cartera son
 * idénticos —ninguna fecha depende del cliente todavía—, así que una fila por
 * cliente serían ~120 renglones repetidos con tres nombres distintos: un dato
 * constante disfrazado de dato por cliente.
 *
 * POR QUÉ LA CLAVE LLEVA `condicional` Y `nota`: son lo único que puede diferir
 * entre clientes en la misma fecha con la misma obligación, y dependen de datos
 * por cliente en cuanto F1-09 los registre. Sin ellos, dos clientes con distinta
 * personalidad jurídica se colapsarían en un renglón y uno de los dos textos
 * desaparecería sin que nada fallara.
 */
export function agrupar(obligaciones: ObligacionPatronal[]): [string, Renglon[]][] {
  const porFecha = new Map<string, Map<string, Renglon>>();
  for (const o of obligaciones) {
    const dia = porFecha.get(o.fecha_limite) ?? new Map<string, Renglon>();
    const clave = `${o.clave}|${o.periodo_cubierto}|${o.condicional}|${o.nota}`;
    const renglon = dia.get(clave) ?? { obligacion: o, clientes: [] };
    // O-01: en modo empresa única el backend manda `cliente_nombre` VACÍO —hay
    // un solo patrón y etiquetar cada renglón con el mismo nombre es ruido—, y
    // aquí se descarta en vez de meter una cadena vacía a la lista. Sin esto,
    // `clientes.join(' · ')` pintaba un separador suelto o una fila con un chip
    // en blanco: el campo sigue siendo obligatorio en el contrato y lo que
    // cambia es su valor, no su presencia.
    if (o.cliente_nombre !== '') renglon.clientes.push(o.cliente_nombre);
    dia.set(clave, renglon);
    porFecha.set(o.fecha_limite, dia);
  }
  return [...porFecha.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([fecha, dia]) => [fecha, [...dia.values()]]);
}

/** Fecha larga en es-MX, para el encabezado del grupo. */
export function fechaLarga(iso: string): string {
  return new Date(`${iso}T00:00:00`).toLocaleDateString('es-MX', {
    weekday: 'long', day: 'numeric', month: 'long', year: 'numeric',
  });
}
