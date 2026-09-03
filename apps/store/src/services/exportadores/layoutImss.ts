/**
 * El layout oficial de movimientos afiliatorios del IMSS. (O-04)
 *
 * FUENTE, VERIFICADA CONTRA EL DOCUMENTO Y NO DE MEMORIA
 * ------------------------------------------------------
 * - **Estructura de Movimientos afiliatorios**, IMSS —
 *   https://www.imss.gob.mx/sites/all/statics/sua/dispmag/EstructuraMovimientosAfiliatorios.pdf
 *   Las tres tablas de campos (alta/reingreso, modificación de salario, baja)
 *   vienen como imágenes dentro del PDF; se extrajeron y se transcribieron
 *   campo por campo.
 * - **Guía de operación DISP-MAG**, IMSS —
 *   http://www.imss.gob.mx/sites/all/statics/pdf/formatos/GuiaOperacionDISP-MAG_2009.pdf
 *   De ahí salen, literales: *"Longitud de los registros **168** fija"*,
 *   *"Código de grabación **ASCII**"*, *"los registros no deberán contener
 *   caracteres de control impuestos por paquetería"*, y la regla del salario:
 *   *"este campo cuenta con **6 posiciones, con 4 para pesos con ceros a la
 *   izquierda y 2 para centavos**"*.
 *
 * DOS DESVIACIONES DEL ENUNCIADO DE O-04, Y GANA LA FUENTE
 * --------------------------------------------------------
 * 1. **Fechas.** El enunciado pide `DD/MM/AAAA`; el layout es `DDMMAAAA`, 8
 *    posiciones sin separadores. Con separadores el registro mide 170 y el
 *    IMSS lo rechaza.
 * 2. **Codificación.** El enunciado dice ANSI; el documento oficial dice
 *    **ASCII**. Se emite CP1252 —superset compatible byte a byte— pero
 *    **transliterando** acentos y `Ñ` a A-Z, de modo que ningún byte pase de
 *    127. Un byte alto en un campo que el IMSS lee como ASCII es un archivo
 *    rechazado. El terminador **CR+LF** sí es el del enunciado.
 *
 * (a) SUA Y (b) IDSE SON EL MISMO LAYOUT
 * ---------------------------------------
 * El documento oficial vive bajo `/statics/sua/dispmag/` y es el que alimenta
 * tanto la presentación por IDSE como la carga al SUA. No se inventa un segundo
 * layout para que sean dos cosas distintas.
 *
 * TRUNCAR ESTÁ PROHIBIDO
 * ----------------------
 * Un valor que no cabe en su campo **levanta**. Truncar un apellido o un NSS en
 * silencio produce un movimiento afiliatorio sobre otra persona, o sobre nadie.
 */

/** Longitud fija de todo registro. Guía de operación, "Aspectos generales". */
export const LARGO_REGISTRO = 168;

export type TipoCampo = 'AN' | 'A' | 'N';

export interface Campo {
  nombre: string;
  tipo: TipoCampo;
  /** 1-indexado, como el documento. */
  desde: number;
  hasta: number;
  /** Con qué se rellena cuando el valor es más corto. */
  relleno: ' ' | '0';
  /** Los numéricos se alinean a la derecha; los alfanuméricos, a la izquierda. */
  alinea: 'izq' | 'der';
}

function campo(
  nombre: string,
  tipo: TipoCampo,
  desde: number,
  hasta: number,
  relleno: ' ' | '0' = ' ',
): Campo {
  return { nombre, tipo, desde, hasta, relleno, alinea: tipo === 'N' ? 'der' : 'izq' };
}

/**
 * Alta o reingreso — tipo de movimiento **08**.
 *
 * Transcrito del documento oficial, incluidos los tres `FILLER`: sin ellos el
 * registro no mide 168 y las posiciones de todo lo que sigue se corren.
 */
