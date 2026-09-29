/**
 * CFDI 4.0 mínimo y SINTÉTICO para tests de uploaders: RFC de pruebas del SAT
 * y UUID inventados. Nada sale de `03. CFDI DE NOMINA/` ni de las demo-xmls.
 */

export const RFC_EMISOR_PRUEBA = 'EKU9003173C9';
export const RFC_RECEPTOR_PRUEBA = 'XIQB891116QE4';

interface Opciones {
  uuid: string;
  tipo?: 'I' | 'E' | 'N';
  claveProdServ?: string;
  subtotal?: number;
}

export function cfdiSintetico({ uuid, tipo = 'I', claveProdServ = '80101500', subtotal = 1000 }: Opciones): string {
  return [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4"',
    ' xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital"',
    ` Version="4.0" Fecha="2026-01-15T10:00:00" SubTotal="${subtotal}" Total="${subtotal}"`,
    ` TipoDeComprobante="${tipo}">`,
    `  <cfdi:Emisor Rfc="${RFC_EMISOR_PRUEBA}" Nombre="EMISOR DE PRUEBA" RegimenFiscal="612"/>`,
    `  <cfdi:Receptor Rfc="${RFC_RECEPTOR_PRUEBA}" Nombre="RECEPTOR DE PRUEBA" UsoCFDI="G03"/>`,
    '  <cfdi:Conceptos>',
    `    <cfdi:Concepto ClaveProdServ="${claveProdServ}" Cantidad="1" Descripcion="SERVICIO" ValorUnitario="${subtotal}" Importe="${subtotal}"/>`,
    '  </cfdi:Conceptos>',
    '  <cfdi:Complemento>',
    `    <tfd:TimbreFiscalDigital Version="1.1" UUID="${uuid}"/>`,
    '  </cfdi:Complemento>',
    '</cfdi:Comprobante>',
  ].join('\n');
}

export function archivo(nombre: string, contenido: string): File {
  return new File([contenido], nombre, { type: nombre.toLowerCase().endsWith('.xml') ? 'text/xml' : '' });
}
