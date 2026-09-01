import { describe, expect, it } from 'vitest';
import ingreso001 from '../../public/demo-xmls/2026/01/ingreso-001.xml?raw';
import egreso001 from '../../public/demo-xmls/2026/01/egreso-001.xml?raw';
import { parseCFDIFromXML } from './cfdiParser';

/**
 * Las fixtures son las mismas que sirve la app en /demo-xmls, para no tener dos
 * fuentes de verdad. Se afirman hechos estructurales y montos; los RFC se leen
 * de la propia fixture en vez de escribirse literales.
 */
describe('parseCFDIFromXML', () => {
  it('extrae los datos de un CFDI de ingreso timbrado', () => {
    const cfdi = parseCFDIFromXML(ingreso001);

    expect(cfdi.uuid).toBe('11111111-1111-1111-1111-111111110001');
    expect(cfdi.tipo).toBe('I');
    expect(cfdi.fecha).toBe('2026-01-15');
    expect(cfdi.subtotal).toBe(15000);
    expect(cfdi.total).toBe(17400);
    expect(cfdi.iva_trasladado).toBe(2400);
    expect(cfdi.metodo_pago).toBe('PUE');
    expect(cfdi.clave_prod_serv).toBe('80101500');
  });

  it('lee una factura de compra: es tipo I, con el contribuyente como receptor', () => {
    // egreso-001.xml se llama "egreso" desde la perspectiva del usuario, pero
    // fiscalmente una factura de compra es TipoDeComprobante="I".
    const compra = parseCFDIFromXML(egreso001);
    const propia = parseCFDIFromXML(ingreso001);

    expect(compra.tipo).toBe('I');
    expect(compra.rfc_receptor).toBe(propia.rfc_emisor);
    expect(compra.rfc_emisor).not.toBe(compra.rfc_receptor);
    expect(compra.subtotal).toBe(3200);
  });

  it('reconoce el tipo E cuando el CFDI realmente es de egreso', () => {
    const xml = [
      '<?xml version="1.0" encoding="UTF-8"?>',
      '<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4"',
      ' Version="4.0" Fecha="2026-01-20T09:00:00" SubTotal="500.00" Total="580.00"',
      ' TipoDeComprobante="E">',
      '  <cfdi:Emisor Rfc="AAA010101AAA" Nombre="EMISOR" RegimenFiscal="612"/>',
      '  <cfdi:Receptor Rfc="BBB010101BBB" Nombre="RECEPTOR" UsoCFDI="G02"/>',
      '</cfdi:Comprobante>',
    ].join('\n');

    expect(parseCFDIFromXML(xml).tipo).toBe('E');
  });

  it('rechaza un XML malformado', () => {
    expect(() => parseCFDIFromXML('<cfdi:Comprobante><sin cerrar>')).toThrow(
      /no es un XML/i,
    );
  });

  it('rechaza un XML bien formado que no es CFDI', () => {
    expect(() => parseCFDIFromXML('<?xml version="1.0"?><otra:Cosa xmlns:otra="urn:x"/>')).toThrow(
      /no es un CFDI/i,
    );
  });
});
