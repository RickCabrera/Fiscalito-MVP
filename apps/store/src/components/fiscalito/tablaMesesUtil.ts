/** Utilidades compartidas de las tablas mes a mes (P3-01, P3-06). */

const MESES = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto',
  'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'];

export interface ColumnaMes {
  campo: string;
  titulo: string;
}

export const CELDA: React.CSSProperties = {
  padding: '6px 8px', borderBottom: '1px solid var(--border)', textAlign: 'right',
  fontFamily: 'JetBrains Mono, monospace', fontSize: '0.8rem', whiteSpace: 'nowrap',
};

export function nombreMes(mes: number): string {
  return MESES[mes - 1] ?? String(mes);
}
