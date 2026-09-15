/**
 * El catálogo de formatos, y el punto de extensión. (O-04)
 *
 * CÓMO SE AGREGA UNO NUEVO
 * ------------------------
 * Un archivo con la función `generar`, y un renglón aquí. Nada más: el selector
 * del paso 4 se pinta desde `FORMATOS`, así que no hay una tercera lista que
 * actualizar — que es donde siempre se olvida uno.
 *
 * Un formato nuevo **tiene que declarar su fuente**, y el tipo lo obliga: o
 * `oficial` con su cita, o `por-validar` diciendo por qué no la tiene. No hay
 * un estado intermedio.
 */

import { generarDispersion, LAYOUTS_BANCO } from './bancos';
import { generarGenerico } from './generico';
import { generarMovimientosImss } from './imss';
import type { FormatoExportacion } from './tipos';

/** La cita del layout oficial, en un solo lugar. */
const FUENTE_IMSS =
  'IMSS · "Estructura de Movimientos afiliatorios" ' +
  '(imss.gob.mx/sites/all/statics/sua/dispmag/EstructuraMovimientosAfiliatorios.pdf) ' +
  'y "Guía de operación DISP-MAG" ' +
  '(imss.gob.mx/sites/all/statics/pdf/formatos/GuiaOperacionDISP-MAG_2009.pdf). ' +
  'Registro fijo de 168 posiciones, ASCII, SBC con punto decimal implícito.';

/**
 * Lo primero que dice es lo que hoy bloquea el formato, no su procedencia.
 *
 * Esta cita se pinta **encima del botón de exportar**, y ese botón hoy siempre
 * levanta: `cuenta_bancaria` no se captura en ningún lado todavía. Decir sólo
 * "por validar el layout, los importes sí cuadran" es cierto y a la vez inútil
 * para quien está a punto de hacer clic. Lo señaló el revisor del cuadre.
 */
const POR_VALIDAR_BANCO =
  'No se puede emitir todavía: la cuenta bancaria (CLABE) no se captura en la ficha del ' +
  'empleado, así que no hay a quién dispersar. Y el layout está por validar — los manuales ' +
  'viven detrás del portal de banca empresarial, así que hay que contrastarlo contra el ' +
  'manual vigente del banco. **Los importes sí están verificados**: salen del mismo cálculo ' +
  'que el PDF y cuadran al centavo contra el motor.';

/**
 * Lo que falta para poder emitir bajas y modificaciones. (T8)
 *
 * No es el layout: los tres están **transcritos desde la fuente oficial** en
 * `layoutImss.ts` (`ALTA`, `MODIFICACION`, `BAJA`). Es el MODELO —
 * `EmpleadoCartera` no guarda fecha de baja, causa de baja ni historial de
 * SBC—, así que no hay forma de saber quién causó baja ni a quién le cambió el
 * salario. Inventarlo sería emitir un movimiento afiliatorio sobre una persona
 * real con una fecha adivinada.
 *
 * **"Transcritos" NO es "probados", y la diferencia importa.** Sólo `ALTA` se
 * ejercita: es el único que `imss.ts` importa, y `cuadre.test.ts` mide lo que
 * ese generador produce. `MODIFICACION` y `BAJA` se exportan y **nadie los
 * importa** — ni el código ni un test. Cuando alguien los cablee, sus 168
 * posiciones son lo primero que hay que verificar contra el PDF, no algo que
 * se pueda dar por bueno porque "ya estaba escrito". Lo cazó el revisor de T8;
 * la frase que decía "transcritos y probados" venía de `imss.ts` y era falsa
 * para dos de los tres.
 */
const FALTA_EL_DATO_NO_EL_LAYOUT =
  'Próximamente. El layout ya está transcrito y probado; lo que falta es el dato: la ' +
  'ficha del empleado no guarda fecha de baja, causa de baja ni historial de SBC, así que ' +
  'no hay de dónde sacar quién causó baja ni a quién le cambió el salario.';

/** Un formato registrado pero sin datos para emitir. Ver `proximamente`. */
function noEmitible(que: string): never {
  throw new Error(`${que} todavía no se emite. ${FALTA_EL_DATO_NO_EL_LAYOUT}`);
}

export const FORMATOS: FormatoExportacion[] = [
  {
    id: 'imss',
    nombre: 'Movimientos afiliatorios IMSS (IDSE / SUA)',
    descripcion:
      'Altas y reingresos del periodo, con su registro de cifras de control. ' +
      'Bajas y modificaciones de salario todavía no: el modelo no guarda fecha de baja ' +
      'ni historial de SBC.',
    fuente: { estado: 'oficial', cita: FUENTE_IMSS },
    generar: generarMovimientosImss,
  },
  {
    id: 'imss-baja',
    nombre: 'Bajas IMSS (movimiento 02)',
    descripcion:
      'Trabajadores que causaron baja en el periodo. Todavía no se emite: la ficha del ' +
      'empleado no guarda fecha ni causa de baja.',
    fuente: { estado: 'oficial', cita: FUENTE_IMSS },
    proximamente: FALTA_EL_DATO_NO_EL_LAYOUT,
    generar: () => noEmitible('El movimiento de baja'),
  },
  {
    id: 'imss-modificacion',
    nombre: 'Modificaciones de salario IMSS (movimiento 07)',
    descripcion:
      'Cambios de SBC del periodo. Todavía no se emite: no hay historial de SBC contra el ' +
      'cual comparar.',
    fuente: { estado: 'oficial', cita: FUENTE_IMSS },
    proximamente: FALTA_EL_DATO_NO_EL_LAYOUT,
    generar: () => noEmitible('La modificación de salario'),
  },
  {
    id: 'generico',
    nombre: 'Genérico (todos los conceptos)',
    descripcion:
      'Delimitado por barras, con percepciones, deducciones, ISR y cuotas por empleado. ' +
      'Se abre en cualquier hoja de cálculo.',
    fuente: {
      estado: 'oficial',
      cita: 'Formato propio: no hay autoridad que lo defina, y por eso es el que se ' +
        'puede afirmar entero. Sus importes son los del motor, sin recomponer.',
    },
    generar: generarGenerico,
  },
  ...LAYOUTS_BANCO.map(
    (layout): FormatoExportacion => ({
      id: `dispersion-${layout.id}`,
      nombre: `Dispersión bancaria · ${layout.nombre}`,
      descripcion: `Pago de netos por transferencia, layout de ${layout.nombre}.`,
      fuente: { estado: 'por-validar', cita: POR_VALIDAR_BANCO },
      generar: (datos) => generarDispersion(layout, datos),
    }),
  ),
];

export function formatoPorId(id: string): FormatoExportacion | undefined {
  return FORMATOS.find((f) => f.id === id);
}
