/**
 * El asistente de voz también vive en el pivote. (O-cierre)
 *
 * O-01 sacó la cartera del menú, de las rutas y de las pantallas — y dejó
 * intacto el único componente que flota sobre TODAS ellas. `FiscalitoVoiceChat`
 * se monta en `AppLayout`, así que el asistente está encima de Empleados,
 * Dispositivos, Nómina, Calendario y Perfil; y su prompt de sistema le decía al
 * operador de una empresa única que su cuenta era un **despacho contable** con
 * **clientes**.
 *
 * Dos consecuencias, y la segunda es la fea:
 *
 * 1. El asistente habla de "tu despacho" y "tus clientes" sobre la nómina
 *    propia del patrón. El criterio de O-01 era literalmente "sin que exista el
 *    concepto de cartera".
 * 2. El bloque de despacho termina en **"Nunca le pidas su RFC ni su régimen"**,
 *    que era correcto cuando no había dónde capturarlos. En modo empresa única
 *    el RFC **sí** se captura, en Configuración de empresa, y es dato
 *    obligatorio para el IMSS: el asistente tenía prohibido mencionar justo el
 *    campo que al operador le falta llenar.
 *
 * El guardián de O-02 no podía cazarlo: `marca.test.ts` busca la palabra
 * "Fiscalito", y el rebrand sí había llegado al nombre del asistente. Llegó al
 * nombre y no al modelo de negocio que el prompt describe.
 *
 * Lo encontró el revisor de cierre de la corrida O.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { NavigateFunction } from 'react-router-dom';
import type { UserProfile } from '../context/ProfileContext';
import { modoDespacho, modoEmpresa } from '../test/modoDespacho';

vi.mock('../services/firebase', () => ({ auth: {}, db: {}, default: {} }));
vi.mock('../services/declaracionesHistory', () => ({ guardarDeclaracion: vi.fn() }));

const sendMessageWithTools = vi.fn();
vi.mock('../services/voiceChatService', () => ({ sendMessageWithTools }));

vi.mock('./AgentContext', () => ({
  getAgentActions: () => ({
    pushToolCall: vi.fn(),
    updateToolCall: vi.fn(),
    setFacturas: vi.fn(),
    setResultado: vi.fn(),
    setPeriodo: vi.fn(),
  }),
  getAgentSnapshot: () => ({ facturas: [], resultado: null, periodoYear: 2026, periodoMonth: 1 }),
}));

const { runAgentLoop } = await import('./agentLoop');
const { toolsOpenAI, TOOL_EXECUTORS } = await import('./tools');

/**
 * El operador de Orca. `contador` NO es un descuido de la fixture: en modo
 * empresa única `StepTipo` sólo ofrece ese tipo, así que **siempre** es éste el
 * perfil. Ahí estaba el defecto.
 */
const OPERADOR = {
  contributorType: 'contador',
  nombre: 'Responsable de Nómina',
  nombreDespacho: 'Despacho Que No Existe',
} as UserProfile;

/** El prompt de sistema que de verdad se le mandó al modelo. */
async function promptDeSistema(): Promise<string> {
  sendMessageWithTools.mockResolvedValue({ type: 'text', text: 'ok' });
  await runAgentLoop({
    history: [],
    userMessage: 'hola',
    profile: OPERADOR,
    historialResumen: '',
    navigate: vi.fn() as unknown as NavigateFunction,
    uid: null,
  });
  const mensajes = sendMessageWithTools.mock.calls[0][0] as { role: string; content: string }[];
  return mensajes.find((m) => m.role === 'system')!.content;
}

beforeEach(() => {
  sendMessageWithTools.mockReset();
});

