/**
 * El contrato de un formato de exportación, y su punto de extensión. (O-04)
 *
 * CÓMO SE AGREGA UN FORMATO NUEVO
 * -------------------------------
 * 1. Un archivo con una función que reciba `DatosExportacion` y devuelva
 *    `ArchivoGenerado`.
 * 2. Un renglón en `FORMATOS` (`registro.ts`).
 *
 * Eso es todo. El selector del paso 4 se pinta desde `FORMATOS`, así que no hay
 * una tercera lista que actualizar — que es donde siempre se olvida uno.
 *
 * TODO FORMATO DECLARA SU FUENTE, Y ESO NO ES OPCIONAL
 * ----------------------------------------------------
 * `fuente.estado` sólo tiene dos valores y los dos obligan a decir algo:
 *
 * - `'oficial'` exige una **cita**: el documento del que salió el layout.
 * - `'por-validar'` significa que el layout **no se pudo verificar contra una
 *   fuente publicada**. La UI lo pinta, el archivo lo lleva en su nombre, y el
 *   `nocturno-log` no lo cuenta como verificado.
 *
 * No hay un tercer estado tipo "probablemente bien". Un archivo que se le
 * entrega al IMSS o a un banco, o está respaldado por su manual o el operador
 * tiene que saber que no lo está.
 */

import type { ClienteDetalle } from '../despachoApi';
import type { EmpleadoCartera } from '../carteraApi';
import type { NominaPeriodo } from '../nominaDemoApi';

export interface DatosExportacion {
  /** Lo que devolvió `POST /nomina/calcular-periodo`, sin tocar. */
  nomina: NominaPeriodo;
  /** La ficha del patrón: razón social, RFC, registro patronal. */
  cliente: ClienteDetalle;
  /**
   * La plantilla de la cartera.
   *
   * Hace falta porque el recibo **no trae NSS, CURP ni apellidos por separado**:
   * `ReciboNomina` tiene `empleado_no` y `nombre`, y el layout del IMSS pide los
   * tres apellidos en campos distintos. Se cruzan por `empleado_no`.
   */
  empleados: EmpleadoCartera[];
  /** Registro patronal del patrón, 11 caracteres (10 + verificador). */
  registroPatronal: string;
  /** Número de guía asignado por la subdelegación. Dato del operador. */
  guia: string;
}

/** Un empleado que NO se pudo exportar, y por qué. */
export interface NoExportable {
  empleadoNo: string;
  nombre: string;
  motivo: string;
}

export interface ArchivoGenerado {
  nombre: string;
  bytes: Uint8Array;
  /**
   * Quién quedó fuera y por qué.
   *
   * **Va aquí y NO dentro del archivo.** Un layout de longitud fija no admite un
   * pie en prosa —rompería las 168 posiciones y el IMSS lo rechazaría— y además
   * escribiría nombres de personas dentro del documento que se presenta. La
   * pantalla los muestra; el archivo sólo lleva lo que le toca.
   */
  noExportables: NoExportable[];
  /**
   * Nombres que se transliteraron a ASCII (`MUÑOZ` → `MUNOZ`).
   *
   * La pantalla los lista **antes de descargar**. Cambiar una letra de un
   * apellido en un movimiento afiliatorio no es una decisión de codificación, y
   * no puede quedar enterrada en un módulo.
   */
  transliterados: string[];
}

export interface FormatoExportacion {
  id: string;
  nombre: string;
  /** Una línea de qué es y para quién. Se pinta en el selector. */
  descripcion: string;
  fuente:
    | { estado: 'oficial'; cita: string }
    | { estado: 'por-validar'; cita: string };
  /**
   * Por qué este formato todavía no se puede emitir. (T8)
   *
   * Presente = el selector lo pinta **deshabilitado**, con la marca
   * "Próximamente" y este texto como tooltip. `generar` existe igual —el tipo
   * lo exige— pero LEVANTA: es la única forma honesta de decir "esto no emite
   * nada" sin devolver un archivo vacío que alguien mandaría al IMSS.
   *
   * POR QUÉ ESTÁN EN LA LISTA SI NO FUNCIONAN
   * -----------------------------------------
   * Porque la pregunta que el operador trae es "¿y las bajas?", y una lista
   * donde sólo existen las altas la contesta con silencio: parece que el
   * formato no existe, no que falta el dato. Los tres layouts —alta,
   * modificación y baja— están **transcritos** desde la fuente oficial en
   * `layoutImss.ts`; lo que falta es que el modelo guarde fecha de baja e
   * historial de SBC.
   *
   * Transcritos, **no probados**: sólo el de alta está cableado y medido. Ver
   * `registro.ts`, que lo explica entero.
   */
  proximamente?: string;
  generar(datos: DatosExportacion): ArchivoGenerado;
}
