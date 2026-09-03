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
import { modoEmpresaUnica } from '../services/modoEmpresa';
import type { ToolCallLogEntry, ToolResult } from './types';
import { ASISTENTE, MARCA } from '../services/marca';

const MAX_ITERATIONS = 8;

export interface AgentLoopOptions {
  history: ChatMessage[];
  userMessage: string;
  profile: UserProfile;
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
 * Quién es el usuario, para el prompt.
 *
 * Un DESPACHO no tiene RFC ni régimen desde E-05, y no es un olvido del
 * usuario: la app dejó de pedírselos porque no se le calcula nada propio. Con
 * el bloque de contribuyente, el prompt decía "RFC: No proporcionado" y el LLM
 * le pedía al contador que completara su perfil — un callejón, porque ya no hay
 * dónde capturarlo.
 *
 * EL MODO EMPRESA ÚNICA TIENE SU PROPIO BLOQUE (O-cierre)
 * -------------------------------------------------------
 * Y no es cosmético. El perfil sigue siendo `contador` —`StepTipo` sólo ofrece
 * esa opción en este modo— así que el asistente, que flota sobre TODAS las
 * pantallas, le hablaba al operador de Orca de "tu despacho" y de "tus
 * clientes", sobre su propia nómina.
 *
 * Peor: la última línea del bloque de despacho es una **instrucción falsa** en
 * este modo. Dice "nunca le pidas su RFC ni su régimen" porque no hay dónde
 * capturarlo — pero en empresa única el RFC **sí** se captura, en Configuración
 * de empresa, y es dato obligatorio para el IMSS. El asistente tenía prohibido
 * mencionar justo el campo que al operador le falta llenar. Lo cazó el revisor
 * de cierre de la corrida O.
 */
function describirUsuario(profile: UserProfile): string {
  if (profile.contributorType === 'contador' && modoEmpresaUnica()) {
    return `Datos de la cuenta actual: lleva la NÓMINA DE UNA SOLA EMPRESA. No es un
despacho y no tiene cartera de clientes — no existe ese concepto en esta app.
- Responsable: ${profile.nombre || 'No proporcionado'}
La app NO calcula las declaraciones propias de la empresa (ISR, IVA): calcula su NÓMINA y
sus obligaciones patronales. Los datos fiscales de la empresa —razón social, RFC, registro
patronal, prima de riesgo— se capturan en Perfil → Configuración de empresa, así que si
falta alguno, ahí se llena. Nunca hables de "clientes" ni de "cartera".`;
  }
  if (profile.contributorType === 'contador') {
    return `Datos de la cuenta actual: es un DESPACHO CONTABLE, no un contribuyente.
- Contador: ${profile.nombre || 'No proporcionado'}
- Despacho: ${profile.nombreDespacho || 'No proporcionado'}
El despacho NO tiene RFC ni régimen capturados en la app, y eso es correcto: la app no
calcula sus declaraciones propias, sino la nómina y las obligaciones patronales de sus
CLIENTES. Nunca le pidas su RFC ni su régimen.`;
  }
  return `Datos del contribuyente actual:
- Nombre: ${profile.nombre || 'No proporcionado'}
- RFC: ${profile.rfc || 'No proporcionado'}
- Tipo: ${profile.contributorType || 'No definido'}
- Régimen: ${profile.regimen || 'No definido'}
- Actividad: ${profile.actividad || 'No proporcionada'}`;
}

function buildAgentSystemPrompt(profile: UserProfile, historialResumen: string): string {
  return `Eres ${ASISTENTE}, un asistente de nómina y fiscal mexicano amigable con voz propia.
Hablas de forma conversacional, clara y concisa (máximo 3 oraciones para voz).

${describirUsuario(profile)}
Historial reciente de declaraciones: ${historialResumen || 'Sin historial aún.'}

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
  const { history, userMessage, profile, historialResumen, navigate, uid } = opts;
  const { pushToolCall, updateToolCall } = getAgentActions();

  const systemMsg: ChatMessage = {
    role: 'system',
    content: buildAgentSystemPrompt(profile, historialResumen),
  };

  // El historial visible al usuario crece con texto plano. El historial al LLM
  // es más rico: incluye tool_calls y mensajes con role 'tool'. Lo construimos
  // por separado.
  const llmMessages: ChatMessage[] = [
    systemMsg,
    ...history,
    { role: 'user', content: userMessage },
  ];

  const deps: ToolDeps = { navigate, profile, uid };
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