describe('en modo empresa única el asistente no habla de despacho ni de clientes', () => {
  /**
   * T1: este bloque medía el modo empresa única heredándolo del default, que
   * hasta T1 era ése. Al invertirse, pasó a medir el despacho y se cayó entero.
   * Ahora lo declara, igual que sus gemelos de abajo declaran el despacho.
   */
  modoEmpresa();

  it('el prompt no dice "DESPACHO CONTABLE"', async () => {
    expect(await promptDeSistema()).not.toMatch(/DESPACHO CONTABLE/);
  });

  it('no le atribuye clientes a la cuenta', async () => {
    const prompt = await promptDeSistema();
    // El bloque viejo decía "la nómina y las obligaciones patronales de sus
    // CLIENTES". Eso es lo que no puede quedar.
    expect(prompt).not.toMatch(/de sus CLIENTES/);
    expect(prompt).not.toMatch(/tus clientes/i);
  });

  it('y le PROHÍBE al modelo usar ese vocabulario', async () => {
    // La palabra sí aparece —en la prohibición—, que es la forma de que el
    // modelo no la use. Afirmar su ausencia sería medir la redacción, no el
    // efecto.
    expect(await promptDeSistema()).toMatch(/Nunca hables de "clientes" ni de "cartera"/);
  });

  it('NO le prohíbe pedir el RFC: en este modo sí hay dónde capturarlo', async () => {
    // La instrucción del bloque de despacho era falsa aquí, y bloqueaba justo
    // el campo que al operador le falta llenar para poder exportar al IMSS.
    expect(await promptDeSistema()).not.toMatch(/Nunca le pidas su RFC/);
  });

  it('y sí dice dónde se capturan los datos fiscales de la empresa', async () => {
    expect(await promptDeSistema()).toMatch(/Configuración de empresa/);
  });

  it('no filtra el nombre del despacho, que en este modo no significa nada', async () => {
    // El campo sigue en el perfil por compatibilidad; ponerlo en el prompt le
    // haría creer al modelo que la cuenta es un despacho llamado así.
    expect(await promptDeSistema()).not.toMatch(/Despacho Que No Existe/);
  });
});

describe('en modo despacho el prompt de siempre no se tocó', () => {
  modoDespacho();

  it('vuelve a decir DESPACHO CONTABLE y a nombrar al despacho', async () => {
    const prompt = await promptDeSistema();
    expect(prompt).toMatch(/DESPACHO CONTABLE/);
    expect(prompt).toMatch(/Despacho Que No Existe/);
    expect(prompt).toMatch(/Nunca le pidas su RFC/);
  });
});

describe('la tool de navegación no ofrece una ruta que redirige', () => {
  modoEmpresa();

  /** El enum de rutas que viaja al LLM. */
  function rutasDelEnum(): string[] {
    const navegar = toolsOpenAI().find((t) => t.function.name === 'navegar')!;
    return (navegar.function.parameters.properties as { ruta: { enum: string[] } }).ruta.enum;
  }

  it('en empresa única /app/clientes NO está en el enum', () => {
    // Estaba, y el LLM la elegía: el operador aterrizaba en Nómina por la
    // redirección mientras el log de tools decía "Navegando a /app/clientes".
    expect(rutasDelEnum()).not.toContain('/app/clientes');
    // Y las que sí existen siguen ahí.
    expect(rutasDelEnum()).toContain('/app/nomina');
    expect(rutasDelEnum()).toContain('/app/calendario');
  });

  it('y el ejecutor la rechaza aunque el LLM la invente', async () => {
    // El enum del schema es una sugerencia; el modelo manda cadenas libres.
    const navigate = vi.fn();
    const resultado = await TOOL_EXECUTORS.navegar(
      { ruta: '/app/clientes' },
      { navigate: navigate as unknown as NavigateFunction, profile: OPERADOR, uid: null },
    );
    expect(resultado.ok).toBe(false);
    expect(navigate).not.toHaveBeenCalled();
  });

  it('la descripción que lee el LLM no promete una cartera', () => {
    const navegar = toolsOpenAI().find((t) => t.function.name === 'navegar')!;
    const props = navegar.function.parameters.properties as { ruta: { description: string } };
    expect(props.ruta.description).toMatch(/no hay cartera de clientes/);
  });
});

describe('en modo despacho la cartera sigue navegable', () => {
  modoDespacho();

  it('/app/clientes vuelve al enum y el ejecutor navega', async () => {
    const navegar = toolsOpenAI().find((t) => t.function.name === 'navegar')!;
    const rutas = (navegar.function.parameters.properties as { ruta: { enum: string[] } }).ruta
      .enum;
    expect(rutas).toContain('/app/clientes');

    const navigate = vi.fn();
    const resultado = await TOOL_EXECUTORS.navegar(
      { ruta: '/app/clientes' },
      { navigate: navigate as unknown as NavigateFunction, profile: OPERADOR, uid: null },
    );
    expect(resultado.ok).toBe(true);
    expect(navigate).toHaveBeenCalledWith('/app/clientes');
  });
});
