/**
 * Definición de cada calculadora fiscal (P3-08): sus campos y qué renglones del
 * resultado se enseñan. El cálculo es del backend; aquí sólo hay formularios.
 */

import type { Calculadora } from '../../services/impuestosApi';

export type TipoCampo = 'dinero' | 'fecha' | 'entero' | 'texto' | 'opcion' | 'casilla';

export interface Campo {
  id: string;
  etiqueta: string;
  tipo: TipoCampo;
  defecto: string;
  opciones?: { valor: string; etiqueta: string }[];
}

export interface Salida {
  id: string;
  etiqueta: string;
  /** `true` = es el resultado principal, se pinta resaltado. */
  principal?: boolean;
}

export interface DefinicionCalculadora {
  id: Calculadora;
  titulo: string;
  descripcion: string;
  campos: Campo[];
  salidas: Salida[];
}

const HOY = new Date().toISOString().slice(0, 10);

const TIPOS_RECARGO = [
  { valor: 'mora', etiqueta: 'Mora (pago extemporáneo)' },
  { valor: 'prorroga', etiqueta: 'Prórroga' },
  { valor: 'parcialidades_12', etiqueta: 'Parcialidades hasta 12 meses' },
  { valor: 'parcialidades_24', etiqueta: 'Parcialidades 12 a 24 meses' },
  { valor: 'parcialidades_mas_24', etiqueta: 'Parcialidades más de 24 meses' },
];

const MODOS_FACTOR = [
  { valor: 'truncar', etiqueta: 'Truncar al diezmilésimo' },
  { valor: 'redondear', etiqueta: 'Redondear al diezmilésimo' },
  { valor: 'sin_redondeo', etiqueta: 'Sin cortar' },
];

