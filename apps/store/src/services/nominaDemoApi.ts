/**
 * Cliente de los endpoints de la demo del checador (épica D).
 *
 * DEMO — se borra en F2 junto con la pantalla.
 *
 * Vive aparte de `fiscalAgentApi.ts` (411 líneas) y reusa su misma variable de
 * entorno: no hay una segunda URL que configurar.
 *
 * NINGUNA CONSTANTE FISCAL VIVE AQUÍ
 * ----------------------------------
 * Ni los empleados, ni la prima de riesgo, ni el periodo. Todo sale de
 * `GET /nomina/demo/plantilla`. Escribirlos en TypeScript sería una copia de
 * valores con fundamento legal en un lugar donde ningún test comprueba que no
 * diverjan de `app/demo_nomina.py`.
 */

import type { ClienteDetalle } from './despachoApi';

import { cuerpoDeError, detalleDelError } from './errorApi';
import type { HorarioLaboral } from './carteraApi';

const BASE_URL = import.meta.env.VITE_FISCAL_AGENT_URL || 'http://localhost:8000';
const V1 = `${BASE_URL}/api/v1`;

/** El cliente único de la demo. El backend lo usa como default. */
export const CLIENTE_DEMO = 'demo';

// ── Tipos que devuelve el backend ──

export interface EmpleadoDemo {
  empleado_no: string;
  nombre: string;
}

export interface PeriodoNomina {
  inicio: string;
  fin: string;
  fecha_pago: string | null;
}

export interface PlantillaDemo {
  cliente: string;
  origen: string;
  empleados: EmpleadoDemo[];
  prima_riesgo: string;
  clave_periodicidad: string;
  zona: string;
  periodo_sugerido: PeriodoNomina;
}

export interface EventoChecada {
  empleado_no: string;
  timestamp: string;
  tipo: 'entrada' | 'salida';
  fuente: string;
  serial_no: number | null;
  raw: { name?: string } | null;
}

export interface IncidenciasEmpleado {
  empleado_no: string;
  dias_periodo: number;
  dias_laborables: number;
  dias_trabajados: number;
  faltas: number;
  dias_ausentismo: number;
  retardos: number;
  /** Informativo. NO alimenta ningún cálculo: la base de cuotas la decide
   *  `DiasDelPeriodo` por ramo (Art. 31 LSS, §D3). */
  dias_cotizados: number;
}

export interface CierrePeriodo {
  cliente: string;
  periodo: { inicio: string; fin: string };
  incidencias: IncidenciasEmpleado[];
  empleados_desconocidos: string[];
}

export interface Partida {
  tipo: string;
  clave: string;
  concepto: string;
  importe: string;
  gravado: string | null;
  exento: string | null;
  subsidio_causado: string | null;
}

export interface CuotaRamo {
  clave: string;
  nombre: string;
  base_diaria: string;
  dias: number;
  patron: string;
  obrero: string;
  fundamento: string;
}

export interface ReciboNomina {
  empleado_no: string;
  nombre: string;
  sbc: string;
  es_salario_minimo: boolean;
  dias_periodo: number;
  dias_ausentismo: number;
  dias_pagados: number;
  percepciones: Partida[];
  deducciones: Partida[];
  otros_pagos: Partida[];
  total_percepciones: string;
  total_deducciones: string;
  neto: string;
  cuota_obrera: string;
  cuota_patronal: string;
  absorbio_cuota_obrera: boolean;
  ramos: CuotaRamo[];
}

export interface PorcionConsolidada {
  periodicidad: string;
  por_ramo: Record<string, string>;
  total_patron: string;
  total_obrero: string;
  total: string;
  empleados: number;
}

export interface NominaPeriodo {
  cliente: string;
  periodo: PeriodoNomina;
  /** Con la que se calculó, ya resuelto el default. NO se deriva en el front. */
  fecha_pago_efectiva: string;
  origen_plantilla: string;
  recibos: ReciboNomina[];
  porcion_mensual: PorcionConsolidada;
  porcion_bimestral: PorcionConsolidada;
  advertencias: string[];
}

/**
 * La plantilla tal como viaja en `POST /nomina/calcular-periodo`.
 *
 * Son los cinco campos que el backend espera, con su nombre y su tipo. Existe
 * como tipo propio para que quien la arme **no tenga que fabricar un
 * `EmpleadoCliente` completo** rellenando campos que no conoce: un `factor: '0'`
 * o un `factor_implicito: false` inventados son afirmaciones falsas sobre
 * números que no existen, viajando con el tipo que la ficha y el PDF consumen.
 */
