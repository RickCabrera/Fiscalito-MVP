/**
 * Texto en ASCII puro para los archivos del IMSS. (O-04)
 *
 * POR QUÉ TRANSLITERAR, Y POR QUÉ ES UNA DECISIÓN Y NO UN DETALLE TÉCNICO
 * ----------------------------------------------------------------------
 * La *Guía de operación DISP-MAG* del IMSS dice **"Código de grabación ASCII"**
 * y que *"los registros no deberán contener caracteres de control impuestos por
 * paquetería"*. ASCII no puede representar `Ñ` ni las vocales acentuadas, así
 * que hay que decidir qué se hace con "MUÑOZ" y con "PÉREZ".
 *
 * Se transliteran: `Ñ`→`N`, `Á`→`A`. Es lo conservador —un byte alto en un campo
 * que el IMSS lee como ASCII es un archivo rechazado— **pero hay que decir de
 * frente lo que significa**: "MUÑOZ" → "MUNOZ" en un movimiento afiliatorio no
 * es una decisión de codificación, es un cambio de apellido en un documento de
 * identidad laboral.
 *
 * POR ESO ESTA FUNCIÓN REPORTA LO QUE CAMBIÓ
 * -------------------------------------------
 * No basta con hacerlo bien y callarlo. `aAscii` devuelve también si hubo
 * cambio, y la pantalla **lista cada nombre que se transliteró antes de
 * descargar**. Sin eso, la decisión quedaría enterrada en un módulo y el
 * operador entregaría al IMSS apellidos que él nunca escribió.
 *
 * Queda como **decisión abierta** en `docs/decisiones-nomina.md`: ¿el IMSS
 * acepta `Ñ` en este layout? El documento no lo dice y no hay fuente que lo
 * resuelva. Se aplica lo literal, se declara, y se ve exactamente dónde se
 * cambia — la misma doctrina de §D22 y §D25.
 */

/**
 * Equivalencias. Sólo las que aparecen en nombres y apellidos en español, más
 * la diéresis: la lista corta y explícita se lee, una tabla Unicode completa no.
 */
const EQUIVALENCIAS: Record<string, string> = {
  Á: 'A', É: 'E', Í: 'I', Ó: 'O', Ú: 'U', Ü: 'U',
  á: 'a', é: 'e', í: 'i', ó: 'o', ú: 'u', ü: 'u',
  Ñ: 'N', ñ: 'n',
  À: 'A', È: 'E', Ì: 'I', Ò: 'O', Ù: 'U',
  Â: 'A', Ê: 'E', Î: 'I', Ô: 'O', Û: 'U',
  Ç: 'C', ç: 'c',
};

export interface Transliteracion {
  texto: string;
  /** `true` si hubo que cambiar algún carácter. La pantalla lo lista. */
  cambio: boolean;
}

/**
 * Deja el texto en ASCII imprimible (32-126).
 *
 * Lo que no tiene equivalencia conocida se descarta en vez de sustituirse por
 * `?`: un signo de interrogación dentro de un apellido es peor que una letra
 * menos, porque parece un dato y no una pérdida.
 */
export function aAscii(texto: string): Transliteracion {
  let salida = '';
  let cambio = false;

  for (const caracter of texto) {
    const codigo = caracter.charCodeAt(0);
    if (codigo >= 32 && codigo <= 126) {
      salida += caracter;
      continue;
    }
    const equivalente = EQUIVALENCIAS[caracter];
    if (equivalente) {
      salida += equivalente;
    }
    // Sin equivalencia: se descarta.
    cambio = true;
  }

  return { texto: salida, cambio };
}

/**
 * Los bytes del archivo.
 *
 * `TextEncoder` sólo produce UTF-8, así que se codifica a mano: después de
 * `aAscii` todo carácter es < 128, y ahí UTF-8 y ASCII coinciden byte a byte.
 * Se hace explícito para que la garantía sea del código y no de una coincidencia
 * de codificaciones — y hay un test que verifica que **ningún byte pase de
 * 127**.
 */
export function bytesAscii(texto: string): Uint8Array {
  const bytes = new Uint8Array(texto.length);
  for (let i = 0; i < texto.length; i += 1) {
    const codigo = texto.charCodeAt(i);
    if (codigo > 127) {
      throw new Error(
        `Carácter no ASCII en la posición ${i} (código ${codigo}). Todo texto que ` +
          `llegue aquí tiene que haber pasado por \`aAscii\` primero.`,
      );
    }
    bytes[i] = codigo;
  }
  return bytes;
}
