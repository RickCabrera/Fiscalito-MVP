/**
 * Validación del Número de Seguridad Social del IMSS. (R-03)
 *
 * QUÉ ES EL DÍGITO VERIFICADOR, Y CON QUÉ AUTORIDAD SE AFIRMA
 * -----------------------------------------------------------
 * El NSS son 11 dígitos: 10 de payload y 1 verificador, calculado con el
 * **algoritmo de Luhn** (módulo 10, ISO/IEC 7812-1) — el mismo de las tarjetas
 * bancarias.
 *
 * Y aquí va la parte honesta, que no se esconde en un pie de página: **no hay
 * norma primaria del IMSS publicada que especifique este algoritmo.** Lo que
 * existe son fuentes secundarias. No es DOF, no es un anexo, no es un acuerdo.
 * Por eso este módulo **no cita "fuente oficial"**: cita lo que hay, que es un
 * algoritmo de dominio público, sin norma publicada y **sin validar con la
 * contadora** (`docs/decisiones-nomina.md`, §NSS).
 *
 * Comprobación aritmética del ejemplo canónico `12345678903`, para que quien
 * lea esto pueda verificar el algoritmo sin correr nada:
 *   payload `1234567890` → duplicando desde el último: 0,16,12,8,4 → 0,7,3,8,4 = 22
 *   sin duplicar: 9+7+5+3+1 = 25 · total 47 · verificador (10 − 47 mod 10) mod 10 = **3**
 *
 * POR QUÉ EL VERIFICADOR ADVIERTE Y NO BLOQUEA
 * ---------------------------------------------
 * El enunciado de R-03 decía "inválido bloquea". Se cumple para el formato y
 * **se desvía para el verificador**, con tres razones en orden de peso:
 *
 * 1. **Bloquear empuja a inventar.** Con el NSS real del trabajador en la mano
 *    y el modal rechazándolo, la salida obvia del contador es teclear uno que
 *    sí pase Luhn. Eso pondría un NSS **inventado** junto a datos reales —
 *    exactamente lo que `app/routes/despacho.py` argumenta que nunca debe pasar
 *    ("un NSS de 11 dígitos bien formado es el NSS de alguien"). Bloquear aquí
 *    construiría la presión que ese docstring existe para evitar.
 * 2. **Sería más estricto que el SAT, con la norma sin publicar de mi lado.**
 *    `apps/api/tests/xsd/nomina12.xsd` declara `NumSeguridadSocial` con
 *    `use="optional"` y patrón `[0-9]{1,15}`: el complemento de nómina se timbra
 *    sin exigir dígito verificador.
 * 3. Un mensaje de error bien redactado no arregla un rechazo indebido.
 *
 * La longitud sí bloquea, y la asimetría es deliberada: el patrón `[0-9]{1,15}`
 * es un sobre laxo de **serialización**, no una afirmación de que un NSS de 3
 * dígitos exista. Y con la longitud no hay ninguna transformación que "haga
 * pasar" el dato, así que no genera la presión del punto 1: el empujón natural
 * es ir a buscar el número bueno.
 *
 * **Lo que hace seguro bloquear por longitud es que vacío siempre guarda.** El
 * contador nunca queda acorralado: si tiene algo que no valida, lo deja en
 * blanco, que es literalmente la regla del repo — *vacío cuando no se conoce, y
 * nunca inventado*. Si esa salida desapareciera, este bloqueo tendría que
 * desaparecer con ella.
 *
 * Si Ricardo quiere el bloqueo duro, es la constante `BLOQUEA_VERIFICADOR`.
 */

/** Longitud del NSS moderno. Los 10 primeros son payload; el 11º, verificador. */
export const LARGO_NSS = 11;

/**
 * Si un verificador que no casa debe impedir el guardado.
 *
 * `false` a propósito — ver el encabezado. Es una constante y no una condición
 * repartida por el formulario justamente para que cambiar la política sea una
 * línea y no una cacería.
 */
export const BLOQUEA_VERIFICADOR = false;

export type GravedadNSS = 'ok' | 'advertencia' | 'error';