export const ALTA: Campo[] = [
  campo('registro_patronal', 'AN', 1, 10),
  campo('digito_rp', 'N', 11, 11, '0'),
  campo('nss', 'N', 12, 21, '0'),
  campo('digito_nss', 'N', 22, 22, '0'),
  campo('apellido_paterno', 'A', 23, 49),
  campo('apellido_materno', 'A', 50, 76),
  campo('nombres', 'A', 77, 103),
  campo('sbc', 'N', 104, 109, '0'),
  campo('filler_110', 'A', 110, 115),
  campo('tipo_trabajador', 'N', 116, 116, '0'),
  campo('tipo_salario', 'N', 117, 117, '0'),
  campo('jornada', 'N', 118, 118, '0'),
  campo('fecha_movimiento', 'N', 119, 126, '0'),
  campo('umf', 'N', 127, 129, '0'),
  campo('filler_130', 'AN', 130, 131),
  campo('tipo_movimiento', 'N', 132, 133, '0'),
  campo('guia', 'N', 134, 138, '0'),
  campo('clave_trabajador', 'AN', 139, 148),
  campo('filler_149', 'AN', 149, 149),
  campo('curp', 'AN', 150, 167),
  campo('identificador', 'N', 168, 168, '0'),
];

/**
 * Modificación de salario — tipo **07**.
 *
 * Difiere del alta en tres puntos, y sólo en tres: la 116 es filler (no lleva
 * tipo de trabajador), no hay UMF —127 a 131 son espacios— y el tipo es 07.
 */
export const MODIFICACION: Campo[] = [
  ...ALTA.slice(0, ALTA.findIndex((c) => c.nombre === 'tipo_trabajador')),
  campo('filler_116', 'N', 116, 116),
  campo('tipo_salario', 'N', 117, 117, '0'),
  campo('jornada', 'N', 118, 118, '0'),
  campo('fecha_movimiento', 'N', 119, 126, '0'),
  campo('filler_127', 'AN', 127, 131),
  campo('tipo_movimiento', 'N', 132, 133, '0'),
  campo('guia', 'N', 134, 138, '0'),
  campo('clave_trabajador', 'AN', 139, 148),
  campo('filler_149', 'AN', 149, 149),
  campo('curp', 'AN', 150, 167),
  campo('identificador', 'N', 168, 168, '0'),
];

/**
 * Baja — tipo **02**.
 *
 * Dos diferencias que no se pueden pasar por alto:
 * - **104 a 118 van en CEROS**, no en espacios. El documento lo dice explícito.
 * - **150 a 167 son espacios, no CURP**: una baja no lleva CURP.
 */
export const BAJA: Campo[] = [
  ...ALTA.slice(0, ALTA.findIndex((c) => c.nombre === 'sbc')),
  campo('filler_104', 'AN', 104, 118, '0'),
  campo('fecha_movimiento', 'N', 119, 126, '0'),
  campo('filler_127', 'AN', 127, 131),
  campo('tipo_movimiento', 'N', 132, 133, '0'),
  campo('guia', 'N', 134, 138, '0'),
  campo('clave_trabajador', 'AN', 139, 148),
  campo('causa_baja', 'N', 149, 149, '0'),
  campo('filler_150', 'AN', 150, 167),
  campo('identificador', 'N', 168, 168, '0'),
];

/**
 * Cifras de control — un registro por lote, del mismo largo.
 *
 * *"El proceso de cómputo requiere de dos formatos, el primero corresponde a la
 * totalidad de registros... el segundo es el de cifras de control"*. Sin él, el
 * lote está incompleto.
 */
export const CIFRAS_CONTROL: Campo[] = [
  campo('asteriscos', 'AN', 1, 13),
  campo('filler_14', 'AN', 14, 56),
  campo('total_registros', 'N', 57, 62, '0'),
  campo('filler_63', 'AN', 63, 133),
  campo('guia', 'N', 134, 138, '0'),
  campo('filler_139', 'AN', 139, 167),
  campo('identificador', 'N', 168, 168, '0'),
];

export const TIPO_ALTA_REINGRESO = '08';
export const TIPO_MODIFICACION = '07';
export const TIPO_BAJA = '02';
/** "Dígito nueve (9)" en la posición 168 de todo registro. */
export const IDENTIFICADOR_FORMATO = '9';
