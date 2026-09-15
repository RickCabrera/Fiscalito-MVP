/**
 * DIOT en archivo de carga batch, delimitado por barras. (T5)
 *
 * EL LAYOUT ESTÁ POR VALIDAR, Y ESO NO ES UNA FORMALIDAD
 * ------------------------------------------------------
 * El resto de este directorio declara su fuente porque `FormatoExportacion`
 * obliga (`tipos.ts`), y aquí se sostiene la misma regla aunque este formato no
 * entre al registro de nómina: **el número y el orden exacto de los campos NO
 * se pudo verificar contra un documento publicado del SAT**. Lo que sigue es la
 * estructura conocida del archivo de carga batch de la DIOT, transcrita de
 * memoria del formato A-29 y ordenada como se documenta habitualmente; no está
 * contrastada contra el instructivo vigente.
 *
 * Por eso el archivo lleva `PORVALIDAR` en el nombre y la pantalla lo dice
 * antes del botón. Un archivo que se sube al portal del SAT, o está respaldado
 * por su instructivo o el operador tiene que saber que no lo está — es
 * literalmente la doctrina de `exportadores/tipos.ts`.
 *
 * **Antes de la primera carga real:** contrastar `CAMPOS` contra el instructivo
 * vigente de la DIOT (A-29) y cargar el `.txt` en el validador del SAT, que
 * rechaza el archivo entero si el orden no coincide.
 *
 * LO QUE EL BACKEND SABE, Y LO QUE NO
 * -----------------------------------
 * `POST /api/v1/diot` devuelve por proveedor **RFC, nombre, total de
 * operaciones (subtotal), IVA pagado y cuántas facturas**, y nada más
 * (`app/fiscal_engine/diot.py`). La DIOT pide el valor de los actos separado
 * por tasa —16%, 0% y exentos—, y ese corte **no viaja en la respuesta**.
 * Reconstruirlo aquí es la única salida sin tocar el API, que la tarea prohíbe;
 * `derivarPorTasa` hace ese corte y dice exactamente qué supone.
 */

import { aAscii, bytesAscii } from './ascii';
import type { DIOTProveedor, DIOTResponse } from '../fiscalAgentApi';

const CRLF = '\r\n';
const SEP = '|';

/** La tasa general de IVA, para deshacer el cálculo del backend. */
const TASA_IVA = 0.16;

/**
 * Los campos del renglón, en orden. **Sin encabezados en el archivo**: la carga
 * batch de la DIOT lee posiciones, no nombres, y un encabezado se leería como
 * un proveedor con RFC "Tipo de tercero".
 *
 * Están nombrados aquí —y sólo aquí— para que validar el layout sea leer esta
 * lista contra el instructivo, en vez de contar barras en un `join`.
 */
const CAMPOS = [
  'tipo_tercero',
  'tipo_operacion',
  'rfc',
  'id_fiscal_extranjero',
  'nombre_extranjero',
  'pais_residencia',
  'nacionalidad',
  'valor_actos_16',
  'valor_actos_16_importacion',
  'valor_actos_importacion_exentos',
  'valor_actos_tasa_0',
  'valor_actos_exentos',
  'iva_retenido_por_el_contribuyente',
  'iva_acreditable_16',
  'devoluciones_descuentos_bonificaciones',
] as const;

/**
 * `04` = proveedor nacional. **DECISIÓN PROVISIONAL (nocturno).**
 *
 * Los otros dos valores son `05` (extranjero) y `15` (global). El desglose del
 * backend agrupa por `rfc_emisor` y un proveedor extranjero no tiene RFC
 * mexicano, así que en la práctica todo lo que llega aquí es nacional — pero
 * eso es una consecuencia del parser de CFDI, no un dato declarado. Si algún
 * día entran comprobantes de comercio exterior, este campo miente.
 */
const TIPO_TERCERO_NACIONAL = '04';

/**
 * `85` = "Otros". **DECISIÓN PROVISIONAL (nocturno), y es la conservadora.**
 *
 * Los otros dos son `03` (prestación de servicios profesionales) y `06`
 * (arrendamiento de inmuebles). Distinguirlos exige leer la clave de producto o
 * servicio de cada concepto del CFDI, que el desglose agregado no trae. "Otros"
 * es el cajón que no afirma una naturaleza de la operación; poner `03` en todo
 * sí la afirmaría, y sería falso para el primer proveedor de materiales.
 */
