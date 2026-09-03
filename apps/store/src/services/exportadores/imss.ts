/**
 * Movimientos afiliatorios del IMSS — el archivo de IDSE/SUA. (O-04)
 *
 * QUÉ EMITE, Y QUÉ NO EMITE AUNQUE EL ENUNCIADO LO PIDIERA
 * --------------------------------------------------------
 * Emite **altas/reingresos (08)**: los empleados cuya `fecha_alta` cae DENTRO
 * del periodo exportado, más el registro de **cifras de control** que el
 * documento oficial exige por lote.
 *
 * **No emite bajas (02) ni modificaciones de salario (07)**, y no es un recorte:
 * el modelo no guarda fecha de baja, causa de baja ni historial de SBC, así que
 * no hay forma de saber quién causó baja ni a quién le cambió el salario. Los
 * tres layouts están transcritos y probados en `layoutImss.ts`; lo que falta son
 * los datos. Queda ABIERTO en `docs/nocturno-log.md`.
 *
 * EL ENUNCIADO PEDÍA DOS FORMATOS, (a) SUA Y (b) IDSE, Y SON EL MISMO
 * -------------------------------------------------------------------
 * El documento oficial vive bajo `imss.gob.mx/sites/all/statics/sua/dispmag/` y
 * es el que alimenta tanto la presentación por IDSE como la carga al SUA. No se
 * inventa un segundo layout para que sean dos cosas distintas.
 *
 * Y **no se emite "un alta por cada empleado activo"** como carga inicial al
 * SUA, que era la otra forma de hacerlos dos: un registro 08 es *un alta con su
 * fecha*. Emitir uno por cada empleado activo declara que **toda la plantilla
 * ingresó ese día**, y si ese archivo entra por IDSE reafilia a todo el mundo.
 * Lo señaló el revisor del plan y tiene razón: es inventar un uso para llenar
 * un enunciado.
 *
 * QUIÉN QUEDA FUERA, Y POR QUÉ SE DICE
 * ------------------------------------
 * Un empleado sin NSS, sin apellidos capturados por separado o sin fecha de
 * alta **no se exporta**, y sale en `noExportables` con su razón. Partir un
 * nombre completo a la adivina produce un movimiento afiliatorio con el
 * apellido equivocado — es la misma política que `sin_vincular` de G-02: quedar
 * fuera en silencio es el modo de falla que este repo lleva cinco épicas
 * evitando.
 */

import { aCentavos } from './dinero';
import { bytesAscii } from './ascii';
import {
  ALTA,
  CIFRAS_CONTROL,
  IDENTIFICADOR_FORMATO,
  TIPO_ALTA_REINGRESO,
} from './layoutImss';
import {
  escribirRegistro,
  fechaDDMMAAAA,
  sbcSeisPosiciones,
} from './registroFijo';
import type {
  ArchivoGenerado,
  DatosExportacion,
  NoExportable,
} from './tipos';

/** Terminador de línea, como pide el enunciado de O-04. */
const CRLF = '\r\n';

/**
 * Valores fijos del alta, con su fundamento.
 *
 * **Son defaults declarados, no datos.** El modelo no registra ninguno de los
 * tres, y para esta empresa los tres tienen una respuesta clara: personal de
 * planta, salario fijo, jornada normal. El día que haya un eventual o un
 * salario variable, esto tiene que volverse dato — y por eso está escrito aquí
 * y no disperso en la construcción del registro.
 */
const TIPO_TRABAJADOR_PERMANENTE = '1';
const TIPO_SALARIO_FIJO = '0';
const JORNADA_NORMAL = '0';

function dentroDelPeriodo(fecha: string, inicio: string, fin: string): boolean {
  return fecha >= inicio && fecha <= fin;
}

/** Lo que le falta a un empleado para poder emitir su movimiento. */
function faltantes(e: {
  nss: string;
  apellido_paterno?: string;
  nombres?: string;
  fecha_alta: string | null;
}): string[] {
  const falta: string[] = [];
  // 11 dígitos exactos, no "algo en el campo". El backend ya lo valida
  // (`empleado.py::_nss_bien_formado`), pero abajo el NSS se parte en 10 + su
  // dígito verificador con `slice`, y `slice` recorta en silencio: es el único
  // punto del módulo donde un dato se acortaría sin que `rellenar` levantara.
  // Un NSS de 10 dígitos declara el movimiento sobre **otra persona**.
  if (!/^\d{11}$/.test(e.nss)) falta.push('el NSS completo (11 dígitos)');
  if (!e.apellido_paterno?.trim()) falta.push('el apellido paterno');
  if (!e.nombres?.trim()) falta.push('el nombre de pila');
  if (!e.fecha_alta) falta.push('la fecha de alta');
  return falta;
}

