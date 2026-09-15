/**
 * Pólizas contables derivadas de los CFDI ya parseados — T7, CASCARÓN.
 *
 * DE DÓNDE SALE CADA NÚMERO
 * -------------------------
 * De `cfdiParser.ts` y de nada más: subtotal, descuento, IVA trasladado e
 * impuestos retenidos ya vienen leídos del XML. Aquí **no se calcula un
 * impuesto**, se acomodan importes que ya existen en los dos lados de una
 * partida doble. Ésa es la razón de que este módulo pueda vivir en el
 * navegador sin romper la regla de oro del repo: no hay motor fiscal metido en
 * el front, hay contabilidad de la que ya está timbrada.
 *
 * POR QUÉ LA CONTRAPARTE SE CALCULA Y NO SE COPIA DE `total`
 * ---------------------------------------------------------
 * La cuenta de Clientes (105) o Proveedores (201) podría tomar el `total` del
 * CFDI. No lo hace: se calcula como `base + IVA trasladado − retenciones`. Así
 * la póliza **cuadra por construcción**, sin depender de que el parser haya
 * leído todos los impuestos del comprobante — hoy lee IVA (002) e ISR (001),
 * no IEPS (003). Cuando el `total` del CFDI y la suma de la póliza no
 * coinciden, la diferencia se GUARDA en `diferenciaConTotal` y la pantalla la
 * enseña, en vez de cuadrar a la fuerza contra un renglón de ajuste que
 * escondería el hueco.
 *
 * LO QUE ESTE CASCARÓN NO HACE
 * ----------------------------
 * No conoce el costo de venta ni el inventario (un ingreso no descarga
 * mercancía), no separa IVA cobrado de IVA por cobrar según el método de pago,
 * no maneja pagos parciales contra la factura original más allá del importe, y
 * no genera la póliza de nómina —los recibos tipo N se cuentan aparte y se
 * quedan fuera, como en todo el resto de la app desde T4—.
 */

import { facturasFiscales, contarNomina, type CFDI, type CFDIFiscal } from '../fiscalAgentApi';
import { nombreDeCuenta } from './catalogoSAT';

/** De quién es el CFDI respecto del contribuyente que está contabilizando. */
export type DireccionCFDI = 'emitido' | 'recibido';

export type TipoPoliza = 'ingreso' | 'egreso' | 'diario';

export interface MovimientoPoliza {
  cuenta: string;
  nombre: string;
  cargo: number;
  abono: number;
}

export interface Poliza {
  uuid: string;
  fecha: string;
  /** Tipo de póliza en el sentido contable (Anexo 24: Ingreso / Egreso / Diario). */
  tipo: TipoPoliza;
  concepto: string;
  /** RFC de la otra parte: el cliente si se emitió, el proveedor si se recibió. */
  contraparte: string;
  direccion: DireccionCFDI;
  /** Tipo de comprobante del CFDI de origen (I, E, T, P). */
  tipoComprobante: CFDIFiscal['tipo'];
  movimientos: MovimientoPoliza[];
  totalCargos: number;
  totalAbonos: number;
  /**
   * `total` del CFDI menos lo que la póliza movió del lado de la contraparte.
   * Distinto de cero significa que el comprobante trae importes que el parser
   * no lee (IEPS, otros impuestos locales), no que la póliza esté descuadrada.
   */
  diferenciaConTotal: number;
}

export interface ResultadoPolizas {
  polizas: Poliza[];
  /** Recibos de nómina (tipo N) que se quedaron fuera. Informativo. */
  recibosNomina: number;
  /** CFDI que no mueven cuentas: traslados y comprobantes en ceros. */
  sinEfecto: number;
}

const CUENTAS = {
  bancos: '102',
  clientes: '105',
  contribucionesAFavor: '107',
  ivaAcreditable: '118',
  proveedores: '201',
  ivaTrasladado: '208',
  retencionesPorEnterar: '216',
  ingresos: '401',
  gastos: '601',
} as const;

/** Dos decimales. Los importes de un CFDI ya vienen así; esto quita ruido binario. */
function redondea(n: number): number {
  return Math.round((n + Number.EPSILON) * 100) / 100;
}

