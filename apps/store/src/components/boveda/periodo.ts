/** Periodo de "Verificar estatus" (P1-03): el del filtro o, sin filtro, del día 1 del mes a hoy. */
export function periodoAVerificar(
  desde?: string, hasta?: string, hoy: string = new Date().toISOString().slice(0, 10),
): { desde: string; hasta: string } {
  const fin = hasta || hoy;
  const inicio = desde || `${fin.slice(0, 7)}-01`;
  return { desde: inicio, hasta: fin };
}
