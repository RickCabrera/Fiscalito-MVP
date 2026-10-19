/**
 * Utilidades de las pantallas de contabilidad (P2). Puras: sin red ni estado.
 *
 * Los importes llegan del backend como texto con dos decimales ("1160.00") y así
 * se mandan de vuelta. `Number()` sólo se usa para PINTAR; ninguna suma que
 * importe se hace en el navegador (el cuadre lo decide el backend).
 */

import { fmtMoney } from '../../utils/format';
import type { Cuenta } from '../../services/contabilidadApi';

/** Primer y último día del mes de `fecha` (AAAA-MM-DD). */
export function mesDe(fecha: string = new Date().toISOString().slice(0, 10)): { desde: string; hasta: string } {
  const [a, m] = fecha.slice(0, 7).split('-').map(Number);
  const ultimo = new Date(Date.UTC(a, m, 0)).getUTCDate();
  const mm = String(m).padStart(2, '0');
  return { desde: `${a}-${mm}-01`, hasta: `${a}-${mm}-${String(ultimo).padStart(2, '0')}` };
}

/** Importe para pintar; "0.00" se pinta como guion para que la tabla respire. */
export function dinero(valor: string | undefined, cero = '—'): string {
  const n = Number(valor ?? 0);
  return n === 0 ? cero : fmtMoney(n);
}

/** Mensaje de un error desconocido. */
export function mensaje(e: unknown, defecto: string): string {
  return e instanceof Error ? e.message : defecto;
}

/** Texto de importe a dos decimales, o '' si no es un número válido. */
export function aCentavos(texto: string): string {
  const limpio = texto.replace(/[,$\s]/g, '');
  if (limpio === '') return '';
  const n = Number(limpio);
  return Number.isFinite(n) && n >= 0 ? n.toFixed(2) : '';
}

/** Suma exacta en centavos (enteros) de importes de texto. */
export function sumaCentavos(valores: string[]): number {
  return valores.reduce((s, v) => s + Math.round(Number(v || 0) * 100), 0);
}

export const ETIQUETA_TIPO_POLIZA: Record<string, string> = {
  ingreso: 'Ingreso', egreso: 'Egreso', diario: 'Diario',
};

export const ETIQUETA_TIPO_CUENTA: Record<string, string> = {
  activo: 'Activo', pasivo: 'Pasivo', capital: 'Capital', ingreso: 'Ingresos',
  costo: 'Costos', gasto: 'Gastos', orden: 'Orden',
};

/** Descarga un Blob con nombre (XML de la bóveda). */
export function descargarBlob(nombre: string, blob: Blob): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = nombre;
  a.click();
  URL.revokeObjectURL(url);
}

/** Ordena el catálogo en profundidad: cada cuenta seguida de sus subcuentas. */
export function enArbol(cuentas: Cuenta[]): Cuenta[] {
  const hijos = new Map<number | null, Cuenta[]>();
  for (const c of cuentas) hijos.set(c.padre_id, [...(hijos.get(c.padre_id) ?? []), c]);
  const salida: Cuenta[] = [];
  const visitar = (padre: number | null) => {
    for (const c of (hijos.get(padre) ?? []).sort((a, b) => a.numero.localeCompare(b.numero))) {
      salida.push(c);
      visitar(c.id);
    }
  };
  visitar(null);
  return salida;
}
