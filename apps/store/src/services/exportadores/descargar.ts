/**
 * Bajar bytes al disco del usuario, y nada más. (T5)
 *
 * Salió de `SelectorExportacion.tsx` cuando la DIOT necesitó exactamente lo
 * mismo (T5). Vive aquí y no en un `.tsx` porque no pinta nada: es la frontera
 * entre un `Uint8Array` y el navegador.
 *
 * EL CONTENIDO NO SE REGISTRA EN NINGÚN LADO
 * -------------------------------------------
 * Estos archivos llevan NSS, salarios y RFC de terceros. **No se loguean, no se
 * mandan a ninguna parte y no se guardan**: se arman en memoria, se descargan y
 * se libera la URL.
 */

export function descargarBytes(nombre: string, bytes: Uint8Array): void {
  // `text/plain` y no un tipo inventado: es lo que es, y así el navegador no
  // intenta abrirlo en una pestaña.
  // El `slice()` copia a un `ArrayBuffer` propio: `Uint8Array<ArrayBufferLike>`
  // no es un `BlobPart` válido porque podría respaldarse en un
  // `SharedArrayBuffer`, que `Blob` no acepta.
  const url = URL.createObjectURL(
    new Blob([bytes.slice().buffer as ArrayBuffer], { type: 'text/plain' }),
  );
  const a = document.createElement('a');
  a.href = url;
  a.download = nombre;
  a.click();
  URL.revokeObjectURL(url);
}
