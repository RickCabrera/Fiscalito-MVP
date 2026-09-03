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
 * **Eran CUATRO las costuras que leían el backend por su cuenta.** Las tres
 * primeras —la lista de `ClientesPage`, la ficha del cliente y
 * `useNominaCliente`— pasaron por aquí en G-03. La cuarta, el proveedor del
 * cliente activo, se dejó fuera "a propósito" con este argumento: *sólo
 * necesita resúmenes para el selector del header, y el cliente en foco existe
 * en las dos fuentes*.
 *
 * **Esa última frase era verdadera sólo por el fallback**, y R-06 lo eliminó.
 * Sin el fallback, una cuenta nueva veía su lista correctamente vacía y el
 * selector de arriba mostrando los tres clientes de demostración, con
 * `/app/nomina` llevando a `demo`. Así que la cuarta costura también pasa por
 * aquí: `ClienteActivoContext` deriva sus resúmenes de esta cartera, y por eso
 * `CarteraProvider` va **por fuera** de él en `main.tsx`.
 *
 * Que la lista faltara no era un detalle: se pintaba desde el backend mientras
 * el alta escribía aquí, así que un cliente recién capturado **no aparecía
 * nunca**, sin error y sin mensaje.
 */

import { createContext, useContext } from 'react';
import type { EmpleadoCartera } from '../services/carteraApi';
import type { ClienteCartera } from '../services/carteraApi';
import type { ConfigEmpresa } from '../services/empresa';
import type { OrigenCartera } from '../services/carteraFirestore';

export interface CarteraContextType {
  clientes: ClienteCartera[];
  loading: boolean;
  /** `backend` = se está viendo el catálogo de demostración, sin escritura. */
  origen: OrigenCartera;
  /** `true` cuando no se puede escribir: la cartera no es del usuario. */
  soloLectura: boolean;
  error: string | null;

  clientePorId: (id: string) => ClienteCartera | null;
  guardarCliente: (cliente: Omit<ClienteCartera, 'empleados'>) => Promise<void>;
  borrarCliente: (clienteId: string) => Promise<void>;
  guardarEmpleado: (clienteId: string, empleado: EmpleadoCartera) => Promise<void>;
  borrarEmpleado: (clienteId: string, empleadoNo: string) => Promise<void>;
  /**
   * Copia los 3 clientes de demostración a la cuenta. **Explícito a propósito**:
   * escribe salarios de terceros en Firestore, y esa escalada no debe ocurrir
   * como efecto colateral del primer login. Ver `CarteraContext`.
   */
  sembrar: () => Promise<void>;
  recargar: () => void;

  /**
   * La configuración de la empresa única (O-01), leída del **mismo documento**
   * que el resto de la cartera: `users/{uid}/clientes/empresa`.
   *
   * En modo despacho vale los defaults y nadie la lee. No se hace opcional para
   * no obligar a cada consumidor a decidir qué hacer con `undefined`: la
   * pantalla de configuración sólo se monta en modo empresa única.
   */
  empresa: ConfigEmpresa;
  /** Guarda la Configuración de empresa. Escribe la ficha del cliente implícito. */
  guardarEmpresa: (config: ConfigEmpresa) => Promise<void>;
}

export const CarteraContext = createContext<CarteraContextType | null>(null);

export function useCartera(): CarteraContextType {
  const ctx = useContext(CarteraContext);
  if (!ctx) throw new Error('useCartera debe usarse dentro de CarteraProvider');
  return ctx;
}
