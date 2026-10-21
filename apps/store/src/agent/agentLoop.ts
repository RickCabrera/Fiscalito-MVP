/**
 * Loop de tool calling del agente.
 *
 * P5-07: el LLM vive en el BACKEND (`POST /asistente/turno`, `services/asistenteApi.ts`).
 * El servidor arma el prompt con los datos del cliente activo que lee de su base, es dueño
 * del catálogo de herramientas y corre por su cuenta las de consulta (bóveda, balanza,
 * nómina, vencimientos, alertas, impuestos): las cifras salen del motor, nunca del modelo.
 * Cuando el modelo pide una herramienta que opera la pantalla (navegar, demo,
 * pre-declaración), el turno vuelve aquí: se agregan al historial los mensajes que mandó el
 * servidor (con sus resultados firmados), se corren las herramientas del navegador y se
 * vuelve a llamar.
 *
 * Tope: 8 iteraciones para prevenir loops infinitos.
 */

import type { NavigateFunction } from 'react-router-dom';
import type { UserProfile } from '../context/ProfileContext';
import { turnoAsistente, type MensajeAsistente } from '../services/asistenteApi';
import type { ChatMessage } from '../services/voiceChatService';
import { getAgentActions } from './AgentContext';
import { isRegisteredTool, TOOL_EXECUTORS, type ToolDeps } from './tools';
import type { PerfilFiscal } from '../context/perfilFiscal';
import type { ToolCallLogEntry, ToolResult } from './types';

const MAX_ITERATIONS = 8;

export interface AgentLoopOptions {
  history: ChatMessage[];
  userMessage: string;
  profile: UserProfile;
  /** K: el cliente activo del despacho, resuelto por `usePerfilFiscal`. */
  perfilFiscal: PerfilFiscal;
  navigate: NavigateFunction;
  uid: string | null;
}

export interface AgentLoopResult {
  reply: string;
  newHistory: ChatMessage[];
  executedTools: ToolCallLogEntry[];
}

/**
 * El catálogo del servidor usa `anio` (los nombres de propiedad de Anthropic no admiten
 * `ñ`); los ejecutores del navegador leen `año`. Se traduce aquí, en un solo lugar.
 */
/** El nombre del contador sin caracteres de control (el servidor rechaza un salto de línea). */
export function nombreParaPrompt(nombre: string | undefined): string {
  return Array.from(nombre || '', (c) => (c.charCodeAt(0) < 32 || c.charCodeAt(0) === 127 ? ' ' : c))
    .join('').trim().slice(0, 120);
}

export function argumentosParaEjecutor(args: Record<string, unknown>): Record<string, unknown> {
  return 'anio' in args && !('año' in args) ? { ...args, año: args.anio } : args;
}

export async function runAgentLoop(opts: AgentLoopOptions): Promise<AgentLoopResult> {
  const { history, userMessage, profile, perfilFiscal, navigate, uid } = opts;
  const { pushToolCall, updateToolCall } = getAgentActions();

  // El historial visible al usuario crece con texto plano. El historial al LLM
  // es más rico: incluye tool_calls y mensajes con role 'tool'. Lo construimos
  // por separado. El prompt de sistema NO viaja: lo arma el servidor.
  const llmMessages: MensajeAsistente[] = [
    ...history,
    { role: 'user', content: userMessage },
  ];

  const deps: ToolDeps = { navigate, profile, perfilFiscal, uid };
  const executedTools: ToolCallLogEntry[] = [];

  for (let iter = 0; iter < MAX_ITERATIONS; iter++) {
    const response = await turnoAsistente({
      cliente: perfilFiscal.clienteId,
      contador: nombreParaPrompt(profile.nombre),
      historial: llmMessages,
    });

    if (response.type === 'text') {
      const newHistory: ChatMessage[] = [
        ...history,
        { role: 'user', content: userMessage },
        { role: 'assistant', content: response.text },
      ];
      return { reply: response.text, newHistory, executedTools };
    }

    // type === 'tool_calls'.
    // El assistant con TODAS sus llamadas y los resultados (firmados) de las del servidor
    // van al historial ANTES de los resultados del navegador, o el servidor rechaza.
    llmMessages.push(...response.mensajes);

    for (const call of response.toolCalls) {
      const logEntry: ToolCallLogEntry = {
        id: crypto.randomUUID(),
        tool: (isRegisteredTool(call.name) ? call.name : 'navegar'),
        input: call.args,
        status: 'running',
        startedAt: Date.now(),
      };
      pushToolCall(logEntry);
      executedTools.push(logEntry);

      let result: ToolResult;
      if (!isRegisteredTool(call.name)) {
        result = {
          ok: false,
          summary: `Tool desconocida: ${call.name}`,
          error: `El LLM pidió la tool "${call.name}" que no está registrada.`,
        };
      } else {
        try {
          result = await TOOL_EXECUTORS[call.name](argumentosParaEjecutor(call.args), deps);
        } catch (e) {
          result = {
            ok: false,
            summary: `Error inesperado en ${call.name}`,
            error: e instanceof Error ? e.message : String(e),
          };
        }
      }

      updateToolCall(logEntry.id, {
        status: result.ok ? 'ok' : 'error',
        result,
        endedAt: Date.now(),
      });

      llmMessages.push({
        role: 'tool',
        tool_call_id: call.id,
        content: JSON.stringify({
          ok: result.ok,
          summary: result.summary,
          ...(result.data ? { data: result.data } : {}),
          ...(result.error ? { error: result.error } : {}),
        }),
      });
    }
  }

  // Se acabaron las iteraciones sin texto final.
  const fallback =
    'Hice todo lo que pude pero no logré cerrar la respuesta. ¿Lo intentamos de nuevo con más detalle?';
  return {
    reply: fallback,
    newHistory: [
      ...history,
      { role: 'user', content: userMessage },
      { role: 'assistant', content: fallback },
    ],
    executedTools,
  };
}
