/**
 * Validación y conversión de la Configuración de empresa. (O-01)
 *
 * VIVE APARTE DEL COMPONENTE por dos razones:
 *
 * 1. **Fast refresh de Vite** exige que un archivo de componentes exporte sólo
 *    componentes (`react-refresh/only-export-components`). Es el mismo motivo
 *    por el que `estilosCampo.ts` está separado de `Campo.tsx`.
 * 2. Se puede probar **sin jsdom**: los mínimos de ley son reglas, y una regla
 *    probada a través de un formulario se prueba peor.
 *
 * LA PRIMA SE CAPTURA EN PORCENTAJE Y SE GUARDA EN FRACCIÓN
 * ---------------------------------------------------------
 * El modelo la guarda como fracción (0.0054355), que es lo que espera el motor,
 * pero el patrón la recibe del IMSS en porcentaje (0.54355 %). Capturar en
 * fracción es cómo alguien teclea `5.4355` creyendo que pone el 5.4 % y
 * multiplica el ramo de Riesgos de Trabajo **por mil** sin que ninguna tabla lo
 * detecte. La conversión se hace aquí, en un solo lugar, y el backend vuelve a
 * acotar a [0.005, 0.150] (Arts. 72 y 73 LSS).
 */

/** Rango de la prima de RT en PORCENTAJE, el mismo que el motor acota en fracción. */
const PRIMA_MINIMA_PCT = 0.5;
const PRIMA_MAXIMA_PCT = 15;

export function aPorcentaje(fraccion: string): string {
  if (fraccion.trim() === '') return '';
  const n = Number(fraccion);
  if (!Number.isFinite(n)) return '';
  // `toFixed` fijo perdería dígitos: la prima del caso real es 1.13065 %.
  return String(Number((n * 100).toFixed(6)));
}

export function aFraccion(porcentaje: string): string {
  const n = Number(porcentaje);
  if (!Number.isFinite(n)) return '';
  return String(Number((n / 100).toFixed(8)));
}

interface Errores {
  razonSocial?: string;
  rfc?: string;
  registroPatronal?: string;
  primaPct?: string;
}

/**
 * Qué está mal, con el motivo.
 *
 * Se valida **en pantalla además de en el motor**, y no es redundancia: un
 * error que sólo rebota tres pantallas después, cuando el operador ya se fue a
 * calcular la nómina, es un error que nadie relaciona con lo que capturó.
 */
export function validar(razonSocial: string, rfc: string, rp: string, primaPct: string): Errores {
  const e: Errores = {};
  if (razonSocial.trim() === '') {
    e.razonSocial = 'La razón social es obligatoria: es lo que sale impreso en los recibos.';
  }
  if (rfc.trim() !== '' && rfc.trim().length !== 12 && rfc.trim().length !== 13) {
    e.rfc = 'El RFC de una persona moral son 12 caracteres y el de una física 13.';
  }
  if (rp.trim() !== '' && rp.trim().length !== 11) {
    e.registroPatronal =
      'El registro patronal son 11 caracteres: los 10 del registro más su dígito verificador.';
  }
  const n = Number(primaPct);
  if (primaPct.trim() === '') {
    e.primaPct = 'Sin la prima de riesgos de trabajo no se pueden calcular las cuotas patronales.';
  } else if (!Number.isFinite(n) || n < PRIMA_MINIMA_PCT || n > PRIMA_MAXIMA_PCT) {
    e.primaPct =
      `La prima va de ${PRIMA_MINIMA_PCT} % a ${PRIMA_MAXIMA_PCT} % (Arts. 72 y 73 LSS). ` +
      'Se captura en porcentaje: 0.54355, no 0.0054355.';
  }
  return e;
}
