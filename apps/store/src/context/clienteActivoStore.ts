/**
 * Contexto y hook del cliente activo (E-02).
 *
 * Vive separado de `ClienteActivoContext.tsx` para que ese archivo exporte
 * SÓLO el componente proveedor: un módulo que mezcla componentes con otras
 * exportaciones rompe el fast refresh de Vite (`react-refresh/only-export-components`).
 */

import { createContext, useContext } from 'react';
import type { ClienteResumen } from '../services/despachoApi';

export interface ClienteActivoContextType {
  clientes: ClienteResumen[];
  clienteId: string | null;
  cliente: ClienteResumen | null;
  loading: boolean;
  error: string | null;
  setClienteId: (id: string) => void;
  recargar: () => void;
}

export const ClienteActivoContext = createContext<ClienteActivoContextType | null>(null);

export function useClienteActivo(): ClienteActivoContextType {
  const ctx = useContext(ClienteActivoContext);
  if (!ctx) throw new Error('useClienteActivo must be used within ClienteActivoProvider');
  return ctx;
}
