/**
 * Volver a integrar el SBC de la plantilla ya dada de alta. (O-cierre)
 *
 * EL DEFECTO QUE ESTO CIERRA
 * --------------------------
 * O-03 abrió un formulario para cambiar el aguinaldo, la prima vacacional y la
 * tabla de vacaciones, y prometió —con razón— que esos valores "alimentan el
 * factor de integración y el SBC". Para la plantilla que **ya existe**, no lo
 * hacían.
 *
 * `ModalEmpleado` es el único lugar de producción que llama a `integrarSBC` y
 * el único que escribe `salario_diario_integrado`; `plantillaDeNomina` manda al
 * motor el SDI guardado, y el motor **no lo recalcula** por decisión bien
 * fundada (§D9: el SDI es dato de entrada). Así que el patrón subía el
 * aguinaldo de 15 a 30 días, guardaba, corría la nómina, y las cuotas salían
 * sobre el SBC viejo — **subintegradas, en silencio**, que es la dirección que
 * este repo trata como la mala en todos lados.
 *
 * Lo encontró el revisor de cierre de la corrida O.
 *
 * NO SE HACE SOLO, Y ES A PROPÓSITO
 * ----------------------------------
 * Reintegrar toca el SBC de **toda** la plantilla, y subir el SBC de un
 * trabajador es un **movimiento 07 (modificación de salario) ante el IMSS** por
 * cada uno. Dispararlo como efecto de guardar un formulario escondería eso.
 * Aquí se calcula, se enseña quién cambia y de cuánto a cuánto, y **el operador
 * decide**. La misma política que `sembrar()` de la cartera.
 *
 * EL FACTOR LO CALCULA EL MOTOR, UNO POR UNO
 * -------------------------------------------
 * No se reproduce el Art. 27 en el front, ni siquiera para "adivinar" quién
 * cambió: se le pregunta al motor por cada empleado, porque la antigüedad
 * cumplida mueve los días de vacaciones y con ellos el factor. Un atajo que
 * calculara el factor una vez y lo aplicara a todos daría mal a quien acaba de
 * cumplir años de servicio.
 *
 * EL PARÁMETRO DEL PATRÓN ES UN **PISO**, NO UN REEMPLAZO (§D28)
 * --------------------------------------------------------------
 * Cada empleado guarda sus propias `prestaciones`, y `ModalEmpleado` las pinta
 * **editables**: se siembran del patrón al dar de alta y se pueden pisar para un
 * caso particular. La primera versión de este módulo las ignoraba y le aplicaba
 * a todos los del patrón — y eso le **bajaba** el SBC al trabajador con 30 días
 * de aguinaldo negociados en una empresa que da 15, y lo **guardaba**: la
 * subintegración que este módulo venía a cerrar, sólo que ahora escrita. Lo cazó
 * el revisor de cierre.
 *
 * Se integra con `max(patrón, ficha)`. Así **sube** con el patrón —que es para
 * lo que existe el formulario de O-03— y **no le baja a nadie**. El fundamento:
 * la política del patrón es una prestación mínima general y el contrato
 * individual puede mejorarla, no empeorarla (Arts. 33 y 56 LFT, derechos
 * adquiridos).
 *
 * Y como red final: si el SBC nuevo resultara **menor** que el guardado, **no se
 * escribe**. Sale en `bajarian` para que lo mire una persona. Bajar un SBC en
 * lote, desde una pantalla, sin que nadie lo vea, no.
 *
 * **DECISIÓN PROVISIONAL (nocturno):** cuál de las dos lecturas manda depende de
 * si Orca tiene gente con prestaciones por encima de la política de la empresa.
 * Ver `docs/decisiones-nomina.md` §D28. Esto es la conservadora.
 */

import {
  integrarSBC,
  type EmpleadoCartera,
  type ParametrosSalariales,
} from './carteraApi';

/** Qué le pasó al SBC de un empleado. */
export interface CambioDeSBC {
  empleadoNo: string;
  nombre: string;
  anterior: string;
  nuevo: string;
  /** `true` cuando el motor no pudo integrarlo; el SBC se deja como estaba. */
  fallo?: string;
}

export interface ResultadoReintegracion {
  /** Los que SUBEN de SBC. Son los que se guardan. */
  cambios: CambioDeSBC[];
  /**
   * Los que BAJARÍAN de SBC. **No se guardan.**
   *
   * Bajar el SBC de alguien en lote y en silencio es lo contrario de lo que
   * este módulo existe para evitar. Se reportan para que una persona decida.
   */
  bajarian: CambioDeSBC[];
  /** Los que el motor no pudo integrar. No se tocan. */
  fallidos: CambioDeSBC[];
  /** La plantilla completa, con el SDI nuevo donde lo hubo. */
  empleados: EmpleadoCartera[];
  revisados: number;
}

