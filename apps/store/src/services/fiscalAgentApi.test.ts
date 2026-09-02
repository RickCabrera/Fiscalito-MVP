/**
 * Frontera de tipos front → API (E-01).
 *
 * `PerfilContribuyente.contributor_type` espeja a mano el enum de Python
 * (`app/schemas/fiscal.py:49`) y `/calendario` valida contra su propio set
 * (`app/routes/calendario.py:19`). El front tiene un tipo más que el backend
 * —`contador`— y estas dos funciones son el único paso permitido.
 *
 * Sin esto: 422 de Pydantic en los cálculos y 400 en el calendario, los dos en
 * vivo y ninguno atrapado por el compilador.
 */

import { describe, expect, it } from 'vitest';
import { tipoParaApi, tipoParaCalendario } from './fiscalAgentApi';
import type { ContributorType } from './contributorProfiles';

const CONTRIBUYENTES: ContributorType[] = [
  'asalariado', 'independiente', 'arrendamiento', 'plataformas', 'pyme',
];

describe('tipoParaApi', () => {
  it('omite al contador: un despacho no es el sujeto del cálculo', () => {
    expect(tipoParaApi('contador')).toBeNull();
  });

  // Que E-01 sea aditivo se prueba aquí: los cinco tipos que ya existían salen
  // idénticos, así que ningún request de contribuyente cambia de forma.
  it.each(CONTRIBUYENTES)('%s viaja tal cual', (tipo) => {
    expect(tipoParaApi(tipo)).toBe(tipo);
  });

  it('un perfil sin tipo manda null', () => {
    expect(tipoParaApi(null)).toBeNull();
  });

  it('nunca deja escapar un tipo que el backend no conozca', () => {
    const aceptados = [...CONTRIBUYENTES, null];
    const todos: (ContributorType | null)[] = ['contador', ...CONTRIBUYENTES, null];
    for (const tipo of todos) {
      expect(aceptados).toContain(tipoParaApi(tipo));
    }
  });
});

describe('tipoParaCalendario', () => {
  /**
   * `/calendario` responde 400 si el tipo no está en su set de cinco, así que
   * aquí no se puede mandar null. Un despacho es persona física con régimen
   * 612 o 626: sus obligaciones propias son las de un independiente.
   */
  it('el contador ve el calendario de un independiente', () => {
    expect(tipoParaCalendario('contador')).toBe('independiente');
  });

  it.each(CONTRIBUYENTES)('%s conserva su propio calendario', (tipo) => {
    expect(tipoParaCalendario(tipo)).toBe(tipo);
  });

  // Comportamiento previo a E-01 (`profile.contributorType || 'independiente'`),
  // fijado para que el arreglo del 400 no cambie de paso el perfil incompleto.
  it('un perfil sin tipo sigue cayendo en independiente', () => {
    expect(tipoParaCalendario(null)).toBe('independiente');
  });

  it('nunca devuelve un tipo que el endpoint rechace con 400', () => {
    const validos = CONTRIBUYENTES;
    const todos: (ContributorType | null)[] = ['contador', ...CONTRIBUYENTES, null];
    for (const tipo of todos) {
      expect(validos).toContain(tipoParaCalendario(tipo));
    }
  });
});
