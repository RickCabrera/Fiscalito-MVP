/**
 * AgentContext — estado compartido entre las tools del agente y los tabs de Fiscalito.
 *
 * Por qué existe:
 *  - Las tools `cargar_xmls_demo` y `calcular_predeclaracion` necesitan leer y
 *    escribir `facturas` y `resultado` que hoy viven dentro de PreDeclaracionTab.
 *  - El panel de actividad del agente (Aditamento C) necesita un feed con cada
 *    tool call que el LLM dispare.
 *
 * Diseño:
 *  - El context expone `state` con valores actuales y `actions` con setters.
 *    Las tools NO usan los hooks de React directamente (no son componentes) —
 *    usan `getAgentSnapshot()` y `getAgentActions()` que leen y escriben sobre
 *    refs vivas. Esto evita "stale closures" en el voice loop.
 *  - PreDeclaracionTab sigue siendo el "owner" visual de facturas/resultado,
 *    pero los sincroniza al context con un useEffect. Cuando una tool muta el
 *    estado del agente, el useEffect inverso del tab refleja el cambio.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import type { CFDI, PreDeclaracionResponse } from '../services/fiscalAgentApi';
import type { AgentSharedState, ToolCallLogEntry } from './types';

interface AgentContextValue {
  // ── Estado reactivo (para componentes que renderizan UI) ──
  facturas: CFDI[];
  resultado: PreDeclaracionResponse | null;
  periodoYear: number;
  periodoMonth: number;
  toolCallLog: ToolCallLogEntry[];

  // ── Setters ──
  setFacturas: (facturas: CFDI[]) => void;
  setResultado: (resultado: PreDeclaracionResponse | null) => void;
  setPeriodo: (year: number, month: number) => void;

  // ── API para el feed de actividad ──
  pushToolCall: (entry: ToolCallLogEntry) => void;
  updateToolCall: (id: string, patch: Partial<ToolCallLogEntry>) => void;
  clearToolCallLog: () => void;
}

const AgentContext = createContext<AgentContextValue | null>(null);

// ── Refs vivas para acceso desde las tools (que no son componentes) ──
//
// Estas refs se actualizan dentro del provider en cada cambio de estado. Las
// tools llaman `getAgentSnapshot()` / `getAgentActions()` para leer/escribir
// SIN depender del closure de React. Es el mismo truco que useVoiceChat.ts usa
// con `profileRef` y `chatHistoryRef`.

const stateRef: { current: AgentSharedState } = {
  current: {
    facturas: [],
    resultado: null,
    periodoYear: new Date().getFullYear(),
    periodoMonth: new Date().getMonth() + 1,
  },
};

const actionsRef: {
  current: Pick<
    AgentContextValue,
    'setFacturas' | 'setResultado' | 'setPeriodo' | 'pushToolCall' | 'updateToolCall'
  > | null;
} = { current: null };

/** Lectura síncrona del estado del agente — para usar dentro de tools. */
export function getAgentSnapshot(): AgentSharedState {
  return stateRef.current;
}

/** Acceso síncrono a los setters del agente — para usar dentro de tools. */
export function getAgentActions() {
  if (!actionsRef.current) {
    throw new Error('AgentContext no está montado. Envuelve la app con <AgentProvider>.');
  }
  return actionsRef.current;
}

// ── Provider ──

export function AgentProvider({ children }: { children: ReactNode }) {
  const [facturas, setFacturasState] = useState<CFDI[]>([]);
  const [resultado, setResultadoState] = useState<PreDeclaracionResponse | null>(null);
  const [periodoYear, setPeriodoYear] = useState(() => new Date().getFullYear());
  const [periodoMonth, setPeriodoMonth] = useState(() => new Date().getMonth() + 1);
  const [toolCallLog, setToolCallLog] = useState<ToolCallLogEntry[]>([]);

  // Mantener stateRef sincronizado con el estado para acceso desde tools.
  useEffect(() => {
    stateRef.current = { facturas, resultado, periodoYear, periodoMonth };
  }, [facturas, resultado, periodoYear, periodoMonth]);

  const setFacturas = useCallback((next: CFDI[]) => setFacturasState(next), []);
  const setResultado = useCallback((next: PreDeclaracionResponse | null) => setResultadoState(next), []);
  const setPeriodo = useCallback((year: number, month: number) => {
    setPeriodoYear(year);
    setPeriodoMonth(month);
  }, []);
  const pushToolCall = useCallback((entry: ToolCallLogEntry) => {
    setToolCallLog((prev) => [...prev, entry]);
  }, []);
  const updateToolCall = useCallback((id: string, patch: Partial<ToolCallLogEntry>) => {
    setToolCallLog((prev) => prev.map((e) => (e.id === id ? { ...e, ...patch } : e)));
  }, []);
  const clearToolCallLog = useCallback(() => setToolCallLog([]), []);

  // Mantener actionsRef sincronizado.
  useEffect(() => {
    actionsRef.current = {
      setFacturas,
      setResultado,
      setPeriodo,
      pushToolCall,
      updateToolCall,
    };
  }, [setFacturas, setResultado, setPeriodo, pushToolCall, updateToolCall]);

  const value = useMemo<AgentContextValue>(
    () => ({
      facturas,
      resultado,
      periodoYear,
      periodoMonth,
      toolCallLog,
      setFacturas,
      setResultado,
      setPeriodo,
      pushToolCall,
      updateToolCall,
      clearToolCallLog,
    }),
    [
      facturas, resultado, periodoYear, periodoMonth, toolCallLog,
      setFacturas, setResultado, setPeriodo, pushToolCall, updateToolCall, clearToolCallLog,
    ],
  );

  return <AgentContext.Provider value={value}>{children}</AgentContext.Provider>;
}

export function useAgent() {
  const ctx = useContext(AgentContext);
  if (!ctx) throw new Error('useAgent must be used within AgentProvider');
  return ctx;
}

/**
 * Hook auxiliar para que un tab "ceda" su estado local al AgentContext.
 * Sincroniza facturas/resultado/periodo desde el tab hacia el context.
 *
 * Uso típico en un tab:
 *   useSyncTabToAgent({ facturas, resultado, year, month });
 *
 * Para sincronía inversa (cuando una tool del agente cambió el estado), el
 * tab puede leer `useAgent().facturas` y reaccionar con su propio efecto.
 */
export function useSyncTabToAgent({
  facturas,
  resultado,
  year,
  month,
}: {
  facturas: CFDI[];
  resultado: PreDeclaracionResponse | null;
  year: number;
  month: number;
}) {
  const { setFacturas, setResultado, setPeriodo } = useAgent();

  useEffect(() => {
    setFacturas(facturas);
  }, [facturas, setFacturas]);

  useEffect(() => {
    setResultado(resultado);
  }, [resultado, setResultado]);

  useEffect(() => {
    setPeriodo(year, month);
  }, [year, month, setPeriodo]);
}
