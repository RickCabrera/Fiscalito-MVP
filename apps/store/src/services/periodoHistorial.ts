/**
 * Lectura de los periodos del historial ("Enero 2026", "Bimestre 1 2026").
 *
 * Salió de `declaracionesHistory.ts` sin cambios en C-02, para que ese archivo
 * —ya muy por encima del tope de 300 líneas— no creciera con el ámbito por
 * cliente.
 */

export const MESES: Record<string, number> = {
  enero: 1, febrero: 2, marzo: 3, abril: 4, mayo: 5, junio: 6,
  julio: 7, agosto: 8, septiembre: 9, octubre: 10, noviembre: 11, diciembre: 12,
};

export function parsearPeriodo(periodo: string): { month: number; year: number } | null {
  const parts = periodo.toLowerCase().trim().split(/\s+/);
  if (parts.length < 2) return null;
  // "Bimestre 1 2026" → último mes del bimestre
  if (parts[0] === 'bimestre') {
    const bim = parseInt(parts[1]);
    const year = parseInt(parts[2]);
    if (!bim || isNaN(year)) return null;
    return { month: bim * 2, year };
  }
  // "Enero 2026"
  const month = MESES[parts[0]];
  const year = parseInt(parts[parts.length - 1]);
  if (!month || isNaN(year)) return null;
  return { month, year };
}
