/**
 * Contexto y hook de la cartera del despacho (G-03).
 *
 * Vive separado del proveedor para que ese archivo exporte SÓLO el componente:
 * mezclar componentes con otras exportaciones rompe el fast refresh de Vite.
 *
 * REEMPLAZA A `clienteActivoStore` COMO FUENTE DEL DATO
 * ----------------------------------------------------
 * `ClienteActivoContext` (E-02) leía `GET /despacho/clientes`, que devuelve
 * resúmenes SIN empleados. La cartera de G-01 sí los trae, y por eso hay un
 * contexto nuevo en vez de ensanchar el viejo: quien necesita empleados los pide
 * aquí, y quien sólo necesita el cliente en foco sigue con el otro.
 *
 * **Las tres costuras que leían el backend por su cuenta** —el proveedor del
 * cliente activo, la ficha del cliente y `useNominaCliente`— pasan por aquí. Si
 * alguna se quedara llamando `obtenerCliente()`, un alta nueva no aparecería en
 * el cálculo y el criterio de G-01 fallaría **en silencio**.
 */

import { createContext, useContext } from 'react';
import type { EmpleadoCartera } from '../services/carteraApi';
import type { ClienteCartera } from '../services/carteraApi';
import type { OrigenCartera } from '../services/carteraFirestore';

export interface CarteraContextType {
  clientes: ClienteCartera[];
  loading: boolean;
  /** `backend` = se está viendo el catálogo de demostración, sin escritura. */
  origen: OrigenCartera;
  /** Por qué se cayó al backend, si pasó. La pantalla lo dice, no lo esconde. */
  motivoFallback: string | null;
  /** `true` cuando no se puede escribir: la cartera no es del usuario. */
  soloLectura: boolean;
  error: string | null;

  clientePorId: (id: string) => ClienteCartera | null;
  guardarCliente: (cliente: Omit<ClienteCartera, 'empleados'>) => Promise<void>;
  borrarCliente: (clienteId: string) => Promise<void>;
  guardarEmpleado: (clienteId: string, empleado: EmpleadoCartera) => Promise<void>;
  borrarEmpleado: (clienteId: string, empleadoNo: string) => Promise<void>;
  recargar: () => void;
}

export const CarteraContext = createContext<CarteraContextType | null>(null);

export function useCartera(): CarteraContextType {
  const ctx = useContext(CarteraContext);
  if (!ctx) throw new Error('useCartera debe usarse dentro de CarteraProvider');
  return ctx;
}
