import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { NavigateFunction } from 'react-router-dom';
import type { UserProfile } from '../context/ProfileContext';

vi.mock('../services/firebase', () => ({ auth: {}, db: {}, default: {} }));
vi.mock('../services/declaracionesHistory', () => ({ guardarDeclaracion: vi.fn() }));

const sendMessageWithTools = vi.fn();
vi.mock('../services/voiceChatService', () => ({ sendMessageWithTools }));

const pushToolCall = vi.fn();
const updateToolCall = vi.fn();
vi.mock('./AgentContext', () => ({
  getAgentActions: () => ({
    pushToolCall,
    updateToolCall,
    setFacturas: vi.fn(),
    setResultado: vi.fn(),
    setPeriodo: vi.fn(),
  }),
  getAgentSnapshot: () => ({
    facturas: [],
    resultado: null,
    periodoYear: 2026,
    periodoMonth: 1,
  }),
}));

const { runAgentLoop } = await import('./agentLoop');

const PERFIL = {
  rfc: 'AAA010101AAA',
  regimen: '612',
  nombre: 'Contribuyente Demo',
  actividad: 'Servicios',
} as UserProfile;

function correr(userMessage = 'hola') {
  return runAgentLoop({
    history: [],
    userMessage,
    profile: PERFIL,
    historialResumen: '',
    navigate: vi.fn() as unknown as NavigateFunction,
    uid: null,
  });
}

/** Respuesta de tool call con la forma que devuelve sendMessageWithTools. */
function toolCall(name: string, args: Record<string, unknown>) {
  return {
    type: 'tool_calls' as const,
    rawAssistantMessage: { content: null, tool_calls: [{ id: 'call_1' }] },
    toolCalls: [{ id: 'call_1', name, args }],
  };
}

beforeEach(() => {
  sendMessageWithTools.mockReset();
  pushToolCall.mockClear();
  updateToolCall.mockClear();
});

describe('runAgentLoop', () => {
  it('devuelve el texto del LLM y arma el historial, con el perfil en el system prompt', async () => {
    sendMessageWithTools.mockResolvedValue({ type: 'text', text: 'Claro que sí.' });

    const res = await correr('¿qué es el ISR?');

    expect(res.reply).toBe('Claro que sí.');
    expect(res.executedTools).toHaveLength(0);
    expect(res.newHistory).toEqual([
      { role: 'user', content: '¿qué es el ISR?' },
      { role: 'assistant', content: 'Claro que sí.' },
    ]);

    // buildAgentSystemPrompt es privada: se verifica por lo que recibe el LLM.
    const [mensajes] = sendMessageWithTools.mock.calls[0];
    expect(mensajes[0].role).toBe('system');
    expect(mensajes[0].content).toContain('AAA010101AAA');
    expect(mensajes[0].content).toContain('Contribuyente Demo');
  });

  /**
   * E-07: un DESPACHO no tiene RFC ni régimen, y no es un olvido del usuario —
   * E-05 dejó de pedírselos porque la app no le calcula nada propio. Con el
   * bloque de contribuyente, el prompt decía "RFC: No proporcionado" y el LLM le
   * pedía completar su perfil: un callejón, porque ya no hay dónde capturarlo.
   */
  it('a un despacho no le pide RFC ni régimen en el system prompt', async () => {
    sendMessageWithTools.mockResolvedValue({ type: 'text', text: 'ok' });

    await runAgentLoop({
      history: [],
      userMessage: 'hola',
      profile: {
        rfc: '', regimen: '', nombre: 'Contadora Demo',
        contributorType: 'contador', nombreDespacho: 'Despacho Demo',
      } as UserProfile,
      historialResumen: '',
      navigate: vi.fn() as unknown as NavigateFunction,
      uid: null,
    });

    const [mensajes] = sendMessageWithTools.mock.calls[0];
    const prompt = mensajes[0].content as string;
    expect(prompt).toContain('DESPACHO CONTABLE');
    expect(prompt).toContain('Despacho Demo');
    expect(prompt).toContain('Nunca le pidas su RFC');
    expect(prompt).not.toContain('RFC: No proporcionado');
  });

  it('reporta una tool desconocida al LLM y sigue el loop', async () => {
    sendMessageWithTools
      .mockResolvedValueOnce(toolCall('tool_inventada', {}))
      .mockResolvedValueOnce({ type: 'text', text: 'Perdón, me equivoqué.' });

    const res = await correr();

    expect(res.reply).toBe('Perdón, me equivoqué.');
    expect(updateToolCall).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        status: 'error',
        result: expect.objectContaining({
          ok: false,
          summary: expect.stringMatching(/tool desconocida/i),
        }),
      }),
    );

    // El error viaja de vuelta al LLM como mensaje role:'tool'.
    const [mensajesSegundaVuelta] = sendMessageWithTools.mock.calls[1];
    const mensajeTool = mensajesSegundaVuelta.find(
      (m: { role: string }) => m.role === 'tool',
    );
    expect(mensajeTool.content).toContain('no está registrada');
  });

  it('corta a las 8 iteraciones y responde con el fallback', async () => {
    // Ruta inválida: la tool falla sin efectos y el LLM nunca emite texto.
    sendMessageWithTools.mockResolvedValue(toolCall('navegar', { ruta: '/no-existe' }));

    const res = await correr();

    expect(sendMessageWithTools).toHaveBeenCalledTimes(8);
    expect(res.executedTools).toHaveLength(8);
    expect(res.reply).toMatch(/no logré cerrar la respuesta/i);
    expect(res.newHistory[res.newHistory.length - 1]).toEqual({
      role: 'assistant',
      content: res.reply,
    });
  });
});
