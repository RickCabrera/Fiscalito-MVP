/** Parser de archivos XML CFDI en el browser usando DOMParser */

import type { CFDI } from './fiscalAgentApi';

const CFDI_NS = 'http://www.sat.gob.mx/cfd/4';
const CFDI_NS_V3 = 'http://www.sat.gob.mx/cfd/3';
const TFD_NS = 'http://www.sat.gob.mx/TimbreFiscalDigital';
const PAGO20_NS = 'http://www.sat.gob.mx/Pagos20';
const PAGO10_NS = 'http://www.sat.gob.mx/Pagos';

function getComprobante(doc: Document): Element | null {
  return (
    doc.getElementsByTagNameNS(CFDI_NS, 'Comprobante')[0] ||
    doc.getElementsByTagNameNS(CFDI_NS_V3, 'Comprobante')[0] ||
    null
  );
}

function getTimbreFiscal(doc: Document): Element | null {
  return doc.getElementsByTagNameNS(TFD_NS, 'TimbreFiscalDigital')[0] || null;
}

function floatAttr(el: Element, attr: string): number {
  return parseFloat(el.getAttribute(attr) || '0') || 0;
}

function getImpuestosGlobales(comp: Element) {
  let iva_trasladado = 0;
  let iva_retenido = 0;
  let isr_retenido = 0;

  // Buscar el nodo global cfdi:Impuestos (hijo directo de Comprobante, NO el de cada Concepto)
  const impuestosNode =
    comp.getElementsByTagNameNS(CFDI_NS, 'Impuestos')[0] ||
    comp.getElementsByTagNameNS(CFDI_NS_V3, 'Impuestos')[0];

  if (!impuestosNode) return { iva_trasladado, iva_retenido, isr_retenido };

  // Solo tomar nodos Traslado dentro del Impuestos global (via Traslados hijo directo)
  const trasladosContainer =
    impuestosNode.getElementsByTagNameNS(CFDI_NS, 'Traslados')[0] ||
    impuestosNode.getElementsByTagNameNS(CFDI_NS_V3, 'Traslados')[0];

  if (trasladosContainer) {
    const traslados = [
      ...Array.from(trasladosContainer.getElementsByTagNameNS(CFDI_NS, 'Traslado')),
      ...Array.from(trasladosContainer.getElementsByTagNameNS(CFDI_NS_V3, 'Traslado')),
    ];
    for (const t of traslados) {
      if (t.getAttribute('Impuesto') === '002') {
        iva_trasladado += floatAttr(t, 'Importe');
      }
    }
  }

  // Solo tomar nodos Retencion dentro del Impuestos global (via Retenciones hijo directo)
  const retencionesContainer =
    impuestosNode.getElementsByTagNameNS(CFDI_NS, 'Retenciones')[0] ||
    impuestosNode.getElementsByTagNameNS(CFDI_NS_V3, 'Retenciones')[0];

  if (retencionesContainer) {
    const retenciones = [
      ...Array.from(retencionesContainer.getElementsByTagNameNS(CFDI_NS, 'Retencion')),
      ...Array.from(retencionesContainer.getElementsByTagNameNS(CFDI_NS_V3, 'Retencion')),
    ];
    for (const r of retenciones) {
      const impuesto = r.getAttribute('Impuesto');
      if (impuesto === '002') {
        iva_retenido += floatAttr(r, 'Importe');
      } else if (impuesto === '001') {
        isr_retenido += floatAttr(r, 'Importe');
      }
    }
  }

  return { iva_trasladado, iva_retenido, isr_retenido };
}

