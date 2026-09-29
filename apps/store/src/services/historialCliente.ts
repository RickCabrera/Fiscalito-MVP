/**
 * El historial de declaraciones, asociado al cliente con el que se calculó (C-02).
 *
 * Hasta C-02 todo vivía en `users/{uid}/declaraciones/{categoria_periodo}`: un
 * sujeto por cuenta. Con un despacho eso deja de ser cierto y rompe dos cosas:
 * el "Enero 2026" del cliente B **pisaba** el del cliente A (mismo id), y el
 * acumulado del Art. 106 de la pre-declaración **sumaba meses de clientes
 * distintos**.
 *
 * El cambio es ADITIVO: un cálculo de cliente guarda `cliente_id` y un id con
 * prefijo propio; uno de contribuyente se guarda **exactamente igual que antes**.
 * Puro a propósito (sin Firestore): se prueba sin dobles.
 */

/** Id base del documento: `categoria_periodo`, normalizado. El de siempre. */
export function generarDocId(categoria: string, periodo: string): string {
  const raw = `${categoria}_${periodo}`;
  return raw
    .toLowerCase()
    .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9_]/g, '_')
    .replace(/_+/g, '_')
    .replace(/^_|_$/g, '');
}

/**
 * El id del cliente, apto para ir dentro del id de un documento **sin perder
 * distinciones**. `generarDocId` pasa todo a minúsculas y colapsa símbolos, y
 * con eso `Taller-1` y `taller_1` compartirían documento. Aquí se conservan
 * letras (con su caja), dígitos y `-`; todo lo demás —el `_` incluido, que es el
 * separador— se escribe como `_<código hex>_`, así que es reversible.
 */
export function codificarClienteId(id: string): string {
  return Array.from(id, (ch) =>
    /[A-Za-z0-9-]/.test(ch) ? ch : `_${ch.codePointAt(0)!.toString(16)}_`,
  ).join('');
}

/** Sin cliente, el id de siempre. Con cliente, prefijado con el suyo. */
export function docIdHistorial(categoria: string, periodo: string, clienteId?: string | null): string {
  const base = generarDocId(categoria, periodo);
  return clienteId ? `c_${codificarClienteId(clienteId)}__${base}` : base;
}

/** Lo que se agrega al documento. Nada para el contribuyente. */
export function camposDeCliente(clienteId?: string | null): { cliente_id?: string } {
  return clienteId ? { cliente_id: clienteId } : {};
}

/**
 * Si un documento pertenece al ámbito que se está mirando. Con cliente: sólo
 * los suyos. Sin cliente: sólo los que no son de ningún cliente — el
 * contribuyente nunca ve un cálculo hecho para un cliente de despacho.
 */
export function delAmbito(data: { cliente_id?: unknown }, clienteId?: string | null): boolean {
  return clienteId ? data.cliente_id === clienteId : !data.cliente_id;
}

/** Milisegundos de un `fecha_calculo` (Timestamp de Firestore, Date o nada). */
export function milisDe(fecha: unknown): number {
  if (fecha && typeof (fecha as { toMillis?: unknown }).toMillis === 'function') {
    return (fecha as { toMillis: () => number }).toMillis();
  }
  if (fecha instanceof Date) return fecha.getTime();
  return 0;
}
