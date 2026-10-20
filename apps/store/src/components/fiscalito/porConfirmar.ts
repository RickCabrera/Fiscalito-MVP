/**
 * O12: las fuentes por confirmar de una respuesta del motor (INPC sin cotejar,
 * tasa de recargos o de ISN de fuente secundaria), sea cual sea su forma.
 */

export function fuentesPorConfirmar(r: Record<string, unknown> | null | undefined): string[] {
  if (!r || r.por_confirmar !== true) return [];
  if (Array.isArray(r.fuentes_por_confirmar) && r.fuentes_por_confirmar.length > 0) {
    return r.fuentes_por_confirmar.map(String);
  }
  return [typeof r.fundamento === 'string' && r.fundamento ? r.fundamento : 'Fuente secundaria'];
}