export interface ResultadoNSS {
  /** `error` impide guardar; `advertencia` no. `ok` incluye el vacío. */
  gravedad: GravedadNSS;
  /** `true` si el formulario puede guardar con este valor. */
  puedeGuardar: boolean;
  /** Qué decirle al contador. `null` cuando no hay nada que decir. */
  motivo: string | null;
}

const OK: ResultadoNSS = { gravedad: 'ok', puedeGuardar: true, motivo: null };

/** Deja sólo dígitos: se captura con espacios y guiones y eso no es un error. */
export function normalizarNSS(entrada: string): string {
  return (entrada ?? '').replace(/\D/g, '');
}

/**
 * El dígito verificador que le corresponde a un payload de 10 dígitos (Luhn).
 *
 * Se expone para que el mensaje pueda decir **cuál** esperaba, que es lo que
 * convierte "está mal" en algo accionable: casi siempre delata un dígito
 * tecleado de más o de menos.
 */
export function digitoVerificador(payload: string): number {
  let suma = 0;
  // Se recorre de derecha a izquierda. El último dígito del payload ocupa una
  // posición par contando desde el verificador, así que se duplica.
  for (let i = payload.length - 1, pos = 0; i >= 0; i -= 1, pos += 1) {
    let d = payload.charCodeAt(i) - 48;
    if (pos % 2 === 0) {
      d *= 2;
      if (d > 9) d -= 9;
    }
    suma += d;
  }
  return (10 - (suma % 10)) % 10;
}

/**
 * Valida un NSS capturado.
 *
 * **Vacío es válido**: el campo es opcional (el XSD del SAT lo declara
 * `use="optional"`, y la semilla del backend va vacía). Es la salida que hace
 * seguro bloquear por longitud, y no es un descuido.
 */
export function validarNSS(entrada: string): ResultadoNSS {
  const crudo = entrada ?? '';
  const digitos = normalizarNSS(crudo);

  if (digitos === '') {
    // Un campo con basura no numérica y cero dígitos no es "vacío": es un error
    // de captura, y tratarlo como vacío lo guardaría en silencio.
    if (crudo.trim() !== '') {
      return {
        gravedad: 'error',
        puedeGuardar: false,
        motivo: 'El NSS son 11 dígitos. Esto no tiene ninguno.',
      };
    }
    return OK;
  }

  if (digitos.length !== LARGO_NSS) {
    // El mensaje CIERRA EL ATAJO en vez de sólo describir el error. Sin la
    // segunda frase, el contador con un NSS de 10 dígitos calcula el onceavo a
    // mano — que es justo el dato inventado que no queremos.
    const falta = LARGO_NSS - digitos.length;
    const cuantos =
      falta > 0 ? `Faltan ${falta}.` : `Sobran ${-falta}.`;
    return {
      gravedad: 'error',
      puedeGuardar: false,
      motivo:
        `El NSS son ${LARGO_NSS} dígitos y capturaste ${digitos.length}. ${cuantos} ` +
        'Un número de 10 dígitos es una asignación previa al dígito verificador: ' +
        'pídelo actualizado, no lo completes a mano. Si no lo tienes, déjalo vacío.',
    };
  }

  const esperado = digitoVerificador(digitos.slice(0, LARGO_NSS - 1));
  const traido = digitos.charCodeAt(LARGO_NSS - 1) - 48;
  if (esperado !== traido) {
    return {
      gravedad: 'advertencia',
      puedeGuardar: !BLOQUEA_VERIFICADOR,
      motivo:
        `El dígito verificador no coincide: termina en ${traido} y el cálculo da ` +
        `${esperado}. Casi siempre es un dígito de más o de menos — revísalo. ` +
        'Se guarda de todos modos: el algoritmo del verificador no está publicado ' +
        'por el IMSS y el SAT timbra sin exigirlo, así que rechazar aquí un NSS ' +
        'bueno sería peor que guardarlo marcado.',
    };
  }

  return OK;
}

/** `true` si el formulario puede guardar con este NSS. Atajo para la UI. */
export function nssPuedeGuardarse(entrada: string): boolean {
  return validarNSS(entrada).puedeGuardar;
}

/** `true` si el NSS quedó guardado con el verificador en desacuerdo. */
export function nssPorVerificar(entrada: string): boolean {
  return validarNSS(entrada).gravedad === 'advertencia';
}