export function generarMovimientosImss(datos: DatosExportacion): ArchivoGenerado {
  const { nomina, empleados, registroPatronal, guia } = datos;
  const { inicio, fin } = nomina.periodo;

  /**
   * Sin registro patronal o sin guía **no se emite nada**.
   *
   * Los dos van en cada renglón —01-11 y 134-138— y los dos los asigna el IMSS:
   * no se calculan ni se deducen. Un archivo con esos campos en blanco lo
   * rechaza el IMSS **sin decir cuál de los dos faltaba**, así que el error
   * tiene que salir aquí, con el nombre del campo.
   */
  if (registroPatronal.trim().length !== 11) {
    throw new Error(
      'El registro patronal son 11 caracteres (los 10 del registro más su dígito ' +
        'verificador) y hoy hay ' +
        `${registroPatronal.trim().length}. Captúralo en Perfil → Configuración de ` +
        'empresa: va en las posiciones 01-11 de cada movimiento, y sin él el IMSS ' +
        'rechaza el archivo entero.',
    );
  }
  if (!guia.trim()) {
    throw new Error(
      'Falta la guía de la subdelegación. La asigna el IMSS y va en las posiciones ' +
        '134-138 de cada movimiento y en el registro de cifras de control. Captúrala en ' +
        'Perfil → Configuración de empresa.',
    );
  }

  const noExportables: NoExportable[] = [];
  const transliterados: string[] = [];
  const lineas: string[] = [];

  // El registro patronal son 11 caracteres: 10 + su dígito verificador. Se
  // captura junto y se parte aquí; el verificador NO se calcula, porque no hay
  // algoritmo publicado y un dígito inventado junto a un registro real es peor
  // que un campo vacío.
  const rp = registroPatronal.trim();
  const rpBase = rp.slice(0, 10);
  const rpDigito = rp.slice(10, 11);

  // Sólo los que de verdad causaron alta en este periodo. Los demás no son un
  // movimiento: ya estaban.
  const conAlta = empleados.filter(
    (e) => e.fecha_alta && dentroDelPeriodo(e.fecha_alta, inicio, fin),
  );

  for (const empleado of conAlta) {
    const falta = faltantes(empleado);
    if (falta.length > 0) {
      noExportables.push({
        empleadoNo: empleado.empleado_no,
        nombre: empleado.nombre,
        motivo: `Falta ${falta.join(', ')}. Sin eso el movimiento iría sobre otra persona, o sobre nadie.`,
      });
      continue;
    }

    // El SBC del RECIBO, no el de la ficha: es el que se usó para calcular las
    // cuotas de este periodo, y el archivo tiene que decir lo mismo que el PDF.
    const recibo = nomina.recibos.find((r) => r.empleado_no === empleado.empleado_no);
    if (!recibo) {
      noExportables.push({
        empleadoNo: empleado.empleado_no,
        nombre: empleado.nombre,
        motivo:
          'No entró al cálculo de este periodo, así que no hay SBC con el que ' +
          'declararlo. Revisa si está vinculado al checador.',
      });
      continue;
    }

    const { linea, transliterados: cambios } = escribirRegistro(ALTA, {
      registro_patronal: rpBase,
      digito_rp: rpDigito,
      nss: empleado.nss.slice(0, 10),
      digito_nss: empleado.nss.slice(10, 11),
      apellido_paterno: (empleado.apellido_paterno ?? '').toUpperCase(),
      apellido_materno: (empleado.apellido_materno ?? '').toUpperCase(),
      nombres: (empleado.nombres ?? '').toUpperCase(),
      sbc: sbcSeisPosiciones(aCentavos(recibo.sbc)),
      tipo_trabajador: TIPO_TRABAJADOR_PERMANENTE,
      tipo_salario: TIPO_SALARIO_FIJO,
      jornada: JORNADA_NORMAL,
      fecha_movimiento: fechaDDMMAAAA(empleado.fecha_alta as string),
      // UMF (clínica de adscripción) y CURP: el modelo no los guarda. La CURP
      // el propio manual la marca como **dato opcional**; la UMF va en ceros y
      // eso queda anotado como abierto, no disfrazado de dato.
      umf: '',
      tipo_movimiento: TIPO_ALTA_REINGRESO,
      guia,
      clave_trabajador: empleado.empleado_no,
      curp: '',
      identificador: IDENTIFICADOR_FORMATO,
    });

    lineas.push(linea);
    for (const campo of cambios) {
      transliterados.push(`${empleado.nombre} (${campo})`);
    }
  }

  // Las cifras de control van SIEMPRE, incluso con cero movimientos: es el
  // segundo formato que el documento exige por lote, y un lote sin él está
  // incompleto aunque el primero esté perfecto.
  const { linea: control } = escribirRegistro(CIFRAS_CONTROL, {
    asteriscos: '*************',
    total_registros: String(lineas.length),
    guia,
    identificador: IDENTIFICADOR_FORMATO,
  });
  lineas.push(control);

  const texto = lineas.join(CRLF) + CRLF;
  return {
    nombre: `MovimientosIMSS_${inicio}_${fin}.txt`,
    bytes: bytesAscii(texto),
    noExportables,
    transliterados,
  };
}
