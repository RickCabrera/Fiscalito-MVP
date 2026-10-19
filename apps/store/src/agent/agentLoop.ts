/**
 * Loop de tool calling del agente.
 *
 * Reemplaza el viejo `sendMessage(...) + extractNavCommands(...)` por un loop
 * agéntico real: el LLM puede pedir herramientas, el cliente las ejecuta, el
 * resultado vuelve al LLM, hasta que el LLM emite una respuesta de texto final.
 *
 * Inspirado en el agente del backend (apps/api/app/routes/agente.py).
 *
 * Tope: 8 iteraciones para prevenir loops infinitos.
 */

import type { NavigateFunction } from 'react-router-dom';
import type { UserProfile } from '../context/ProfileContext';
import { sendMessageWithTools, type ChatMessage } from '../services/voiceChatService';
import { getAgentActions } from './AgentContext';
import { isRegisteredTool, TOOL_EXECUTORS, toolsOpenAI, type ToolDeps } from './tools';
import type { PerfilFiscal } from '../context/perfilFiscal';
import type { ToolCallLogEntry, ToolResult } from './types';
import { ASISTENTE, MARCA } from '../services/marca';

const MAX_ITERATIONS = 8;

export interface AgentLoopOptions {
  history: ChatMessage[];
  userMessage: string;
  profile: UserProfile;
  /** K: el cliente activo del despacho, resuelto por `usePerfilFiscal`. */
  perfilFiscal: PerfilFiscal;
  historialResumen: string;
  navigate: NavigateFunction;
  uid: string | null;
}

export interface AgentLoopResult {
  reply: string;
  newHistory: ChatMessage[];
  executedTools: ToolCallLogEntry[];
}

/**
 * Quién es el usuario y sobre qué cliente trabaja, para el prompt.
 *
 * K: el sistema es solo para despachos. El despacho no tiene RFC ni régimen
 * propios (E-05); los datos fiscales que importan son los del CLIENTE ACTIVO.
 */
export function describirUsuario(profile: UserProfile, perfilFiscal: PerfilFiscal): string {
  const cliente = perfilFiscal.clienteId
    ? `Cliente activo (sobre él se calcula todo):
- Nombre: ${perfilFiscal.nombre || 'Sin nombre'}
- RFC: ${perfilFiscal.rfc || 'SIN CAPTURAR — se captura editando el cliente en Clientes'}
- Régimen: ${perfilFiscal.regimen || 'SIN CAPTURAR — se captura editando el cliente en Clientes'}`
    : 'No hay cliente activo: para calcular algo, el contador debe elegir un cliente en Clientes.';
  return `Datos de la cuenta actual: es un DESPACHO CONTABLE, no un contribuyente.
- Contador: ${profile.nombre || 'No proporcionado'}
- Despacho: ${profile.nombreDespacho || 'No proporcionado'}
El despacho NO tiene RFC ni régimen propios en la app, y eso es correcto: nunca se los pidas.
La app calcula las declaraciones, la nómina y las obligaciones patronales de sus CLIENTES.
${cliente}`;
}

function buildAgentSystemPrompt(
  profile: UserProfile,
  perfilFiscal: PerfilFiscal,
  historialResumen: string,
): string {
  return `Eres ${ASISTENTE}, un asistente de nómina y fiscal mexicano amigable con voz propia.
Hablas de forma conversacional, clara y concisa (máximo 3 oraciones para voz).

${describirUsuario(profile, perfilFiscal)}
Historial reciente de declaraciones del cliente activo: ${historialResumen || 'Sin historial aún.'}

PUEDES OPERAR LA APLICACIÓN POR TU CUENTA usando las herramientas (tools) disponibles.
NO describas lo que vas a hacer en texto: simplemente llama la tool. Después de que
ejecuten, comenta el resultado con el usuario.

Reglas:
1. Si el usuario pide ver, ir, mostrar o entrar a una sección: usa la tool "navegar".
2. Si el usuario pide calcular una pre-declaración y NO hay facturas cargadas: usa
   primero "cargar_xmls_demo" con el año y mes correspondientes, y luego
   "calcular_predeclaracion" con esos mismos valores. Esto es una secuencia normal.
3. Si el usuario solo pregunta cosas conceptuales (qué es ISR, etc.) responde
   directamente con texto, sin llamar tools.
4. Cuando reportes un cálculo, siempre menciona que es una PRE-declaración estimada.

Cuando presentes ${MARCA}, hazlo con entusiasmo.`;
}

export async function runAgentLoop(opts: AgentLoopOptions): Promise<AgentLoopResult> {
  const { history, userMessage, profile, perfilFiscal, historialResumen, navigate, uid } = opts;
  const { pushToolCall, updateToolCall } = getAgentActions();

  const systemMsg: ChatMessage = {
    role: 'system',
    content: buildAgentSystemPrompt(profile, perfilFiscal, historialResumen),
  };

  // El historial visible al usuario crece con texto plano. El historial al LLM
  // es más rico: incluye tool_calls y mensajes con role 'tool'. Lo construimos
  // por separado.
  const llmMessages: ChatMessage[] = [
    systemMsg,
    ...history,
    { role: 'user', content: userMessage },
  ];

  const deps: ToolDeps = { navigate, profile, perfilFiscal, uid };
  const executedTools: ToolCallLogEntry[] = [];

  for (let iter = 0; iter < MAX_ITERATIONS; iter++) {
    const response = await sendMessageWithTools(llmMessages, toolsOpenAI());

    if (response.type === 'text') {
      const newHistory: ChatMessage[] = [
        ...history,
        { role: 'user', content: userMessage },
        { role: 'assistant', content: response.text },
      ];
      return { reply: response.text, newHistory, executedTools };
    }

    // type === 'tool_calls'.
    // El assistant message con tool_calls debe empujarse al historial del LLM
    // ANTES de los tool_results, o la API rechaza.
    llmMessages.push({
      role: 'assistant',
      content: response.rawAssistantMessage.content ?? '',
      // @ts-expect-error: tool_calls es válido en OpenAI pero no está en nuestro tipo base.
      tool_calls: response.rawAssistantMessage.tool_calls,
    });

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
          result = await TOOL_EXECUTORS[call.name](call.args, deps);
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
        // @ts-expect-error: tool_call_id existe en OpenAI tool messages.
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
