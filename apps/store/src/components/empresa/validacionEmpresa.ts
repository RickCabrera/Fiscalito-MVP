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

import type { ParametrosSalariales } from '../../services/carteraApi';

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
  guia?: string;
  primaPct?: string;
}

/**
 * Qué está mal, con el motivo.
 *
 * Se valida **en pantalla además de en el motor**, y no es redundancia: un
 * error que sólo rebota tres pantallas después, cuando el operador ya se fue a
 * calcular la nómina, es un error que nadie relaciona con lo que capturó.
 */
export function validar(
  razonSocial: string,
  rfc: string,
  rp: string,
  primaPct: string,
  guia = '',
): Errores {
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
  // O-cierre: el backend la declara `^\d{0,5}$` y ninguna de las dos pantallas
  // que la capturan lo espejaba — mismo caso que el techo de vacaciones. Un 422
  // sobre la guía, tres pantallas después, no lo relaciona nadie con lo que
  // tecleó aquí.
  if (guia.trim() !== '' && !/^\d{1,5}$/.test(guia.trim())) {
    e.guia =
      'La guía de la subdelegación son hasta 5 dígitos, sin letras ni guiones. La asigna ' +
      'el IMSS.';
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

// ── O-03 · Parámetros salariales ──────────────────────────────────────────

/**
 * Las periodicidades que la app puede calcular.
 *
 * Son las cuatro claves de `c_PeriodicidadPago` con tarifa publicada en el
 * Anexo 8. **Catorcenal (03) y decenal (10) no están, y no es un olvido**: el
 * Anexo 8 no publica la de 14 días y la de 10 no se pudo verificar contra
 * fuente al construir `tablas_isr_periodicas.py` (§D10). El motor las rechaza
 * con su propio motivo; ofrecerlas aquí sería prometer un cálculo que después
 * no se puede hacer.
 *
 * La diaria (01) tampoco se ofrece: el enunciado de O-03 pide
 * semanal/quincenal/mensual, y una nómina diaria no es un caso de esta empresa.
 */
export const PERIODICIDADES = [
  { clave: '02', nombre: 'Semanal' },
  { clave: '04', nombre: 'Quincenal' },
  { clave: '05', nombre: 'Mensual' },
];

/**
 * Días de vacaciones que marca el Art. 76 LFT — **sólo para ETIQUETAR el
 * formulario**, nunca para calcular.
 *
 * Es una copia de `dias_vacaciones_de_ley` de `nomina_engine/integracion.py`, y
 * eso normalmente sería una segunda verdad. Se acepta acotada a este uso por
 * una razón concreta: el campo dice "Días (ley: 16)" mientras el operador
 * teclea, y pedirle ese número al backend con cada pulsación sería un request
 * por tecla para pintar una etiqueta.
 *
 * **Lo que sí calcula el backend, siempre**: los días que de verdad se aplican
 * (`dias_vacaciones_aplicados` de `POST /nomina/sbc`) y el rechazo de una tabla
 * bajo el mínimo. Si esta copia divergiera, la etiqueta se vería mal — pero
 * ningún SBC saldría distinto, que es la línea que importa no cruzar.
 */
export function diasDeLey(aniosCumplidos: number): number {
  if (aniosCumplidos < 0) return 0;
  if (aniosCumplidos <= 1) return 12;
  if (aniosCumplidos <= 5) return 12 + 2 * (aniosCumplidos - 1);
  const quinquenios = Math.ceil((aniosCumplidos - 5) / 5);
  return 20 + 2 * quinquenios;
}

/**
 * Qué está mal en los parámetros, con el motivo y el fundamento.
 *
 * Se valida en pantalla **además** de en el motor, y no es redundancia: un
 * aguinaldo de 10 días capturado en el formulario debe rebotar ahí, no tres
 * pantallas después cuando el operador ya se fue a calcular la nómina. El
 * motor sigue siendo la autoridad y vuelve a rechazarlo.
 */
/**
 * Techo de días de vacaciones, espejo de `MAXIMO_DIAS_VACACIONES` del motor
 * (`apps/api/app/nomina_engine/vacaciones.py`). No es una regla de ley —la LFT
 * sólo pone pisos— sino una guarda contra el dedazo, y por eso el mensaje lo
 * dice así.
 */
export const MAXIMO_DIAS_VACACIONES = 60;

export function erroresDeParametros(p: ParametrosSalariales): string[] {
  const errores: string[] = [];

  if (!Number.isFinite(p.dias_aguinaldo) || p.dias_aguinaldo < 15) {
    errores.push(
      'El aguinaldo mínimo de ley son 15 días (Art. 87 LFT). Menos subintegraría el ' +
        'SBC y con él todas las cuotas.',
    );
  }
  const prima = Number(p.prima_vacacional);
  if (!Number.isFinite(prima) || prima < 0.25) {
    errores.push('La prima vacacional mínima de ley es 25 % (Art. 80 LFT).');
  } else if (prima > 1) {
    errores.push('La prima vacacional no puede pasar del 100 %.');
  }

  for (const [anios, dias] of p.tabla_vacaciones) {
    const minimo = diasDeLey(anios);
    if (dias < minimo) {
      errores.push(
        `La tabla da ${dias} días al año ${anios} y el mínimo de ley son ${minimo} ` +
          '(Art. 76 LFT). Se pueden dar más, nunca menos.',
      );
    }
    // O-cierre: el motor acota arriba en 60 (`MAXIMO_DIAS_VACACIONES`) y esta
    // pantalla no lo hacía: se guardaba una tabla con 200 días y el 422 llegaba
    // después, al integrar el SBC, sobre un campo que el operador ya había dado
    // por bueno. O-03 puso las dos validaciones en espejo a propósito; este
    // borde se había quedado fuera del espejo.
    if (dias > MAXIMO_DIAS_VACACIONES) {
      errores.push(
        `La tabla da ${dias} días al año ${anios}, y el máximo que acepta el motor son ` +
          `${MAXIMO_DIAS_VACACIONES}. Más que eso suele ser un dedazo, no una prestación.`,
      );
    }
  }

  if (p.horario.dias_laborables.length === 0) {
    errores.push(
      'Tiene que haber al menos un día laborable: sin ninguno, el cierre no marcaría ' +
        'una sola falta y la nómina saldría completa siempre.',
    );
  }
  if (p.horario.hora_salida <= p.horario.hora_entrada) {
    errores.push('La hora de salida tiene que ser posterior a la de entrada.');
  }

  return errores;
}