const TIPO_OPERACION_OTROS = '85';

/** Los importes van con punto decimal y sin separador de millares. */
function importe(centavos: number): string {
  const signo = centavos < 0 ? '-' : '';
  const abs = Math.abs(centavos);
  return `${signo}${Math.floor(abs / 100)}.${String(abs % 100).padStart(2, '0')}`;
}

/**
 * Los importes de la DIOT llegan como `number` y se pasan a centavos enteros.
 *
 * `dinero.ts` no sirve aquí: parsea cadenas, porque los importes de nómina
 * viajan como `Decimal` serializado. Los de la DIOT vienen de `round(x, 2)` en
 * Python y llegan al front como float de JSON, así que el redondeo ya está
 * hecho aguas arriba y lo único que falta es fijarlo antes de sumar o restar en
 * punto flotante.
 */
function aCentavos(n: number): number {
  return Math.round(n * 100);
}

export interface DesglosePorTasa {
  /** Valor de los actos pagados a la tasa del 16%. */
  base16: number;
  /** IVA acreditable de esos actos. Es el dato del backend, sin recalcular. */
  iva16: number;
  /** Lo que no trae IVA. Ver el porqué de que vaya entero a tasa 0%. */
  tasaCero: number;
}

/**
 * Parte el total del proveedor en lo gravado al 16% y lo que no lo está.
 *
 * LA BASE DEL 16% SE DEDUCE DEL IVA, NO AL REVÉS
 * -----------------------------------------------
 * `iva_pagado / 0.16` da el valor de los actos gravados; el resto del subtotal
 * es lo que no llevó IVA. Se hace en este sentido porque **el IVA es el dato
 * duro**: es lo que el proveedor trasladó y lo que el contribuyente acredita.
 * El `iva16` que sale en el archivo es el del backend tal cual, sin recalcular
 * sobre la base deducida — recalcularlo metería un redondeo propio en la única
 * columna que el SAT cruza contra los CFDI del proveedor.
 *
 * LA TOLERANCIA NO ES UN FUDGE
 * -----------------------------
 * El backend redondea el IVA a dos decimales **después de sumarlo**, así que
 * `iva/0.16` puede caer unos centavos por debajo del subtotal aunque todas las
 * facturas fueran del 16%. Sin tolerancia, casi todo proveedor sacaría una
 * línea de "tasa 0%" de seis centavos que nadie pagó. El margen es de 5
 * centavos por factura, holgado contra los ±3.2 que el redondeo puede mover por
 * cada una.
 *
 * DECISIÓN PROVISIONAL (nocturno): lo no gravado va ENTERO a tasa 0%
 * -------------------------------------------------------------------
 * La DIOT separa "tasa 0%" de "exentos", y el desglose agregado **no permite
 * distinguirlos**: los dos llegan aquí como subtotal sin IVA. Van a tasa 0%
 * porque es lo que le corresponde a la mayoría de lo que un proveedor factura
 * sin IVA, y porque dejar la columna de exentos en cero es una omisión visible
 * al revisar el archivo, mientras que repartir a ojo entre las dos sería
 * inventar un dato. Quien valide el layout revisa también esto.
 */
export function derivarPorTasa(proveedor: DIOTProveedor): DesglosePorTasa {
  const total = aCentavos(proveedor.total_operaciones);
  const iva = aCentavos(proveedor.iva_pagado);
  if (iva <= 0) return { base16: 0, iva16: 0, tasaCero: total };

  // El `min` cierra el caso imposible: un IVA que implica más base que el
  // subtotal declarado. Pasa si el comprobante trae retenciones o tasas
  // mezcladas, y sin el tope saldría un "tasa 0%" negativo.
  const base16 = Math.min(Math.round(iva / TASA_IVA), total);
  const resto = total - base16;
  const tolerancia = 5 * Math.max(proveedor.cantidad_facturas, 1);

  if (resto <= tolerancia) return { base16: total, iva16: iva, tasaCero: 0 };
  return { base16, iva16: iva, tasaCero: resto };
}

