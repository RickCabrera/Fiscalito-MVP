/**
 * Tipos compartidos del agente Fiscalito.
 *
 * El loop de tool calling, el AgentContext y el panel de actividad
 * (Aditamento C, día 7) hablan en estos términos.
 */

import type { CFDI, PreDeclaracionResponse } from '../services/fiscalAgentApi';

/** Nombre de cada tool registrada. Se extiende a medida que se agregan tools. */
export type ToolName =
  | 'navegar'
  | 'cargar_xmls_demo'
  | 'calcular_predeclaracion';

/** Resultado de ejecutar una tool — lo que se manda de vuelta al LLM. */
export interface ToolResult {
  /** true si la tool corrió sin errores (aunque el resultado sea "0 facturas"). */
  ok: boolean;
  /** Mensaje breve que el LLM puede leer y razonar sobre él. */
  summary: string;
  /** Datos estructurados opcionales (los más útiles para el siguiente paso). */
  data?: Record<string, unknown>;
  /** Si ok=false, mensaje de error legible para el LLM. */
  error?: string;
}

/**
 * Entrada del feed de actividad del agente — la usa el panel lateral
 * (Aditamento C) y se mantiene en AgentContext aunque el panel no exista
 * todavía. Cada tool call genera una entrada.
 */
export interface ToolCallLogEntry {
  id: string;                  // crypto.randomUUID()
  tool: ToolName;
  input: Record<string, unknown>;
  status: 'running' | 'ok' | 'error';
  result?: ToolResult;
  startedAt: number;           // Date.now()
  endedAt?: number;
}

/**
 * Estado compartido que las tools leen y escriben.
 * Vive en AgentContext.
 */
export interface AgentSharedState {
  facturas: CFDI[];
  resultado: PreDeclaracionResponse | null;
  /** Año/mes activos en el tab. Sirve a tools que no reciben periodo explícito. */
  periodoYear: number;
  periodoMonth: number;
}