function mov(cuenta: string, cargo: number, abono: number): MovimientoPoliza {
  return { cuenta, nombre: nombreDeCuenta(cuenta), cargo: redondea(cargo), abono: redondea(abono) };
}

/**
 * El RFC del contribuyente, deducido de los comprobantes cargados.
 *
 * POR QUÉ SE DEDUCE Y NO SE PIDE: la ficha del cliente tiene el RFC como campo
 * **opcional** (`ClienteCartera.rfc`) y los clientes de demostración no lo
 * traen, así que exigirlo dejaría la pantalla vacía justo en la demo. El RFC
 * propio es el único que aparece en TODOS los comprobantes de la carpeta —en
 * los que emitió está de emisor y en los que recibió, de receptor—, así que el
 * más repetido es él. Se enseña en pantalla para que quien mire pueda
 * desmentirlo, y se puede sobrescribir a mano.
 *
 * Empate: gana el alfabéticamente menor, para que dos corridas con los mismos
 * archivos den el mismo resultado.
 */
export function inferirRfcPropio(facturas: CFDI[]): string {
  const cuenta = new Map<string, number>();
  for (const f of facturas) {
    for (const rfc of new Set([f.rfc_emisor, f.rfc_receptor])) {
      const clave = (rfc || '').toUpperCase();
      if (!clave) continue;
      cuenta.set(clave, (cuenta.get(clave) ?? 0) + 1);
    }
  }
  let mejor = '';
  let mejorCuenta = 0;
  for (const [rfc, n] of cuenta) {
    if (n > mejorCuenta || (n === mejorCuenta && rfc < mejor)) {
      mejor = rfc;
      mejorCuenta = n;
    }
  }
  return mejor;
}

function direccionDe(cfdi: CFDI, rfcPropio: string): DireccionCFDI {
  const propio = rfcPropio.toUpperCase();
  if (propio && (cfdi.rfc_emisor || '').toUpperCase() === propio) return 'emitido';
  if (propio && (cfdi.rfc_receptor || '').toUpperCase() === propio) return 'recibido';
  // Sin RFC que comparar, el tipo de comprobante es lo único que queda: un
  // CFDI de Ingreso lo emite quien cobra. Es una suposición, y por eso la
  // pantalla enseña de quién cree que es cada póliza.
  return cfdi.tipo === 'E' ? 'recibido' : 'emitido';
}

/**
 * Los asientos de un CFDI de Ingreso (I) o de Egreso (E).
 *
 * El Egreso es el Ingreso con los cargos y los abonos intercambiados: una nota
 * de crédito deshace exactamente lo que la factura hizo. Por eso comparten
 * función en vez de tener dos listas paralelas que alguien pueda desincronizar.
 */
function asientosDeFactura(
  cfdi: CFDIFiscal,
  direccion: DireccionCFDI,
): { movimientos: MovimientoPoliza[]; contraparteImporte: number } {
  const base = redondea((cfdi.subtotal || 0) - (cfdi.descuento || 0));
  const ivaTrasladado = redondea(cfdi.iva_trasladado || 0);
  const retenciones = redondea((cfdi.iva_retenido || 0) + (cfdi.isr_retenido || 0));
  const contraparteImporte = redondea(base + ivaTrasladado - retenciones);

  const partidas: { cuenta: string; importe: number; esCargoEnIngreso: boolean }[] = [
    { cuenta: direccion === 'emitido' ? CUENTAS.clientes : CUENTAS.proveedores, importe: contraparteImporte, esCargoEnIngreso: direccion === 'emitido' },
    { cuenta: direccion === 'emitido' ? CUENTAS.ingresos : CUENTAS.gastos, importe: base, esCargoEnIngreso: direccion !== 'emitido' },
    { cuenta: direccion === 'emitido' ? CUENTAS.ivaTrasladado : CUENTAS.ivaAcreditable, importe: ivaTrasladado, esCargoEnIngreso: direccion !== 'emitido' },
    { cuenta: direccion === 'emitido' ? CUENTAS.contribucionesAFavor : CUENTAS.retencionesPorEnterar, importe: retenciones, esCargoEnIngreso: direccion === 'emitido' },
  ];

  // Una nota de crédito (E) invierte los cargos y los abonos de la factura.
  const invierte = cfdi.tipo === 'E';
  const movimientos = partidas
    .filter((p) => p.importe !== 0)
    .map((p) => {
      const esCargo = invierte ? !p.esCargoEnIngreso : p.esCargoEnIngreso;
      return mov(p.cuenta, esCargo ? p.importe : 0, esCargo ? 0 : p.importe);
    });

  return { movimientos, contraparteImporte };
}

