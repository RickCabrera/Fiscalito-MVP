/**
 * Asistente IA del despacho (P5-07, absorbe S-00): chat, voz a texto y texto a voz.
 *
 * TODO pasa por el backend con la sesión de Firebase (`apiFetch`). El navegador no tiene
 * ninguna llave de proveedor de IA: antes `voiceChatService.ts` llamaba a OpenAI con una
 * llave en una variable de Vite, y toda variable `VITE_*` se incrusta en el JavaScript que
 * descarga cada visitante. `sinLlavesLLM.test.ts` falla si eso vuelve.
 *
 * El servidor es dueño del prompt y del catálogo de herramientas: aquí sólo viajan el
 * cliente activo, el nombre del contador y el historial.
 */

import { apiArchivo, apiFetch } from './api';

/** Mensaje del historial con la forma de Chat Completions que arma `agentLoop`. */
export interface MensajeAsistente {
  role: 'user' | 'assistant' | 'tool';
  content: string | null;
  tool_calls?: Array<{
    id: string;
    type: 'function';
    function: { name: string; arguments: string };
  }>;
  tool_call_id?: string;
  /** Firma del servidor en los resultados de SUS herramientas: se devuelve tal cual. */
  firma?: string;
}

export interface HerramientaServidor {
  id: string;
  nombre: string;
  argumentos: Record<string, unknown>;
  ok: boolean;
  datos?: Record<string, unknown> | null;
  error?: string | null;
}

export interface TurnoAsistente {
  exito: boolean;
  type: 'text' | 'tool_calls';
  text: string;
  /** Herramientas que le tocan al navegador (navegar, demo, pre-declaración). */
  toolCalls: Array<{ id: string; name: string; args: Record<string, unknown> }>;
  /** Se agregan al historial ANTES de los resultados de las herramientas del navegador. */
  mensajes: MensajeAsistente[];
  /** Lo que respondieron la base y los motores: las cifras salen de aquí. */
  herramientas_servidor: HerramientaServidor[];
}

export interface PeticionTurno {
  cliente: string | null;
  contador: string;
  historial: MensajeAsistente[];
}

export function turnoAsistente(peticion: PeticionTurno): Promise<TurnoAsistente> {
  return apiFetch<TurnoAsistente>('/asistente/turno', {
    method: 'POST', json: peticion, timeoutMs: 90000,
  });
}

/** Voz a texto. El audio va crudo en el cuerpo, con su tipo (`audio/webm;codecs=opus`). */
export async function transcribirAudio(audio: Blob): Promise<string> {
  const r = await apiFetch<{ texto: string }>('/asistente/transcribir', {
    method: 'POST', body: audio, timeoutMs: 60000,
    headers: { 'Content-Type': audio.type || 'audio/webm' },
  });
  return r.texto ?? '';
}

/** Texto a voz: MP3 listo para `decodeAudioData`. */
export async function sintetizarVoz(texto: string): Promise<ArrayBuffer> {
  const audio = await apiArchivo('/asistente/hablar', {
    method: 'POST', json: { texto: texto.slice(0, 4096) }, timeoutMs: 60000,
  });
  return audio.arrayBuffer();
}
