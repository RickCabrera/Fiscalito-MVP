/**
 * CLABE interbancaria y celular E.164 mexicano (P4-12, P4-13), para dar respuesta al teclear.
 *
 * MISMO CRITERIO QUE `apps/api/app/dispersion/clabe.py` y
 * `apps/api/app/schemas/empleado_pago.py`, que son la autoridad: el backend rechaza lo que
 * no pase. El vector de casos de `clabe.test.ts` es el mismo que el de
 * `apps/api/tests/plan_p/test_dispersion.py`, para que divergir rompa una prueba.
 *
 * Dígito verificador (Banxico): los primeros 17 dígitos por 3, 7, 1, 3, 7, 1…; de cada
 * producto se toma el dígito de las unidades, se suman, y el verificador es
 * (10 − suma mod 10) mod 10.
 */

const FACTORES = [3, 7, 1];

export function digitoVerificador(primeros17: string): number {
  let suma = 0;
  for (let i = 0; i < 17; i += 1) suma += (Number(primeros17[i]) * FACTORES[i % 3]) % 10;
  return (10 - (suma % 10)) % 10;
}

/** `null` si la CLABE es válida (o está vacía); si no, por qué. */
export function motivoClabeInvalida(clabe: string): string | null {
  const limpio = clabe.replace(/\s/g, '');
  if (limpio === '') return null;
  if (!/^\d+$/.test(limpio)) return 'La CLABE sólo lleva dígitos.';
  if (limpio.length !== 18) return `La CLABE son 18 dígitos y llevas ${limpio.length}.`;
  const esperado = digitoVerificador(limpio.slice(0, 17));
  if (Number(limpio[17]) !== esperado) {
    return `El dígito verificador no cuadra (debería terminar en ${esperado}): revisa que no haya un dígito tecleado mal.`;
  }
  return null;
}

/** Normaliza a `+52` + 10 dígitos; `null` si no se puede. Vacío se queda vacío. */
export function normalizarCelular(valor: string): string | null {
  const limpio = valor.replace(/[\s\-().]/g, '');
  if (limpio === '') return '';
  if (/^\d{10}$/.test(limpio)) return `+52${limpio}`;
  if (/^52\d{10}$/.test(limpio)) return `+${limpio}`;
  if (/^\+521\d{10}$/.test(limpio)) return `+52${limpio.slice(4)}`;
  if (/^\+52\d{10}$/.test(limpio)) return limpio;
  return null;
}

/** Lo mínimo de la ficha que esto valida (sin depender del modelo completo). */
export interface DatosPagoContacto {
  clabe?: string;
  numero_cuenta?: string;
  correo?: string;
  celular?: string;
  consentimiento_whatsapp?: boolean;
}

/** El primer problema de los datos de pago y contacto, o `null`. Bloquea guardar. */
export function errorPagoContacto(d: DatosPagoContacto): string | null {
  const clabe = motivoClabeInvalida(d.clabe ?? '');
  if (clabe) return clabe;
  const cuenta = (d.numero_cuenta ?? '').trim();
  if (cuenta && !/^(\d{10,12}|\d{16})$/.test(cuenta)) {
    return 'La cuenta son 10 a 12 dígitos (o 16 si es tarjeta).';
  }
  const correo = (d.correo ?? '').trim();
  if (correo && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(correo)) return 'El correo no tiene forma de correo.';
  const celular = normalizarCelular(d.celular ?? '');
  if (celular === null) return 'El celular va con +52 y 10 dígitos (p. ej. +525512345678).';
  if (d.consentimiento_whatsapp && !celular) return 'El consentimiento de WhatsApp necesita un celular.';
  return null;
}

/** Nombre corto de los bancos más comunes por su clave c_Banco (= clave ABM de la CLABE). */
export const BANCOS: Record<string, string> = {
  '002': 'Banamex', '012': 'BBVA', '014': 'Santander', '021': 'HSBC', '030': 'BanBajío',
  '036': 'Inbursa', '044': 'Scotiabank', '058': 'Banregio', '062': 'Afirme', '072': 'Banorte',
  '127': 'Azteca', '137': 'BanCoppel', '646': 'STP',
};