/** Los asientos de un complemento de Pagos (P): mueve efectivo, no resultados. */
function asientosDePago(cfdi: CFDIFiscal, direccion: DireccionCFDI): MovimientoPoliza[] {
  const importe = redondea(cfdi.monto_pago || cfdi.total || 0);
  if (importe === 0) return [];
  return direccion === 'emitido'
    ? [mov(CUENTAS.bancos, importe, 0), mov(CUENTAS.clientes, 0, importe)]
    : [mov(CUENTAS.proveedores, importe, 0), mov(CUENTAS.bancos, 0, importe)];
}

function tipoDePoliza(cfdi: CFDIFiscal, direccion: DireccionCFDI): TipoPoliza {
  if (cfdi.tipo === 'P') return direccion === 'emitido' ? 'ingreso' : 'egreso';
  if (cfdi.tipo === 'T') return 'diario';
  const entraDinero = (cfdi.tipo === 'I') === (direccion === 'emitido');
  return entraDinero ? 'ingreso' : 'egreso';
}

function conceptoDe(cfdi: CFDIFiscal, direccion: DireccionCFDI): string {
  const etiqueta: Record<CFDIFiscal['tipo'], string> = {
    I: direccion === 'emitido' ? 'Venta' : 'Compra',
    E: direccion === 'emitido' ? 'Nota de crédito a cliente' : 'Nota de crédito de proveedor',
    P: direccion === 'emitido' ? 'Cobro de cliente' : 'Pago a proveedor',
    T: 'Traslado de mercancía',
  };
  const descripcion = (cfdi.descripcion || '').trim();
  return descripcion ? `${etiqueta[cfdi.tipo]} — ${descripcion}` : etiqueta[cfdi.tipo];
}

/**
 * Una póliza por CFDI fiscal. Los recibos de nómina se cuentan y se excluyen.
 *
 * `rfcPropio` vacío es válido: cae en la suposición por tipo de comprobante,
 * que la pantalla declara.
 */
export function generarPolizas(facturas: CFDI[], rfcPropio: string): ResultadoPolizas {
  const fiscales = facturasFiscales(facturas);
  const polizas: Poliza[] = [];
  let sinEfecto = 0;

  for (const cfdi of fiscales) {
    const direccion = direccionDe(cfdi, rfcPropio);
    let movimientos: MovimientoPoliza[];
    let contraparteImporte: number;

    if (cfdi.tipo === 'P') {
      movimientos = asientosDePago(cfdi, direccion);
      contraparteImporte = redondea(cfdi.monto_pago || cfdi.total || 0);
    } else if (cfdi.tipo === 'T') {
      // Un traslado no transfiere propiedad ni importe: no mueve cuentas.
      movimientos = [];
      contraparteImporte = 0;
    } else {
      const asientos = asientosDeFactura(cfdi, direccion);
      movimientos = asientos.movimientos;
      contraparteImporte = asientos.contraparteImporte;
    }

    if (movimientos.length === 0) sinEfecto += 1;

    const totalCargos = redondea(movimientos.reduce((s, m) => s + m.cargo, 0));
    const totalAbonos = redondea(movimientos.reduce((s, m) => s + m.abono, 0));

    polizas.push({
      uuid: cfdi.uuid,
      fecha: cfdi.fecha,
      tipo: tipoDePoliza(cfdi, direccion),
      concepto: conceptoDe(cfdi, direccion),
      contraparte: direccion === 'emitido' ? cfdi.rfc_receptor : cfdi.rfc_emisor,
      direccion,
      tipoComprobante: cfdi.tipo,
      movimientos,
      totalCargos,
      totalAbonos,
      diferenciaConTotal:
        cfdi.tipo === 'T' ? 0 : redondea((cfdi.total || 0) - contraparteImporte),
    });
  }

  return { polizas, recibosNomina: contarNomina(facturas), sinEfecto };
}
