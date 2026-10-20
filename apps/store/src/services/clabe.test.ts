import { describe, expect, it } from 'vitest';
import { digitoVerificador, motivoClabeInvalida, normalizarCelular } from './clabe';

// Mismo vector que apps/api/tests/plan_p/test_dispersion.py::TestClabe.
describe('CLABE', () => {
  it('vector público válido', () => {
    expect(digitoVerificador('03218000011835971')).toBe(9);
    expect(motivoClabeInvalida('032180000118359719')).toBeNull();
    expect(motivoClabeInvalida('032 180 000118359719')).toBeNull();
    expect(motivoClabeInvalida('')).toBeNull();
  });

  it.each([
    ['032180000118359718', /verificador/],
    ['032180000118359', /18 dígitos/],
    ['03218000011835971X', /sólo lleva dígitos/],
    ['132180000118359719', /verificador/],
  ])('%s es inválida', (mala, motivo) => {
    expect(motivoClabeInvalida(mala)).toMatch(motivo);
  });
});

describe('celular E.164 mexicano', () => {
  it('normaliza las formas aceptadas y rechaza las demás', () => {
    expect(normalizarCelular('55 1234-5678')).toBe('+525512345678');
    expect(normalizarCelular('+5215512345678')).toBe('+525512345678');
    expect(normalizarCelular('525512345678')).toBe('+525512345678');
    expect(normalizarCelular('')).toBe('');
    expect(normalizarCelular('+15551234567')).toBeNull();
  });
});
