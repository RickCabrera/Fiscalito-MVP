/**
 * Dispersión bancaria — BBVA, Banamex y Banorte. (O-04)
 *
 * ⚠️ **LOS TRES LAYOUTS ESTÁN POR VALIDAR CONTRA EL MANUAL VIGENTE DEL BANCO.**
 *
 * Y eso no es una nota al pie: es la primera línea del archivo, aparece en el
 * selector de la pantalla, va en el nombre del archivo generado, y el
 * `nocturno-log` **no los cuenta como verificados**.
 *
 * POR QUÉ NO HAY CITA
 * -------------------
 * Los manuales de dispersión de nómina de los tres bancos viven detrás del
 * portal de banca empresarial de cada uno: no hay documento público que
 * transcribir, como sí lo hay para el IMSS. Lo que está aquí es la forma
 * **habitual** de esos archivos —longitud fija, cuenta, importe en centavos sin
 * punto, referencia— y sirve para que el operador tenga la estructura y la
 * ajuste contra su manual, no para mandarla a producción sin mirar.
 *
 * QUÉ SÍ ESTÁ VERIFICADO EN ESTE ARCHIVO
 * --------------------------------------
 * **Los importes.** Salen del mismo cálculo que el PDF y cuadran al centavo
 * contra los totales del motor — eso lo mide el test de cuadre igual que en los
 * demás formatos. Lo que no está verificado es **dónde va cada dato**, que es
 * cosa del banco.
 *
 * Dicho de otro modo: si el layout está mal, el banco rechaza el archivo. Si los
 * importes estuvieran mal, pagaría de más o de menos — y de eso sí hay
 * garantía.
 */

import { aAscii, bytesAscii } from './ascii';
import { aCentavos } from './dinero';
import type { ArchivoGenerado, DatosExportacion, NoExportable } from './tipos';

const CRLF = '\r\n';

export interface LayoutBanco {
  id: string;
  nombre: string;
  /** Ancho de cada campo, en el orden en que se escriben. */
  campos: { nombre: string; ancho: number; relleno: ' ' | '0'; alinea: 'izq' | 'der' }[];
}

function campo(
  nombre: string,
  ancho: number,
  relleno: ' ' | '0' = ' ',
  alinea: 'izq' | 'der' = 'izq',
) {
  return { nombre, ancho, relleno, alinea };
}

/**
 * Los tres layouts, con la misma estructura y anchos distintos.
 *
 * `importe_centavos` va **sin punto decimal** en los tres: es la convención de
 * dispersión que comparten, y la que hace que un punto de más no mueva el pago
 * por un factor de cien.
 */
export const LAYOUTS_BANCO: LayoutBanco[] = [
  {
    id: 'bbva',
    nombre: 'BBVA',
    campos: [
      campo('cuenta', 20),
      campo('importe_centavos', 15, '0', 'der'),
      campo('nombre', 40),
      campo('referencia', 20),
    ],
  },
  {
    id: 'banamex',
    nombre: 'Banamex',
    campos: [
      campo('cuenta', 18),
      campo('importe_centavos', 13, '0', 'der'),
      campo('nombre', 30),
      campo('referencia', 15),
    ],
  },
  {
    id: 'banorte',
    nombre: 'Banorte',
    campos: [
      campo('cuenta', 20),
      campo('importe_centavos', 12, '0', 'der'),
      campo('nombre', 40),
      campo('referencia', 16),
    ],
  },
];

