/**
 * El historial asociado al cliente (C-02): ids y ámbito, sin Firestore.
 */

import { describe, expect, it } from 'vitest';
import { camposDeCliente, codificarClienteId, delAmbito, docIdHistorial, milisDe } from './historialCliente';

describe('docIdHistorial', () => {
  it('sin cliente, el id de siempre: el contribuyente no cambia', () => {
    expect(docIdHistorial('predeclaracion', 'Enero 2026')).toBe('predeclaracion_enero_2026');
    expect(docIdHistorial('predeclaracion', 'Enero 2026', null)).toBe('predeclaracion_enero_2026');
    expect(docIdHistorial('estado_cuenta', 'Año 2026')).toBe('estado_cuenta_ano_2026');
  });

  it('el mismo periodo de dos clientes NO comparte documento', () => {
    const a = docIdHistorial('predeclaracion', 'Enero 2026', 'taller');
    const b = docIdHistorial('predeclaracion', 'Enero 2026', 'resico');
    expect(a).toBe('c_taller__predeclaracion_enero_2026');
    expect(a).not.toBe(b);
    expect(a).not.toBe(docIdHistorial('predeclaracion', 'Enero 2026'));
  });

  it('ids que sólo difieren en caja o símbolos siguen siendo distintos', () => {
    const ids = ['Taller-1', 'taller-1', 'taller_1', 'taller.1', 'taller 1'];
    const docIds = new Set(ids.map((id) => docIdHistorial('diot', 'Enero 2026', id)));
    expect(docIds.size).toBe(ids.length);
    // Y nada que Firestore no acepte en un id de documento.
    for (const d of docIds) expect(d).not.toMatch(/\//);
  });

  it('codificarClienteId deja pasar letras, dígitos y guion, y escapa lo demás', () => {
    expect(codificarClienteId('Taller-1')).toBe('Taller-1');
    expect(codificarClienteId('a_b')).toBe('a_5f_b');
    expect(codificarClienteId('a/b')).toBe('a_2f_b');
  });
});

describe('ámbito', () => {
  it('camposDeCliente sólo agrega cliente_id cuando hay cliente', () => {
    expect(camposDeCliente(null)).toEqual({});
    expect(camposDeCliente(undefined)).toEqual({});
    expect(camposDeCliente('taller')).toEqual({ cliente_id: 'taller' });
  });

  it('un cliente sólo ve lo suyo', () => {
    expect(delAmbito({ cliente_id: 'taller' }, 'taller')).toBe(true);
    expect(delAmbito({ cliente_id: 'resico' }, 'taller')).toBe(false);
    // Un registro del contribuyente (o uno anterior a C-02) no es de ningún cliente.
    expect(delAmbito({}, 'taller')).toBe(false);
  });

  it('el contribuyente nunca ve un cálculo hecho para un cliente', () => {
    expect(delAmbito({}, null)).toBe(true);
    expect(delAmbito({ cliente_id: 'taller' }, null)).toBe(false);
  });

  it('milisDe entiende Timestamp, Date y nada', () => {
    expect(milisDe({ toMillis: () => 42 })).toBe(42);
    expect(milisDe(new Date(7))).toBe(7);
    expect(milisDe(undefined)).toBe(0);
  });
});
