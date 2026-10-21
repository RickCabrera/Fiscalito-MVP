import { describe, expect, it } from 'vitest';
import { periodoAVerificar } from './periodo';

describe('periodoAVerificar (P1-03)', () => {
  it('usa el filtro cuando lo hay', () => {
    expect(periodoAVerificar('2026-03-01', '2026-03-31', '2026-10-19')).toEqual({ desde: '2026-03-01', hasta: '2026-03-31' });
  });
  it('sin filtro, del día 1 del mes a hoy', () => {
    expect(periodoAVerificar(undefined, undefined, '2026-10-19')).toEqual({ desde: '2026-10-01', hasta: '2026-10-19' });
  });
  it('sólo "hasta": del día 1 de ese mes', () => {
    expect(periodoAVerificar('', '2026-02-14', '2026-10-19')).toEqual({ desde: '2026-02-01', hasta: '2026-02-14' });
  });
});
