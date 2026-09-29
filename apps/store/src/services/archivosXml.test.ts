import { describe, expect, it } from 'vitest';
import { ACCEPT_XML, MOTIVO_NO_XML, esNombreXml, separarXml } from './archivosXml';

const f = (nombre: string) => new File(['x'], nombre);

describe('C-03 · qué entra a un uploader de CFDI', () => {
  it('la extensión .xml se reconoce sin importar mayúsculas', () => {
    for (const n of ['a.xml', 'FACTURA.XML', 'Mixta.Xml', 'con espacios y puntos.v4.xMl']) {
      expect(esNombreXml(n), n).toBe(true);
    }
  });

  it('lo que no termina en .xml no es XML, aunque lo contenga en el nombre', () => {
    for (const n of ['factura.xml.pdf', 'notas.pdf', 'sinextension', 'xml', 'reporte.xmls', '']) {
      expect(esNombreXml(n), n).toBe(false);
    }
  });

  it('separa por nombre y reporta cada rechazado con su nombre', () => {
    const { xml, rechazados } = separarXml([f('a.xml'), f('B.XML'), f('notas.pdf'), f('foto.jpg')]);
    expect(xml.map((x) => x.name)).toEqual(['a.xml', 'B.XML']);
    expect(rechazados).toEqual([
      { fileName: 'notas.pdf', error: MOTIVO_NO_XML },
      { fileName: 'foto.jpg', error: MOTIVO_NO_XML },
    ]);
  });

  it('el accept del input admite ambas cajas y los tipos MIME de XML', () => {
    expect(ACCEPT_XML.split(',')).toEqual(expect.arrayContaining(['.xml', '.XML', 'text/xml', 'application/xml']));
  });
});
