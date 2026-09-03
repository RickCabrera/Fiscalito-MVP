/**
 * Dinero en CENTAVOS ENTEROS. (O-04)
 *
 * POR QUÉ NO `Number()`
 * ---------------------
 * Los importes viajan del backend como cadenas decimales (`"5056.00"`) porque
 * allá son `Decimal`. Convertirlos a `number` para sumarlos mete error de punto
 * flotante en una columna que después se compara **al centavo** contra el PDF y
 * contra el motor: `0.1 + 0.2 !== 0.3` no es una curiosidad académica cuando el
 * criterio de la tarea es "totales idénticos".
 *
 * El PDF hoy hace `Number(r.importe)` para imprimir, y eso se queda: imprimir un
 * float redondeado a dos decimales es correcto. Lo que no puede hacerse en
 * float es **sumar** — y eso es lo que hace el cuadre.
 *
 * PARSEA LA CADENA, NO LA REDONDEA
 * --------------------------------
 * `aCentavos('5056.005')` **levanta**. No se inventa un redondeo aquí: el motor
 * ya redondea por concepto y por empleado a dos decimales, al estilo SUA
 * (`docs/decisiones-nomina.md` §D1), así que un tercer decimal significa que
 * algo aguas arriba cambió — y taparlo con un `Math.round` escondería
 * exactamente eso.
 */

/** Convierte `"5056.00"` a `505600`. Levanta si no es un decimal de 2 dígitos. */
export function aCentavos(importe: string): number {
  const limpio = importe.trim();
  const m = /^(-?)(\d+)(?:\.(\d{1,2}))?$/.exec(limpio);
  if (!m) {
    throw new Error(
      `Importe con una forma que no se puede convertir a centavos sin redondear: ` +
        `${JSON.stringify(importe)}. El motor redondea por concepto a 2 decimales ` +
        `(§D1); un tercer decimal significa que algo cambió aguas arriba.`,
    );
  }
  const [, signo, enteros, decimales = ''] = m;
  const centavos = Number(enteros) * 100 + Number(decimales.padEnd(2, '0'));
  return signo === '-' ? -centavos : centavos;
}

/** El camino de vuelta, para poder comparar y para imprimir. */
export function deCentavos(centavos: number): string {
  const signo = centavos < 0 ? '-' : '';
  const abs = Math.abs(centavos);
  return `${signo}${Math.floor(abs / 100)}.${String(abs % 100).padStart(2, '0')}`;
}

export function sumaCentavos(importes: string[]): number {
  return importes.reduce((acc, i) => acc + aCentavos(i), 0);
}
