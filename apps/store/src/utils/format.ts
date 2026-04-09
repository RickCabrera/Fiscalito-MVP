/** Shared formatting utilities */

export function fmtMoney(n: number): string {
  return n.toLocaleString('es-MX', { style: 'currency', currency: 'MXN' });
}

/** Alias for backwards compatibility */
export const formatMoney = fmtMoney;
