import { describe, expect, it } from 'vitest';

/** Guardia del propio setup: si alguien afloja la red, esto se cae. */
describe('red cerrada por default', () => {
  it('fetch lanza si el test no la stubbea a proposito', () => {
    // La guardia lanza de forma sincrona, no devuelve una promesa rechazada:
    // asi el test que se olvido de stubbear la red falla de inmediato.
    expect(() => fetch('https://api.openai.com/v1/chat/completions')).toThrow(
      /red bloqueada/i,
    );
  });

  it('XMLHttpRequest lanza al construirse', () => {
    expect(() => new XMLHttpRequest()).toThrow(/red bloqueada/i);
  });
});
