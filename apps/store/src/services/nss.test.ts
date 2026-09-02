/**
 * Vector de casos del NSS. (R-03)
 *
 * **Este vector es compartido con el backend.** Cuando R-07 agregue el
 * validador de pydantic, sus casos tienen que ser éstos mismos: son dos
 * implementaciones del mismo algoritmo —una para dar respuesta al teclear y
 * otra para ser la autoridad del contrato— y divergir tiene que romper un test,
 * no pasar callado. Si agregas un caso aquí, agrégalo allá.
 */

import { describe, expect, it } from 'vitest';
import {
  digitoVerificador,
  normalizarNSS,
  nssPorVerificar,
  validarNSS,
  BLOQUEA_VERIFICADOR,
} from './nss';

/**
 * NSS **sintéticos**, construidos con el algoritmo, no tomados de nadie.
 * La regla del repo aplica también a los tests: un NSS bien formado es el NSS
 * de alguien, así que estos salen de payloads obviamente artificiales.
 */
const VALIDOS = [
  '12345678903', // el ejemplo canónico, verificado a mano en el docstring
  // NO es un artefacto: es el único vector que fija el módulo EXTERNO de
  // `(10 - (suma % 10)) % 10`. Sin ese `% 10` final, `digitoVerificador`
  // devolvería 10 para un payload cuya suma es múltiplo de 10.
  '00000000000',
  '11111111115', // payload de unos: 5 duplicados (2 c/u) + 5 sueltos = 15 -> 5
];

describe('digitoVerificador (Luhn)', () => {
  it('reproduce el ejemplo canónico calculado a mano', () => {
    // 22 (duplicados) + 25 (sin duplicar) = 47 -> (10 - 7) % 10 = 3
    expect(digitoVerificador('1234567890')).toBe(3);
  });

  it.each([
    // ANCLAS EXTERNAS. El test de propiedad de abajo construye el número CON
    // `digitoVerificador` y luego lo verifica con la misma función: no puede
    // detectar un algoritmo equivocado, sólo una inconsistencia consigo mismo.
    // Estos son números Luhn-válidos publicados fuera de este repo, así que
    // anclan la PARIDAD —qué posiciones se duplican—, que es donde este
    // algoritmo se implementa mal más a menudo.
    ['7992739871', 3],
    ['411111111111111', 1],
    ['550000555555555', 9],
    ['37828224631000', 5],
    ['453957876362148', 6],
  ])('coincide con un número Luhn publicado: %s -> %i', (payload, esperado) => {
    expect(digitoVerificador(payload)).toBe(esperado);
  });

  it('el dígito que calcula siempre cierra el Luhn del número completo', () => {
    // Propiedad, no ejemplo: para cualquier payload, payload+digito debe validar.
    for (let n = 0; n < 200; n += 7) {
      const payload = String(n).padStart(10, '0');
      const completo = payload + String(digitoVerificador(payload));
      expect(validarNSS(completo).gravedad, completo).toBe('ok');
    }
  });
});

describe('normalizarNSS', () => {
  it('deja sólo dígitos: se captura con espacios y guiones y eso no es un error', () => {
    expect(normalizarNSS('12-34 5678 903')).toBe('12345678903');
  });
});

describe('validarNSS', () => {
  it('vacío es VÁLIDO: el campo es opcional y es la salida del contador', () => {
    // No es un detalle: es lo que hace seguro bloquear por longitud. Sin esta
    // salida, un NSS raro dejaría al contador sin forma de guardar al empleado.
    expect(validarNSS('').gravedad).toBe('ok');
    expect(validarNSS('   ').gravedad).toBe('ok');
    expect(validarNSS('').puedeGuardar).toBe(true);
  });

  it.each(VALIDOS)('acepta un NSS bien formado: %s', (nss) => {
    const r = validarNSS(nss);
    expect(r.gravedad).toBe('ok');
    expect(r.puedeGuardar).toBe(true);
    expect(r.motivo).toBeNull();
  });

  it('acepta el mismo NSS con separadores', () => {
    expect(validarNSS('12 34 56 78 903').gravedad).toBe('ok');
  });

  describe('longitud: BLOQUEA', () => {
    it.each([
      ['1234567890', 10],
      ['123456789034', 12],
      ['1', 1],
    ])('rechaza %s (%i dígitos)', (nss) => {
      const r = validarNSS(nss);
      expect(r.gravedad).toBe('error');
      expect(r.puedeGuardar).toBe(false);
    });

    it('el mensaje CIERRA EL ATAJO, no sólo describe el error', () => {
      // Sin esta frase el contador con 10 dígitos calcula el onceavo a mano, que
      // es exactamente el dato inventado que R-03 no quiere producir. Si alguien
      // "simplifica" el mensaje, este test lo detiene.
      const motivo = validarNSS('1234567890').motivo ?? '';
      expect(motivo).toMatch(/no lo completes a mano/i);
      expect(motivo).toMatch(/déjalo vacío/i);
    });

    it('la explicación de la asignación antigua sólo sale con 10 dígitos', () => {
      // Incondicional, le decía "un número de 10 dígitos es..." a quien capturó
      // 13. Y va en potencial: `nss.ts` declara que no hay norma publicada, así
      // que no puede afirmarlo como hecho en la UI.
      expect(validarNSS('1234567890').motivo).toMatch(/suele ser una asignación previa/);
      expect(validarNSS('123456789034').motivo).not.toMatch(/asignación previa/);
      expect(validarNSS('123456789034').motivo).toMatch(/Sobran 1\./);
    });

    it('texto sin un solo dígito es error, no "vacío"', () => {
      // Tratarlo como vacío guardaría basura en silencio.
      const r = validarNSS('no me lo sé');
      expect(r.gravedad).toBe('error');
      expect(r.puedeGuardar).toBe(false);
    });
  });

  describe('dígito verificador: ADVIERTE y deja guardar', () => {
    // `12345678903` es el válido; cualquier otro último dígito no casa.
    const malos = ['12345678900', '12345678901', '12345678909'];

    it.each(malos)('marca %s como advertencia', (nss) => {
      const r = validarNSS(nss);
      expect(r.gravedad).toBe('advertencia');
      expect(nssPorVerificar(nss)).toBe(true);
    });

    it('NO impide guardar, que es la desviación consciente del enunciado', () => {
      // Bloquear aquí empujaría al contador a teclear un NSS que pase Luhn, y
      // eso pondría un número INVENTADO junto a datos reales. Es la razón #1 del
      // encabezado de `nss.ts`; si alguien invierte la política sin querer, este
      // test lo caza.
      expect(BLOQUEA_VERIFICADOR).toBe(false);
      expect(validarNSS('12345678900').puedeGuardar).toBe(true);
    });

    it('el mensaje dice qué dígito esperaba, para que sea accionable', () => {
      const motivo = validarNSS('12345678900').motivo ?? '';
      expect(motivo).toContain('termina en 0');
      expect(motivo).toContain('da 3');
    });

    it('un NSS válido NO se marca por verificar', () => {
      // La aserción simétrica: sin ella, un `nssPorVerificar` que devolviera
      // siempre `true` pasaría los tres tests de arriba.
      expect(nssPorVerificar('12345678903')).toBe(false);
      expect(nssPorVerificar('')).toBe(false);
    });
  });
});