/**
 * La mayor de dos primas vacacionales, comparadas como número.
 *
 * Viajan como cadenas decimales (`'0.25'`) porque el backend las guarda así.
 * Se devuelve la **cadena original**, no el número: reconstruirla metería
 * `0.25` → `'0.25'` bien, pero `0.30` → `'0.3'`, y el motor recibe un formato
 * distinto del que la app guarda.
 */
export function mayorPrima(a: string, b: string): string {
  return Number(b) > Number(a) ? b : a;
}

/** Años de servicio cumplidos a la fecha, o 0 si no hay fecha de alta. */
export function antiguedadCumplida(fechaAlta: string | null, hoy: Date): number {
  if (!fechaAlta) return 0;
  const alta = new Date(`${fechaAlta}T00:00:00`);
  if (Number.isNaN(alta.getTime())) return 0;
  let anios = hoy.getFullYear() - alta.getFullYear();
  const cumpleEsteAnio = new Date(hoy.getFullYear(), alta.getMonth(), alta.getDate());
  if (hoy < cumpleEsteAnio) anios -= 1;
  return Math.max(0, anios);
}

/**
 * Recalcula el SBC de cada empleado con los parámetros vigentes.
 *
 * **No escribe nada.** Devuelve la plantilla nueva y el reporte; guardar es
 * decisión de quien llama, que es lo que permite enseñar el cambio antes de
 * aplicarlo.
 */
export async function reintegrarPlantilla(
  empleados: EmpleadoCartera[],
  parametros: ParametrosSalariales,
  hoy: Date = new Date(),
): Promise<ResultadoReintegracion> {
  const fecha = hoy.toISOString().slice(0, 10);
  const cambios: CambioDeSBC[] = [];
  const bajarian: CambioDeSBC[] = [];
  const fallidos: CambioDeSBC[] = [];
  const nuevos: EmpleadoCartera[] = [];

  for (const empleado of empleados) {
    const anterior = empleado.salario_diario_integrado;
    try {
      const r = await integrarSBC({
        salario_diario: empleado.salario_diario,
        fecha,
        zona: empleado.zona,
        anios_servicio_cumplidos: antiguedadCumplida(empleado.fecha_alta, hoy),
        // El piso, no el reemplazo. Ver §D28 y el encabezado.
        dias_aguinaldo: Math.max(
          parametros.dias_aguinaldo,
          empleado.prestaciones.dias_aguinaldo,
        ),
        prima_vacacional: mayorPrima(
          parametros.prima_vacacional,
          empleado.prestaciones.prima_vacacional,
        ),
        // Los días de vacaciones sí son del empleado: `0` significa "los de
        // ley", que la tabla del patrón resuelve por antigüedad. Un `max` aquí
        // convertiría ese centinela en un número y rompería la escala.
        dias_vacaciones: empleado.prestaciones.dias_vacaciones,
        tabla_vacaciones: parametros.tabla_vacaciones,
      });
      const registro = {
        empleadoNo: empleado.empleado_no,
        nombre: empleado.nombre,
        anterior,
        nuevo: r.sbc,
      };
      if (r.sbc === anterior) {
        nuevos.push(empleado);
      } else if (Number(r.sbc) < Number(anterior)) {
        // NO se escribe. Con el piso esto debería ser rarísimo —lo produciría
        // un cambio de la tabla de vacaciones o del salario diario—, y
        // precisamente por raro merece que lo mire alguien.
        bajarian.push(registro);
        nuevos.push(empleado);
      } else {
        cambios.push(registro);
        nuevos.push({ ...empleado, salario_diario_integrado: r.sbc });
      }
    } catch (e) {
      // Un empleado que el motor rechaza se deja EXACTAMENTE como estaba. Una
      // plantilla a medio reintegrar, con unos al valor nuevo y otros al viejo
      // y nadie avisado, es peor que no haber reintegrado.
      fallidos.push({
        empleadoNo: empleado.empleado_no,
        nombre: empleado.nombre,
        anterior,
        nuevo: anterior,
        fallo: e instanceof Error ? e.message : 'No se pudo integrar',
      });
      nuevos.push(empleado);
    }
  }

  return { cambios, bajarian, fallidos, empleados: nuevos, revisados: empleados.length };
}
