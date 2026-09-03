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
  /** Sólo los que de verdad cambiaron de SBC. */
  cambios: CambioDeSBC[];
  /** Los que el motor no pudo integrar. No se tocan. */
  fallidos: CambioDeSBC[];
  /** La plantilla completa, con el SDI nuevo donde lo hubo. */
  empleados: EmpleadoCartera[];
  revisados: number;
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
        dias_aguinaldo: parametros.dias_aguinaldo,
        prima_vacacional: parametros.prima_vacacional,
        tabla_vacaciones: parametros.tabla_vacaciones,
      });
      if (r.sbc !== anterior) {
        cambios.push({
          empleadoNo: empleado.empleado_no,
          nombre: empleado.nombre,
          anterior,
          nuevo: r.sbc,
        });
      }
      nuevos.push({ ...empleado, salario_diario_integrado: r.sbc });
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

  return { cambios, fallidos, empleados: nuevos, revisados: empleados.length };
}
