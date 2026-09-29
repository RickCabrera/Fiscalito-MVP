/**
 * Qué archivos entran a un uploader de CFDI y cuáles se rechazan (C-03).
 *
 * Antes de C-03 cada uploader filtraba con `f.name.endsWith('.xml')`, que
 * distingue mayúsculas: un `FACTURA.XML` se tiraba sin avisar, y ni siquiera
 * contaba entre los excluidos. Aquí la extensión se compara sin mayúsculas, y lo que no es XML sale
 * con su nombre en `rechazados` para que el uploader lo muestre, no lo calle.
 */

export interface ArchivoRechazado {
  fileName: string;
  error: string;
}

export const MOTIVO_NO_XML = 'No es un archivo XML; no se cargó.';

/**
 * Para el `accept` de los `<input type="file">`. El estándar de HTML ya compara
 * extensiones sin mayúsculas; `.XML` va explícito por si algún navegador no lo
 * hace. Ojo: `accept` sólo filtra el diálogo —no el drag & drop ni "Todos los
 * archivos"—, así que lo que de verdad protege es `separarXml`.
 */
export const ACCEPT_XML = '.xml,.XML,text/xml,application/xml';

export function esNombreXml(nombre: string): boolean {
  return /\.xml$/i.test(nombre);
}

export function separarXml(files: FileList | File[]): { xml: File[]; rechazados: ArchivoRechazado[] } {
  const xml: File[] = [];
  const rechazados: ArchivoRechazado[] = [];
  for (const f of Array.from(files)) {
    if (esNombreXml(f.name)) xml.push(f);
    else rechazados.push({ fileName: f.name, error: MOTIVO_NO_XML });
  }
  return { xml, rechazados };
}
