/**
 * Nómina completa del cliente (plan P, P4-01 a P4-08). Siempre autenticada (`apiFetch`).
 *
 * P4-01: `calcularNomina` YA NO MANDA LA PLANTILLA. El backend la lee de la cartera del
 * cliente; mandarla sería afirmar un cliente y calcular otro. Lo que sí viaja es lo que
 * sólo sabe el operador: incidencias del cierre, variables capturadas y el tipo de nómina.
 *
 * Ninguna cifra fiscal se calcula aquí: todo importe sale del motor.
 */

import { apiFetch } from './api';
import type { ClienteDetalle } from './despachoApi';
import type { IncidenciasEmpleado, NominaPeriodo, PeriodoNomina } from './nominaDemoApi';

export type TipoNomina = 'ordinaria' | 'extraordinaria' | 'asimilados';
export type TipoHistorial = TipoNomina | 'finiquito' | 'aguinaldo' | 'ptu';

/** Variables e incidencias capturadas por empleado (P4-05). Importes como string. */
export interface VariablesEmpleado {
  empleado_no: string;
  horas_dobles?: string;
  horas_triples?: string;
  domingos_trabajados?: number;
  dias_vacaciones?: number;
  incapacidades?: { tipo: '01' | '02' | '03'; dias: number }[];
  faltas_adicionales?: number;
  infonavit?: { tipo: 'porcentaje' | 'cuota_fija' | 'factor'; valor: string } | null;
  fonacot?: string;
  prestamo?: string;
  pension?: { tipo: 'porcentaje' | 'monto'; valor: string; base: 'neto' | 'bruto' } | null;
  viaticos_comprobados?: string;
}

export interface ResumenPeriodo {
  id: number;
  tipo: TipoHistorial;
  periodicidad: string;
  inicio: string;
  fin: string;
  fecha_pago: string;
  estado: 'borrador' | 'calculada' | 'cerrada' | 'timbrada';
  empleados: number;
  total_percepciones: string;
  total_deducciones: string;
  total_isr: string;
  total_neto: string;
}

export interface PeriodoGuardado {
  periodo: ResumenPeriodo;
  criterios: Record<string, string>;
  parametros: Record<string, unknown>;
  resultado: Record<string, unknown>;
}

export interface Comparacion {
  a: ResumenPeriodo;
  b: ResumenPeriodo;
  diferencia_neto: string;
  diferencia_isr: string;
  diferencia_percepciones: string;
  por_empleado: { empleado_no: string; nombre: string; neto_a: string | null; neto_b: string | null; diferencia: string }[];
}

export interface CriteriosDisponibles {
  defaults: Record<string, string>;
  opciones: Record<string, Record<string, string>>;
}

export interface CalculoExtraordinario {
  tipo: string;
  periodo_id: number | null;
  resultado: Record<string, unknown>;
  advertencias: string[];
}

/** Lo que devuelve el motor con los campos de P4. */
export interface NominaCalculada extends NominaPeriodo {
  tipo?: TipoNomina;
  periodo_id?: number | null;
  criterios?: Record<string, string>;
}

const base = (cliente: string) => `/nomina/clientes/${encodeURIComponent(cliente)}`;

/**
 * Calcula (y guarda) la nómina del periodo. Las incidencias van verbatim desde el
 * cierre; la plantilla NO viaja (P4-01).
 */
export function calcularNomina(
  cliente: string,
  periodo: PeriodoNomina,
  incidencias: IncidenciasEmpleado[],
  ficha: Pick<ClienteDetalle, 'prima_riesgo' | 'clave_periodicidad'>,
  opciones: { tipo?: TipoNomina; variables?: VariablesEmpleado[] } = {},
): Promise<NominaCalculada> {
  return apiFetch('/nomina/calcular-periodo', {
    method: 'POST',
    json: {
      cliente,
      periodo,
      incidencias: incidencias.map((i) => ({
        empleado_no: i.empleado_no,
        dias_periodo: i.dias_periodo,
        faltas: i.faltas,
        dias_ausentismo: i.dias_ausentismo,
      })),
      parametros: { prima_riesgo: ficha.prima_riesgo, clave_periodicidad: ficha.clave_periodicidad },
      tipo: opciones.tipo ?? 'ordinaria',
      variables: opciones.variables ?? [],
    },
  });
}

export function listarHistorial(cliente: string, tipo?: TipoHistorial): Promise<{ periodos: ResumenPeriodo[] }> {
  return apiFetch(`${base(cliente)}/historial${tipo ? `?tipo=${tipo}` : ''}`);
}

export function abrirPeriodo(cliente: string, id: number): Promise<PeriodoGuardado> {
  return apiFetch(`${base(cliente)}/periodos/${id}`);
}

export function cerrarPeriodoNomina(cliente: string, id: number): Promise<PeriodoGuardado> {
  return apiFetch(`${base(cliente)}/periodos/${id}/cerrar`, { method: 'POST' });
}

export function compararPeriodos(cliente: string, a: number, b: number): Promise<Comparacion> {
  return apiFetch(`${base(cliente)}/comparar?a=${a}&b=${b}`);
}

export function obtenerCriterios(): Promise<CriteriosDisponibles> {
  return apiFetch('/nomina/criterios');
}

export function calcularAguinaldo(
  cliente: string,
  cuerpo: { ejercicio: number; fecha_pago: string; empleados?: string[] },
): Promise<CalculoExtraordinario> {
  return apiFetch(`${base(cliente)}/aguinaldo`, { method: 'POST', json: cuerpo });
}

export function calcularPTU(
  cliente: string,
  cuerpo: {
    ejercicio: number;
    renta_gravable: string;
    fecha_pago: string;
    trabajadores: { empleado_no: string; dias_trabajados: number; salarios_devengados: string; tipo?: string }[];
  },
): Promise<CalculoExtraordinario> {
  return apiFetch(`${base(cliente)}/ptu`, { method: 'POST', json: cuerpo });
}

export function calcularFiniquito(
  cliente: string,
  cuerpo: { empleado_no: string; fecha_baja: string; causa: string; dias_salario_pendientes?: number },
): Promise<CalculoExtraordinario> {
  return apiFetch(`${base(cliente)}/finiquito`, { method: 'POST', json: cuerpo });
}

export function calcularAjusteAnual(cliente: string, ejercicio: number): Promise<CalculoExtraordinario> {
  return apiFetch(`${base(cliente)}/ajuste-anual`, { method: 'POST', json: { ejercicio } });
}
