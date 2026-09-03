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

const POR_VALIDAR_BANCO =
  'Sin fuente publicada: los manuales de dispersión viven detrás del portal de banca ' +
  'empresarial. La estructura es la habitual del banco y hay que contrastarla contra su ' +
  'manual vigente antes de usarla. **Los importes sí están verificados**: salen del mismo ' +
  'cálculo que el PDF y cuadran al centavo contra el motor.';

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
