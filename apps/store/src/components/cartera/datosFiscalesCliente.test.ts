/**
 * Las reglas de RFC, código postal y entidad del cliente (C-01).
 *
 * MISMO VECTOR QUE `apps/api/tests/cartera/test_cartera_crud.py`
 * (`TestDatosFiscalesDelCliente`). Son dos implementaciones del mismo criterio
 * y divergir tiene que romper una prueba: con el flag de R-07 encendido, lo que
 * este formulario acepta y el backend rechaza es un 422 sobre un campo que el
 * contador ya dio por bueno. Si agregas un caso aquí, agrégalo allá.
 */

import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import {
  ENTIDADES_FEDERATIVAS,
  normalizarRfc,
  problemaCodigoPostal,
  problemaEntidad,
  problemaRfc,
} from './datosFiscalesCliente';

describe('problemaRfc', () => {
  it.each([
    ['612', 'ABCD010101AB1'],
    ['601', 'ABC010101AB1'],
    // DECISIÓN PROVISIONAL (nocturno), §D31: RESICO admite moral y física.
    ['626', 'ABC010101AB1'],
    ['626', 'ABCD010101AB1'],
    // Régimen no capturado: sólo se valida el formato.
    ['', 'ABC010101AB1'],
    ['612', 'ÑAND010101AB1'],
    // Minúsculas y espacios se normalizan, como en el backend.
    ['612', ' abcd010101ab1 '],
  ])('régimen %s acepta %s', (regimen, rfc) => {
    expect(problemaRfc(rfc, regimen, true)).toBeNull();
  });

  it.each([
    ['612', 'ABC010101AB1', /persona física/],
    ['601', 'ABCD010101AB1', /persona moral/],
    ['612', 'ABCD01', /formato/],
    ['612', 'ABCD0101X1AB1', /formato/],
    ['', '1234010101AB1', /formato/],
  ])('régimen %s rechaza %s', (regimen, rfc, motivo) => {
    expect(problemaRfc(rfc, regimen, false)).toMatch(motivo);
  });

  it('vacío: obligatorio en el alta, opcional en la edición', () => {
    expect(problemaRfc('', '612', true)).toMatch(/Captura el RFC/);
    expect(problemaRfc('  ', '612', false)).toBeNull();
  });

  it('normaliza a mayúsculas y sin espacios', () => {
    expect(normalizarRfc(' abcd010101ab1 ')).toBe('ABCD010101AB1');
  });
});

describe('problemaCodigoPostal', () => {
  it.each(['9100', '910000', '9100A'])('rechaza %s', (cp) => {
    expect(problemaCodigoPostal(cp, false)).toMatch(/5 dígitos/);
  });

  it('acepta 5 dígitos, y vacío sólo si no es obligatorio', () => {
    expect(problemaCodigoPostal('01000', true)).toBeNull();
    expect(problemaCodigoPostal('', false)).toBeNull();
    expect(problemaCodigoPostal('', true)).not.toBeNull();
  });
});

describe('problemaEntidad', () => {
  it.each(['XXX', 'ver', 'TX'])('rechaza %s', (clave) => {
    expect(problemaEntidad(clave, false)).toMatch(/c_Estado/);
  });

  it('acepta las claves del catálogo, y vacío sólo si no es obligatorio', () => {
    expect(problemaEntidad('VER', true)).toBeNull();
    expect(problemaEntidad('DIF', true)).toBeNull();
    expect(problemaEntidad('', false)).toBeNull();
    expect(problemaEntidad('', true)).not.toBeNull();
  });
});

describe('ENTIDADES_FEDERATIVAS es el c_Estado versionado del SAT', () => {
  it('coincide EXACTO con las claves de 3 letras de catCFDI.xsd', () => {
    // El XSD también trae estados de EE. UU. y provincias de Canadá (2 letras)
    // y no los agrupa por país. Se compara el conjunto exacto, no el conteo.
    const aqui = dirname(fileURLToPath(import.meta.url));
    const xsd = readFileSync(
      join(aqui, '..', '..', '..', '..', 'api', 'tests', 'xsd', 'catCFDI.xsd'),
      'utf8',
    );
    const inicio = xsd.indexOf('<xs:simpleType name="c_Estado">');
    const fin = xsd.indexOf('</xs:simpleType>', inicio);
    expect(inicio).toBeGreaterThan(-1);
    const claves = [...xsd.slice(inicio, fin).matchAll(/value="([^"]+)"/g)]
      .map((m) => m[1])
      .filter((c) => c.length === 3);

    const nuestras = ENTIDADES_FEDERATIVAS.map((e) => e.clave);
    expect(new Set(nuestras).size).toBe(nuestras.length);
    expect([...nuestras].sort()).toEqual([...claves].sort());
    expect(nuestras).toHaveLength(33);
  });

  it('CMX va antes que DIF, y DIF dice que es la clave anterior', () => {
    const claves = ENTIDADES_FEDERATIVAS.map((e) => e.clave as string);
    expect(claves.indexOf('CMX')).toBeLessThan(claves.indexOf('DIF'));
    expect(ENTIDADES_FEDERATIVAS.find((e) => e.clave === 'DIF')?.nombre).toMatch(/anterior/);
  });
});