export interface EmpleadoNominaRequest {
  empleado_no: string;
  nombre: string;
  salario_diario: string;
  salario_diario_integrado: string;
  zona: string;
}

// ── Transporte ──

async function pedir<T>(ruta: string, opciones?: RequestInit): Promise<T> {
  const res = await fetch(`${V1}${ruta}`, {
    headers: { 'Content-Type': 'application/json' },
    ...opciones,
  });
  if (!res.ok) {
    // El handler de dominio responde `{exito: false, error: "..."}`; las
    // validaciones de FastAPI, `{detail: [...]}`; y una ruta que el backend no
    // conoce, `{detail: "Not Found"}` — que es un caso distinto y merece un
    // mensaje distinto. Las tres formas viven en `errorApi.ts`.
    throw new Error(detalleDelError(res, await cuerpoDeError(res)));
  }
  return res.json() as Promise<T>;
}

export function obtenerPlantillaDemo(cliente = CLIENTE_DEMO): Promise<PlantillaDemo> {
  return pedir(`/nomina/demo/plantilla?cliente=${encodeURIComponent(cliente)}`);
}

/**
 * Checadas del cliente, para el panel en vivo.
 *
 * **NO manda `desde`, y es a propósito.** El simulador siembra la última
 * quincena YA TERMINADA (D-05), así que un `desde` anclado en el presente
 * dejaría el panel vacío en la demo. El almacén tiene tope de 5,000 eventos y
 * la quincena son 194.
 */
export function obtenerEventos(cliente = CLIENTE_DEMO): Promise<{ eventos: EventoChecada[] }> {
  return pedir(`/asistencia/eventos?cliente=${encodeURIComponent(cliente)}`);
}

export function cerrarPeriodo(
  cliente: string,
  empleados: string[],
  periodo: { inicio: string; fin: string },
  /**
   * O-03: el horario del patrón, contra el que se miden retardos y faltas.
   *
   * **Objeto de opciones y no un cuarto posicional, a propósito.** Un
   * posicional opcional se olvida en un llamador y cae al default sin que nada
   * avise — que es exactamente el defecto que O-03 viene a arreglar: hasta
   * ahora el front NUNCA mandaba horario y el backend aplicaba 08:00-17:00 con
   * 15 minutos a todo el mundo, aunque la empresa hubiera configurado otro.
   *
   * Omitirlo sigue siendo válido y significa "el default del backend", que es
   * lo que el modo despacho necesita: ahí no hay una empresa única de la que
   * sacarlo.
   */
  opciones: { horario?: HorarioLaboral } = {},
): Promise<CierrePeriodo> {
  return pedir('/asistencia/cerrar-periodo', {
    method: 'POST',
    body: JSON.stringify({
      cliente,
      empleados,
      periodo,
      ...(opciones.horario ? { horario: opciones.horario } : {}),
    }),
  });
}

/**
 * Calcula la nómina del periodo.
 *
 * `incidencias` se pasan **verbatim** desde el cierre: `dias_periodo`, `faltas`
 * y `dias_ausentismo` alimentan `DiasDelPeriodo` y los días pagados, o sea las
 * cuotas del IMSS y el ISR. Recomponerlas aquí sería mover números fiscales
 * desde la UI.
 */
export function calcularNomina(
  cliente: string,
  periodo: PeriodoNomina,
  incidencias: IncidenciasEmpleado[],
  ficha: ClienteDetalle,
  /** La plantilla que entra al cálculo. Explícita desde G-01: puede venir de la
   *  cartera del despacho y no de la ficha del backend. */
  empleados: EmpleadoNominaRequest[],
): Promise<NominaPeriodo> {
  return pedir('/nomina/calcular-periodo', {
    method: 'POST',
    body: JSON.stringify({
      cliente,
      periodo,
      incidencias: incidencias.map((i) => ({
        empleado_no: i.empleado_no,
        dias_periodo: i.dias_periodo,
        faltas: i.faltas,
        dias_ausentismo: i.dias_ausentismo,
      })),
      parametros: {
        prima_riesgo: ficha.prima_riesgo,
        clave_periodicidad: ficha.clave_periodicidad,
      },
      // E-03: la plantilla viaja SIEMPRE. Omitirla sólo es válido para el
      // cliente `demo` (`routes/nomina.py`), así que sin esto los sintéticos no
      // se pueden calcular. Los campos salen tal cual de la ficha: son un
      // superconjunto compatible de `EmpleadoNominaSchema` y remapearlos aquí
      // sería mover datos fiscales desde la UI.
      empleados,
    }),
  });
}