function renglon(proveedor: DIOTProveedor): { texto: string; transliterado: boolean } {
  const { base16, iva16, tasaCero } = derivarPorTasa(proveedor);
  // El RFC pasa por ASCII igual que todo lo demás: no debería llevar nada
  // fuera de [A-Z0-9&Ñ], pero la `Ñ` es válida en un RFC y el archivo no.
  const rfc = aAscii(proveedor.rfc.trim().toUpperCase());

  const valores: Record<(typeof CAMPOS)[number], string> = {
    tipo_tercero: TIPO_TERCERO_NACIONAL,
    tipo_operacion: TIPO_OPERACION_OTROS,
    rfc: rfc.texto,
    // Los cuatro campos de residente en el extranjero van vacíos: sólo aplican
    // con tipo de tercero `05`, y aquí siempre es `04`.
    id_fiscal_extranjero: '',
    nombre_extranjero: '',
    pais_residencia: '',
    nacionalidad: '',
    valor_actos_16: importe(base16),
    // Importación: el desglose no distingue comercio exterior, así que van en
    // cero en vez de duplicar el nacional.
    valor_actos_16_importacion: '0.00',
    valor_actos_importacion_exentos: '0.00',
    valor_actos_tasa_0: importe(tasaCero),
    valor_actos_exentos: '0.00',
    // El IVA que el contribuyente RETUVO a este proveedor es otro cálculo
    // (`/api/v1/retenciones-terceros`) y no viaja en la respuesta de la DIOT.
    // Cero es lo que se puede afirmar desde aquí; quien retenga IVA lo corrige
    // en el portal antes de enviar.
    iva_retenido_por_el_contribuyente: '0.00',
    iva_acreditable_16: importe(iva16),
    devoluciones_descuentos_bonificaciones: '0.00',
  };

  return { texto: CAMPOS.map((c) => valores[c]).join(SEP), transliterado: rfc.cambio };
}

export interface ArchivoDIOT {
  nombre: string;
  bytes: Uint8Array;
  /** RFC que hubo que transliterar a ASCII. La pantalla los lista. */
  transliterados: string[];
  /** Cuántos renglones lleva el archivo. Uno por proveedor. */
  renglones: number;
}

/**
 * El `.txt` de carga batch: **una línea por proveedor, sin encabezados**.
 *
 * No hay renglón de totales, a diferencia del formato genérico de nómina: la
 * carga batch lee cada línea como un tercero, y un "TOTAL" al final entraría al
 * portal como un proveedor más.
 */
export function generarDIOTBatch(data: DIOTResponse): ArchivoDIOT {
  const transliterados: string[] = [];
  const lineas: string[] = [];

  for (const proveedor of data.proveedores) {
    const { texto, transliterado } = renglon(proveedor);
    if (transliterado) transliterados.push(proveedor.rfc);
    lineas.push(texto);
  }

  // Un periodo sin proveedores sale como archivo de cero líneas, no como error:
  // levantar aquí escondería que el periodo no tuvo egresos.
  const texto = lineas.length > 0 ? lineas.join(CRLF) + CRLF : '';
  const periodo = data.periodo.trim().replace(/\s+/g, '_').replace(/[^A-Za-z0-9_]/g, '');

  return {
    nombre: `DIOT_PORVALIDAR_${periodo}.txt`,
    bytes: bytesAscii(texto),
    transliterados,
    renglones: lineas.length,
  };
}

/**
 * La advertencia que la pantalla pinta **antes** del botón, no después.
 *
 * Vive aquí y no en el `.tsx` por la misma razón que `registro.ts` guarda sus
 * citas: quien cambie el layout tiene a la vista el texto que lo describe.
 */
export const DIOT_BATCH_POR_VALIDAR =
  'Layout por validar: el orden de los campos no está contrastado contra el instructivo ' +
  'vigente del SAT, y el corte por tasa (16% / 0% / exentos) se deduce del IVA pagado ' +
  'porque el desglose no lo trae. Los importes sí salen del cálculo, sin recomponer. ' +
  'Valídalo en el portal antes de enviarlo.';
