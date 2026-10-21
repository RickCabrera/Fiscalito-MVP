import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { NavigateFunction } from 'react-router-dom';
import type { UserProfile } from '../context/ProfileContext';
import { resolverPerfilFiscal } from '../context/perfilFiscal';
import type { ClienteResumen } from '../services/despachoApi';

vi.mock('../services/firebase', () => ({ auth: {}, db: {}, default: {} }));
vi.mock('../services/declaracionesHistory', () => ({ guardarDeclaracion: vi.fn() }));

// P5-07: el LLM vive en el backend; el loop habla con `POST /asistente/turno`.
const turnoAsistente = vi.fn();
vi.mock('../services/asistenteApi', () => ({ turnoAsistente }));

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

const { runAgentLoop, argumentosParaEjecutor } = await import('./agentLoop');

const PERFIL = {
  rfc: '', regimen: '', nombre: 'Contadora Demo',
  contributorType: 'contador', nombreDespacho: 'Despacho Demo',
} as UserProfile;

const CLIENTE = {
  id: 'taller', nombre: 'Taller Nogal', rfc: 'TNO010101AB1', regimen: '612',
} as ClienteResumen;

const navigateFn = vi.fn();
const navigate = navigateFn as unknown as NavigateFunction;

function correr(userMessage = 'hola', cliente: ClienteResumen | null = CLIENTE) {
  return runAgentLoop({
    history: [],
    userMessage,
    profile: PERFIL,
    perfilFiscal: resolverPerfilFiscal(PERFIL, cliente),
    navigate,
    uid: null,
  });
}

/** Respuesta `tool_calls` con la forma de `POST /asistente/turno`. */
function toolCall(name: string, args: Record<string, unknown>, extra: unknown[] = []) {
  return {
    exito: true,
    type: 'tool_calls' as const,
    text: '',
    toolCalls: [{ id: 'call_1', name, args }],
    mensajes: [
      {
        role: 'assistant', content: '',
        tool_calls: [{ id: 'call_1', type: 'function',
          function: { name, arguments: JSON.stringify(args) } }],
      },
      ...extra,
    ],
    herramientas_servidor: [],
  };
}

function texto(t: string) {
  return { exito: true, type: 'text' as const, text: t, toolCalls: [], mensajes: [],
    herramientas_servidor: [] };
}

beforeEach(() => {
  turnoAsistente.mockReset();
  pushToolCall.mockClear();
  updateToolCall.mockClear();
  navigateFn.mockClear();
});

describe('runAgentLoop', () => {
  it('devuelve el texto y manda al servidor el cliente activo, sin prompt de sistema', async () => {
    turnoAsistente.mockResolvedValue(texto('Claro que sí.'));

    const res = await correr('¿qué es el ISR?');

    expect(res.reply).toBe('Claro que sí.');
    expect(res.executedTools).toHaveLength(0);
    expect(res.newHistory).toEqual([
      { role: 'user', content: '¿qué es el ISR?' },
      { role: 'assistant', content: 'Claro que sí.' },
    ]);
    // El prompt lo arma el SERVIDOR con lo que dice su base del cliente: aquí sólo viaja
    // la clave del cliente activo, y ningún mensaje `system`.
    const [peticion] = turnoAsistente.mock.calls[0];
    expect(peticion.cliente).toBe('taller');
    expect(peticion.contador).toBe('Contadora Demo');
    expect(peticion.historial).toEqual([{ role: 'user', content: '¿qué es el ISR?' }]);
    expect(peticion).not.toHaveProperty('tools');
  });

  it('sin cliente activo manda cliente null', async () => {
    turnoAsistente.mockResolvedValue(texto('ok'));
    await correr('hola', null);
    expect(turnoAsistente.mock.calls[0][0].cliente).toBeNull();
  });

  it('agrega los mensajes del servidor (firmados) antes del resultado del navegador', async () => {
    const firmado = { role: 'tool', tool_call_id: 'srv_1', content: '{"ok":true}', firma: 'f' };
    turnoAsistente
      .mockResolvedValueOnce(toolCall('navegar', { ruta: '/app/nomina' }, [firmado]))
      .mockResolvedValueOnce(texto('Listo.'));

    const res = await correr('llévame a nómina');

    expect(res.reply).toBe('Listo.');
    expect(navigateFn).toHaveBeenCalledWith('/app/nomina');
    const historial = turnoAsistente.mock.calls[1][0].historial;
    expect(historial.map((m: { role: string }) => m.role)).toEqual(
      ['user', 'assistant', 'tool', 'tool']);
    expect(historial[2]).toEqual(firmado); // la firma vuelve intacta
    expect(historial[3].tool_call_id).toBe('call_1');
  });

  it('traduce anio → año para los ejecutores del navegador', () => {
    expect(argumentosParaEjecutor({ anio: 2026, mes: 3 })).toEqual({ anio: 2026, año: 2026, mes: 3 });
    expect(argumentosParaEjecutor({ ruta: '/app' })).toEqual({ ruta: '/app' });
  });

  it('reporta una tool desconocida al servidor y sigue el loop', async () => {
    turnoAsistente
      .mockResolvedValueOnce(toolCall('tool_inventada', {}))
      .mockResolvedValueOnce(texto('Perdón, me equivoqué.'));

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

    // El error viaja de vuelta como mensaje role:'tool'.
    const historial = turnoAsistente.mock.calls[1][0].historial;
    const mensajeTool = historial.find((m: { role: string }) => m.role === 'tool');
    expect(mensajeTool.content).toContain('no está registrada');
  });

  it('corta a las 8 iteraciones y responde con el fallback', async () => {
    // Ruta inválida: la tool falla sin efectos y el LLM nunca emite texto.
    turnoAsistente.mockResolvedValue(toolCall('navegar', { ruta: '/no-existe' }));

    const res = await correr();

    expect(turnoAsistente).toHaveBeenCalledTimes(8);
    expect(res.executedTools).toHaveLength(8);
    expect(res.reply).toMatch(/no logré cerrar la respuesta/i);
    expect(res.newHistory[res.newHistory.length - 1]).toEqual({
      role: 'assistant',
      content: res.reply,
    });
  });
});
