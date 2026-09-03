/**
 * Escribir un registro de posiciones fijas. (O-04)
 *
 * TRUNCAR ESTÁ PROHIBIDO, Y ES LA REGLA MÁS IMPORTANTE DE ESTE ARCHIVO
 * --------------------------------------------------------------------
 * Un valor que no cabe en su campo **levanta**. Cortar un apellido produce un
 * movimiento afiliatorio sobre alguien que no es; cortar un NSS, sobre nadie. Y
 * las dos cosas pasan en silencio: el archivo mide 168 posiciones igual y el
 * IMSS lo acepta.
 *
 * Es la misma disciplina que el resto del repo aplica a los datos que no se
 * conocen —`None` y nunca inventado— llevada al que sí se conoce pero no cabe.
 *
 * LAS ANCHURAS SE VERIFICAN, NO SE CONFÍAN
 * ----------------------------------------
 * `escribirRegistro` comprueba que los campos cubran 1..168 **sin huecos ni
 * traslapes** antes de escribir nada. Con 21 campos transcritos a mano de un
 * PDF, un `hasta` mal tecleado corre todo lo que sigue y el archivo entero sale
 * mal sin que nada avise.
 */

import { aAscii, type Transliteracion } from './ascii';
import { LARGO_REGISTRO, type Campo } from './layoutImss';

/** Qué se transliteró al escribir, para que la pantalla pueda decirlo. */
export interface ResultadoRegistro {
  linea: string;
  /** Campos cuyo texto cambió al pasarlo a ASCII. */
  transliterados: string[];
}

/**
 * Comprueba que el layout cubra el registro completo.
 *
 * Se corre en cada escritura y no una sola vez al cargar: es barato, y un
 * layout roto tiene que fallar donde se usa y no en un módulo que quizá nadie
 * importó.
 */
export function verificarLayout(campos: Campo[], largo = LARGO_REGISTRO): void {
  let esperado = 1;
  for (const c of campos) {
    if (c.desde !== esperado) {
      throw new Error(
        `El layout tiene un ${c.desde > esperado ? 'hueco' : 'traslape'} antes de ` +
          `"${c.nombre}": se esperaba la posición ${esperado} y empieza en ${c.desde}.`,
      );
    }
    if (c.hasta < c.desde) {
      throw new Error(`El campo "${c.nombre}" termina antes de empezar.`);
    }
    esperado = c.hasta + 1;
  }
  if (esperado - 1 !== largo) {
    throw new Error(
      `El layout cubre ${esperado - 1} posiciones y el registro son ${largo}.`,
    );
  }
}

function rellenar(campo: Campo, valor: string): string {
  const ancho = campo.hasta - campo.desde + 1;
  if (valor.length > ancho) {
    throw new Error(
      `"${valor}" no cabe en el campo "${campo.nombre}" (${ancho} posiciones). ` +
        `Truncarlo produciría un movimiento afiliatorio sobre otra persona, así que ` +
        `se rechaza: corrige el dato o el layout.`,
    );
  }
  return campo.alinea === 'der'
    ? valor.padStart(ancho, campo.relleno)
    : valor.padEnd(ancho, campo.relleno);
}

/**
 * Arma la línea de 168 posiciones.
 *
 * Un campo que no venga en `valores` se rellena entero — es lo que hace que los
 * `FILLER` del layout no haya que enumerarlos en cada llamada.
 */
export function escribirRegistro(
  campos: Campo[],
  valores: Record<string, string>,
  largo = LARGO_REGISTRO,
): ResultadoRegistro {
  verificarLayout(campos, largo);

  const transliterados: string[] = [];
  let linea = '';

  for (const campo of campos) {
    const crudo = valores[campo.nombre] ?? '';
    let texto = crudo;
    if (crudo !== '') {
      const ascii: Transliteracion = aAscii(crudo);
      texto = ascii.texto;
      if (ascii.cambio) transliterados.push(campo.nombre);
    }
    linea += rellenar(campo, texto);
  }

  if (linea.length !== largo) {
    // Inalcanzable con el layout verificado, y aun así se comprueba: un archivo
    // de longitud fija que mida distinto lo rechaza el IMSS entero, no el
    // renglón.
    throw new Error(`El registro mide ${linea.length} y debería medir ${largo}.`);
  }
  return { linea, transliterados };
}

/** Fecha `DDMMAAAA`, como la pide el layout. Nunca con separadores. */
export function fechaDDMMAAAA(iso: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  if (!m) throw new Error(`Fecha que no es ISO (AAAA-MM-DD): ${JSON.stringify(iso)}.`);
  const [, anio, mes, dia] = m;
  return `${dia}${mes}${anio}`;
}

/**
 * SBC en 6 posiciones: **4 para pesos con ceros a la izquierda y 2 para
 * centavos**, punto decimal implícito.
 *
 * Literal de la *Guía de operación DISP-MAG* del IMSS. `$526.05` → `052605`.
 *
 * El tope de 4 enteros da $9,999.99, muy por encima del tope legal del SBC (25
 * UMA ≈ $2,932.75), así que en la práctica no se alcanza — pero si se
 * alcanzara, **levanta**: un SBC truncado es una cuota mal calculada en el
 * documento que se le entrega al IMSS.
 */
export function sbcSeisPosiciones(importeEnCentavos: number): string {
  if (importeEnCentavos < 0) {
    throw new Error(`El SBC no puede ser negativo: ${importeEnCentavos} centavos.`);
  }
  if (importeEnCentavos > 999999) {
    throw new Error(
      `El SBC de ${importeEnCentavos} centavos no cabe en las 6 posiciones del layout ` +
        `(máximo $9,999.99). Truncarlo declararía un salario distinto al real.`,
    );
  }
  return String(importeEnCentavos).padStart(6, '0');
}
