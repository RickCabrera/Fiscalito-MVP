/**
 * Formato genérico, delimitado por barras. (O-04)
 *
 * **Todos los conceptos del recibo, por empleado**: percepciones, deducciones,
 * ISR, cuota obrera y cuota patronal. Es el que se abre en Excel, el que se le
 * manda al contador externo y el que sirve para cuadrar contra cualquier otro
 * sistema.
 *
 * POR QUÉ PIPE Y NO COMA
 * ----------------------
 * Los nombres llevan comas ("SANTA CRUZ RIVERA, MARIA") y los importes en
 * español llevan coma de millares. Un CSV con comas obliga a entrecomillar y a
 * escapar, y el primer nombre con comilla rompe el archivo en silencio. La barra
 * no aparece en un nombre ni en un importe.
 *
 * LOS IMPORTES VAN EN PUNTO DECIMAL, SIN SEPARADOR DE MILLARES
 * ------------------------------------------------------------
 * Es lo que cualquier hoja de cálculo lee sin configurar nada, y es la forma en
 * que el motor los emite: se copian **tal cual llegan**, sin pasar por
 * `Number()`. Formatearlos aquí sería re-decidir un redondeo que el motor ya
 * hizo por concepto y por empleado (§D1).
 */

import { bytesAscii, aAscii } from './ascii';
import { deCentavos, sumaCentavos } from './dinero';
import type { ArchivoGenerado, DatosExportacion } from './tipos';

const CRLF = '\r\n';
const SEP = '|';

const ENCABEZADOS = [
  'empleado_no',
  'nombre',
  'nss',
  'sbc',
  'dias_pagados',
  'total_percepciones',
  'total_deducciones',
  'isr_retenido',
  'cuota_obrera',
  'cuota_patronal',
  'neto',
];

/** El ISR es la deducción con clave `002` de `c_TipoDeduccion`. */
function isrDelRecibo(deducciones: { tipo: string; importe: string }[]): string {
  const partida = deducciones.find((d) => d.tipo === '002');
  return partida ? partida.importe : '0.00';
}

export function generarGenerico(datos: DatosExportacion): ArchivoGenerado {
  const { nomina, empleados } = datos;
  const porNumero = new Map(empleados.map((e) => [e.empleado_no, e]));
  const transliterados: string[] = [];

  const filas = [ENCABEZADOS.join(SEP)];

  for (const recibo of nomina.recibos) {
    const nombre = aAscii(recibo.nombre);
    if (nombre.cambio) transliterados.push(`${recibo.nombre} (nombre)`);

    filas.push(
      [
        recibo.empleado_no,
        nombre.texto,
        porNumero.get(recibo.empleado_no)?.nss ?? '',
        recibo.sbc,
        String(recibo.dias_pagados),
        recibo.total_percepciones,
        recibo.total_deducciones,
        isrDelRecibo(recibo.deducciones),
        recibo.cuota_obrera,
        recibo.cuota_patronal,
        recibo.neto,
      ].join(SEP),
    );
  }

  /**
   * Renglón de totales, marcado.
   *
   * Va con la etiqueta `TOTAL` en la primera columna y no como un renglón más:
   * quien abra esto en Excel y sume la columna no puede acabar contando los
   * totales dos veces.
   *
   * **Los importes son los del MOTOR** (`total_percepciones`, `total_neto`,
   * `total_isr` de la respuesta), no una suma hecha aquí. Es lo que permite que
   * el cuadre compare contra el backend en vez de contra sí mismo.
   *
   * LAS CUOTAS SON LA EXCEPCIÓN, Y VAN SUMADAS DE LAS DOS PORCIONES
   * ---------------------------------------------------------------
   * `total_obrero` y `total_patron` no viajan sueltos en la respuesta: viajan
   * partidos en `porcion_mensual` (EyM, RT, guardería) y `porcion_bimestral`
   * (Retiro, CEAV, Infonavit), porque se enteran en fechas distintas. El motor
   * define el total como **la suma de las dos** (`periodo_tipos.py`), y la
   * columna por empleado —`recibo.cuota_obrera`— ya trae las dos.
   *
   * Tomar sólo la mensual dejaba el renglón TOTAL por debajo de la suma de su
   * propia columna: en un periodo con Infonavit (5% del SBC), Retiro (2%) y
   * CEAV, el faltante es grande y silencioso. Lo cazó el revisor del cuadre.
   */
  const cuotaObrera = deCentavos(
    sumaCentavos([nomina.porcion_mensual.total_obrero, nomina.porcion_bimestral.total_obrero]),
  );
  const cuotaPatronal = deCentavos(
    sumaCentavos([nomina.porcion_mensual.total_patron, nomina.porcion_bimestral.total_patron]),
  );
  filas.push(
    [
      'TOTAL',
      `${nomina.recibos.length} empleados`,
      '',
      '',
      '',
      nomina.total_percepciones,
      '',
      nomina.total_isr,
      cuotaObrera,
      cuotaPatronal,
      nomina.total_neto,
    ].join(SEP),
  );

  const texto = filas.join(CRLF) + CRLF;
  return {
    nombre: `Nomina_${nomina.periodo.inicio}_${nomina.periodo.fin}.txt`,
    bytes: bytesAscii(texto),
    // Todos los del cálculo salen: este formato no exige NSS ni apellidos.
    noExportables: [],
    transliterados,
  };
}