function escribir(layout: LayoutBanco, valores: Record<string, string>): string {
  return layout.campos
    .map((c) => {
      const v = valores[c.nombre] ?? '';
      // Aquí SÍ se recorta el nombre, y es la única excepción del proyecto: un
      // nombre largo en una dispersión no cambia a quién se le paga —eso lo
      // decide la CUENTA— y los bancos truncan el concepto de todas formas. El
      // importe y la cuenta nunca se recortan: si no caben, levanta.
      if (v.length > c.ancho) {
        if (c.nombre === 'nombre') return v.slice(0, c.ancho);
        throw new Error(
          `"${v}" no cabe en el campo "${c.nombre}" (${c.ancho}) del layout de ` +
            `${layout.nombre}. Recortarlo cambiaría a quién o cuánto se le paga.`,
        );
      }
      return c.alinea === 'der' ? v.padStart(c.ancho, c.relleno) : v.padEnd(c.ancho, c.relleno);
    })
    .join('');
}

export function generarDispersion(
  layout: LayoutBanco,
  datos: DatosExportacion,
): ArchivoGenerado {
  const { nomina, empleados } = datos;
  const porNumero = new Map(empleados.map((e) => [e.empleado_no, e]));
  const noExportables: NoExportable[] = [];
  const transliterados: string[] = [];
  const lineas: string[] = [];

  for (const recibo of nomina.recibos) {
    const empleado = porNumero.get(recibo.empleado_no);
    // La cuenta bancaria **no está en el modelo**, y no se inventa. Queda
    // ABIERTO: sin ella el archivo no se puede dispersar, y decirlo es mejor
    // que emitir un renglón con la cuenta en blanco que el banco rechaza sin
    // explicar cuál.
    const cuenta = (empleado as { cuenta_bancaria?: string } | undefined)?.cuenta_bancaria;
    if (!cuenta) {
      noExportables.push({
        empleadoNo: recibo.empleado_no,
        nombre: recibo.nombre,
        motivo:
          'Falta la cuenta bancaria. Todavía no se captura en la ficha del empleado: ' +
          'es una tarea abierta, no un dato que se pueda deducir.',
      });
      continue;
    }

    const nombre = aAscii(recibo.nombre);
    if (nombre.cambio) transliterados.push(`${recibo.nombre} (nombre)`);

    lineas.push(
      escribir(layout, {
        cuenta,
        importe_centavos: String(aCentavos(recibo.neto)),
        nombre: nombre.texto.toUpperCase(),
        referencia: recibo.empleado_no,
      }),
    );
  }

  /**
   * Cero renglones NO se descarga como archivo vacío.
   *
   * Hoy este es el caso NORMAL, no el raro: `cuenta_bancaria` **todavía no
   * existe en el modelo** —no está en la ficha del empleado, ni en el backend,
   * ni en ninguna pantalla— así que en un periodo real *todos* los recibos caen
   * en `noExportables` y esto emitía un `.txt` de **0 bytes** que el navegador
   * descargaba sin decir nada. Un archivo vacío parece un archivo: se manda al
   * banco y el rechazo llega días después.
   *
   * Levantar es lo honesto mientras el dato no exista. Queda ABIERTO en
   * `docs/nocturno-log.md`: capturar la CLABE es lo que falta para que este
   * formato sirva, y no es algo que el exportador pueda deducir.
   */
  if (lineas.length === 0) {
    throw new Error(
      `No hay ni un pago que dispersar: ${noExportables.length} ` +
        `${noExportables.length === 1 ? 'empleado' : 'empleados'} sin cuenta bancaria. ` +
        'La cuenta todavía no se captura en la ficha del empleado — es una tarea ' +
        'abierta, no un dato que se pueda deducir — así que este formato no se ' +
        'puede emitir todavía. El PDF y el TXT del IMSS sí.',
    );
  }

  const texto = lineas.join(CRLF) + CRLF;
  return {
    // "PORVALIDAR" en el nombre del archivo, a propósito: quien lo encuentre en
    // Descargas dentro de tres meses tiene que saberlo sin abrir la app.
    nombre: `Dispersion_${layout.nombre}_PORVALIDAR_${nomina.periodo.inicio}_${nomina.periodo.fin}.txt`,
    bytes: bytesAscii(texto),
    noExportables,
    transliterados,
  };
}