export function parseCFDIFromXML(xmlString: string): CFDI {
  const parser = new DOMParser();
  const doc = parser.parseFromString(xmlString, 'text/xml');

  const parserError = doc.querySelector('parsererror');
  if (parserError) {
    throw new Error('El archivo no es un XML válido.');
  }

  const comp = getComprobante(doc);
  if (!comp) {
    throw new Error('El XML no es un CFDI válido (no tiene nodo Comprobante).');
  }

  const timbre = getTimbreFiscal(doc);
  const uuid = timbre?.getAttribute('UUID') || crypto.randomUUID();

  const tipoRaw = comp.getAttribute('TipoDeComprobante') || 'I';
  const tipo = (['I', 'E', 'T', 'P'].includes(tipoRaw) ? tipoRaw : 'I') as CFDI['tipo'];

  // Emisor y receptor
  const emisorNS = comp.getElementsByTagNameNS(CFDI_NS, 'Emisor')[0]
    || comp.getElementsByTagNameNS(CFDI_NS_V3, 'Emisor')[0];
  const receptorNS = comp.getElementsByTagNameNS(CFDI_NS, 'Receptor')[0]
    || comp.getElementsByTagNameNS(CFDI_NS_V3, 'Receptor')[0];

  const rfc_emisor = emisorNS?.getAttribute('Rfc') || '';
  const rfc_receptor = receptorNS?.getAttribute('Rfc') || '';

  // Extraer ClaveProdServ del primer concepto
  const primerConcepto =
    comp.getElementsByTagNameNS(CFDI_NS, 'Concepto')[0] ||
    comp.getElementsByTagNameNS(CFDI_NS_V3, 'Concepto')[0];
  const clave_prod_serv = primerConcepto?.getAttribute('ClaveProdServ') || undefined;
  const descripcion = primerConcepto?.getAttribute('Descripcion') || undefined;

  const impuestos = getImpuestosGlobales(comp);

  // Extraer MetodoPago del Comprobante
  const metodo_pago = comp.getAttribute('MetodoPago') || undefined;

  // Para complementos de pago (tipo P), extraer datos del pago
  // NOTA: Solo toma el primer DoctoRelacionado. Un complemento P puede pagar
  // múltiples facturas PPD (múltiples DoctoRelacionado). Para MVP es aceptable.
  let uuid_relacionado: string | undefined;
  let monto_pago: number | undefined;

  if (tipo === 'P') {
    const doctoRel =
      doc.getElementsByTagNameNS(PAGO20_NS, 'DoctoRelacionado')[0] ||
      doc.getElementsByTagNameNS(PAGO10_NS, 'DoctoRelacionado')[0];

    if (doctoRel) {
      uuid_relacionado = doctoRel.getAttribute('IdDocumento') || undefined;
      const impPagado = doctoRel.getAttribute('ImpPagado');
      if (impPagado) {
        monto_pago = parseFloat(impPagado) || undefined;
      }
    }

    // Fallback: si no hay ImpPagado, usar Monto del nodo Pago
    if (!monto_pago) {
      const pagoNode =
        doc.getElementsByTagNameNS(PAGO20_NS, 'Pago')[0] ||
        doc.getElementsByTagNameNS(PAGO10_NS, 'Pago')[0];
      if (pagoNode) {
        monto_pago = floatAttr(pagoNode, 'Monto') || undefined;
      }
    }
  }

  return {
    uuid,
    fecha: (comp.getAttribute('Fecha') || '').substring(0, 10),
    tipo,
    rfc_emisor,
    rfc_receptor,
    subtotal: floatAttr(comp, 'SubTotal'),
    total: floatAttr(comp, 'Total'),
    descuento: floatAttr(comp, 'Descuento') || undefined,
    iva_trasladado: impuestos.iva_trasladado || undefined,
    iva_retenido: impuestos.iva_retenido || undefined,
    isr_retenido: impuestos.isr_retenido || undefined,
    metodo_pago,
    uuid_relacionado,
    monto_pago,
    clave_prod_serv,
    descripcion,
  };
}

function readFileAsText(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = () => reject(new Error(`No se pudo leer el archivo: ${file.name}`));
    reader.readAsText(file);
  });
}

export interface ParseResult {
  success: CFDI[];
  errors: { fileName: string; error: string }[];
}

export async function parseMultipleCFDI(files: File[]): Promise<ParseResult> {
  const success: CFDI[] = [];
  const errors: { fileName: string; error: string }[] = [];

  for (const file of files) {
    try {
      const text = await readFileAsText(file);
      const cfdi = parseCFDIFromXML(text);
      success.push(cfdi);
    } catch (e) {
      errors.push({
        fileName: file.name,
        error: e instanceof Error ? e.message : 'Error desconocido',
      });
    }
  }

  return { success, errors };
}