export const CALCULADORAS: DefinicionCalculadora[] = [
  {
    id: 'actualizacion-recargos',
    titulo: 'Actualización y recargos',
    descripcion: 'Arts. 17-A y 21 CFF con el INPC del INEGI y la tasa de la LIF.',
    campos: [
      { id: 'monto', etiqueta: 'Contribución omitida', tipo: 'dinero', defecto: '' },
      { id: 'fecha_limite', etiqueta: 'Fecha en que debió pagarse', tipo: 'fecha', defecto: '' },
      { id: 'fecha_pago', etiqueta: 'Fecha de pago', tipo: 'fecha', defecto: HOY },
      { id: 'tipo_recargo', etiqueta: 'Tasa de recargos', tipo: 'opcion', defecto: 'mora', opciones: TIPOS_RECARGO },
      { id: 'modo_factor', etiqueta: 'Factor', tipo: 'opcion', defecto: 'truncar', opciones: MODOS_FACTOR },
    ],
    salidas: [
      { id: 'monto_actualizado', etiqueta: 'Monto actualizado' },
      { id: 'actualizacion', etiqueta: 'Actualización' },
      { id: 'meses', etiqueta: 'Meses de recargo' },
      { id: 'tasa_acumulada', etiqueta: 'Tasa acumulada' },
      { id: 'recargos', etiqueta: 'Recargos' },
      { id: 'total', etiqueta: 'Total', principal: true },
      { id: 'total_a_pagar_ajustado', etiqueta: 'A pagar (ajustado a pesos)' },
    ],
  },
  {
    id: 'isr-sueldos',
    titulo: 'ISR de sueldos',
    descripcion: 'Tarifa del Art. 96 LISR y subsidio para el empleo (motor de nómina).',
    campos: [
      { id: 'base_gravable', etiqueta: 'Base gravable del periodo', tipo: 'dinero', defecto: '' },
      {
        id: 'clave_periodicidad', etiqueta: 'Periodicidad', tipo: 'opcion', defecto: '05',
        opciones: [
          { valor: '01', etiqueta: 'Diaria' }, { valor: '02', etiqueta: 'Semanal' },
          { valor: '04', etiqueta: 'Quincenal' }, { valor: '05', etiqueta: 'Mensual' },
        ],
      },
      { id: 'dias_periodo', etiqueta: 'Días del periodo', tipo: 'entero', defecto: '30' },
      { id: 'fecha_pago', etiqueta: 'Fecha de pago', tipo: 'fecha', defecto: HOY },
    ],
    salidas: [
      { id: 'isr_causado', etiqueta: 'ISR causado' },
      { id: 'subsidio', etiqueta: 'Subsidio para el empleo' },
      { id: 'subsidio_acreditado', etiqueta: 'Subsidio acreditado' },
      { id: 'isr_retenido', etiqueta: 'ISR a retener', principal: true },
    ],
  },
  {
    id: 'isr-resico',
    titulo: 'ISR RESICO personas físicas',
    descripcion: 'Tasa mensual del Art. 113-E LISR sobre ingresos cobrados.',
    campos: [
      { id: 'ingresos_cobrados', etiqueta: 'Ingresos cobrados del mes (sin IVA)', tipo: 'dinero', defecto: '' },
      { id: 'isr_retenido', etiqueta: 'ISR retenido por personas morales', tipo: 'dinero', defecto: '0' },
    ],
    salidas: [
      { id: 'tasa', etiqueta: 'Tasa' },
      { id: 'isr_causado', etiqueta: 'ISR causado' },
      { id: 'isr_a_pagar', etiqueta: 'ISR a pagar', principal: true },
    ],
  },
  {
    id: 'aguinaldo',
    titulo: 'Aguinaldo',
    descripcion: 'Art. 87 LFT, exento hasta 30 UMA (Art. 93 fr. XIV LISR).',
    campos: [
      { id: 'salario_diario', etiqueta: 'Salario diario', tipo: 'dinero', defecto: '' },
      { id: 'dias_aguinaldo', etiqueta: 'Días de aguinaldo', tipo: 'entero', defecto: '15' },
      { id: 'dias_trabajados_en_el_anio', etiqueta: 'Días trabajados en el año', tipo: 'entero', defecto: '365' },
      { id: 'fecha_pago', etiqueta: 'Fecha de pago', tipo: 'fecha', defecto: HOY },
    ],
    salidas: [
      { id: 'importe', etiqueta: 'Aguinaldo' },
      { id: 'isr', etiqueta: 'ISR' },
      { id: 'neto', etiqueta: 'Neto', principal: true },
    ],
  },
  {
    id: 'ptu',
    titulo: 'PTU',
    descripcion: 'Arts. 123 y 127 LFT; exenta hasta 15 UMA.',
    campos: [
      { id: 'utilidad_repartible', etiqueta: 'Utilidad repartible', tipo: 'dinero', defecto: '' },
      { id: 'dias_trabajador', etiqueta: 'Días trabajados del trabajador', tipo: 'entero', defecto: '365' },
      { id: 'salario_trabajador', etiqueta: 'Salarios del trabajador en el año', tipo: 'dinero', defecto: '' },
      { id: 'total_dias_todos', etiqueta: 'Días de todos los trabajadores', tipo: 'entero', defecto: '' },
      { id: 'total_salarios_todos', etiqueta: 'Salarios de todos los trabajadores', tipo: 'dinero', defecto: '' },
      { id: 'salario_diario', etiqueta: 'Salario diario del trabajador', tipo: 'dinero', defecto: '' },
      { id: 'promedio_ptu_3_anios', etiqueta: 'Promedio PTU últimos 3 años', tipo: 'dinero', defecto: '0' },
      { id: 'fecha_pago', etiqueta: 'Fecha de pago', tipo: 'fecha', defecto: HOY },
    ],
    salidas: [
      { id: 'por_dias', etiqueta: 'Parte por días' },
      { id: 'por_salario', etiqueta: 'Parte por salarios' },
      { id: 'tope', etiqueta: 'Tope (Art. 127 fr. IX)' },
      { id: 'importe', etiqueta: 'PTU' },
      { id: 'isr', etiqueta: 'ISR' },
      { id: 'neto', etiqueta: 'Neto', principal: true },
    ],
  },
  {
    id: 'finiquito',
    titulo: 'Finiquito y liquidación',
    descripcion: 'Proporcionales, prima de antigüedad e indemnización con su ISR.',
    campos: [
      { id: 'salario_diario', etiqueta: 'Salario diario', tipo: 'dinero', defecto: '' },
      { id: 'fecha_ingreso', etiqueta: 'Fecha de ingreso', tipo: 'fecha', defecto: '' },
      { id: 'fecha_baja', etiqueta: 'Fecha de baja', tipo: 'fecha', defecto: HOY },
      { id: 'dias_vacaciones_pendientes', etiqueta: 'Vacaciones pendientes (días)', tipo: 'entero', defecto: '0' },
      { id: 'dias_pendientes_de_pago', etiqueta: 'Días de sueldo pendientes', tipo: 'entero', defecto: '0' },
      {
        id: 'tipo', etiqueta: 'Tipo', tipo: 'opcion', defecto: 'renuncia',
        opciones: [
          { valor: 'renuncia', etiqueta: 'Renuncia (finiquito)' },
          { valor: 'despido_injustificado', etiqueta: 'Despido injustificado (liquidación)' },
        ],
      },
    ],
    salidas: [
      { id: 'anios_servicio', etiqueta: 'Años de servicio' },
      { id: 'total_bruto', etiqueta: 'Total bruto' },
      { id: 'separacion_exento', etiqueta: 'Separación exenta' },
      { id: 'isr', etiqueta: 'ISR' },
      { id: 'neto', etiqueta: 'Neto', principal: true },
    ],
  },
  {
    id: 'isn',
    titulo: 'Impuesto sobre nóminas',
    descripcion: 'Tasa de la ley de hacienda de cada estado, con su fuente.',
    campos: [
      { id: 'entidad', etiqueta: 'Entidad (clave c_Estado)', tipo: 'texto', defecto: 'VER' },
      { id: 'total_erogaciones', etiqueta: 'Erogaciones gravadas del mes', tipo: 'dinero', defecto: '' },
      { id: 'fecha', etiqueta: 'Fecha', tipo: 'fecha', defecto: HOY },
      { id: 'aplicar_adicional', etiqueta: 'Aplicar adicional estatal', tipo: 'casilla', defecto: 'true' },
    ],
    salidas: [
      { id: 'tasa', etiqueta: 'Tasa' },
      { id: 'base', etiqueta: 'Base' },
      { id: 'impuesto', etiqueta: 'Impuesto' },
      { id: 'adicional', etiqueta: 'Adicional' },
      { id: 'total', etiqueta: 'Total', principal: true },
      { id: 'fundamento', etiqueta: 'Fundamento' },
    ],
  },
];

/** Convierte lo capturado al cuerpo del request (enteros y casillas con su tipo). */
export function cuerpoDe(def: DefinicionCalculadora, valores: Record<string, string>): Record<string, unknown> {
  const cuerpo: Record<string, unknown> = {};
  for (const c of def.campos) {
    const v = valores[c.id] ?? c.defecto;
    if (c.tipo === 'casilla') cuerpo[c.id] = v === 'true';
    else if (c.tipo === 'entero') cuerpo[c.id] = Number(v || 0);
    else if (v !== '') cuerpo[c.id] = v;
  }
  return cuerpo;
}
