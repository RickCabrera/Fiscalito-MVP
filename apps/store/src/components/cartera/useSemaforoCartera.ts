/**
 * Semáforo SAT de la cartera (P1-05/P1-04) indexado por clave de cliente.
 *
 * Es información complementaria de la lista: si el servidor no responde, la lista se pinta
 * igual y sólo faltan los indicadores (el error queda en `error` para quien quiera mostrarlo).
 *
 * El cliente HTTP se importa PEREZOSO: `ClientesPage` se monta en muchas suites que no
 * tienen llaves de Firebase, y un import estático de `api.ts` → `firebase.ts` las tumbaría
 * al cargar (ver `sinLlavesDeFirebase.test.ts`). Así la página no arrastra Firebase y la
 * falla, si la hay, cae en el `.catch` como cualquier error de red.
 */

import { useEffect, useState } from 'react';
import type { SemaforoCliente } from '../../services/semaforoSat';

export function useSemaforoCartera(activo: boolean, recarga = 0): {
  porClave: Record<string, SemaforoCliente>;
  error: string | null;
} {
  const [porClave, setPorClave] = useState<Record<string, SemaforoCliente>>({});
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!activo) return;
    let vigente = true;
    import('../../services/satVerificacionApi')
      .then((m) => m.semaforoCartera())
      .then((lista) => {
        if (!vigente) return;
        setPorClave(Object.fromEntries(lista.map((c) => [c.clave, c])));
        setError(null);
      })
      .catch((e: unknown) => {
        if (vigente) setError(e instanceof Error ? e.message : 'No se pudo cargar el semáforo SAT.');
      });
    return () => { vigente = false; };
  }, [activo, recarga]);

  return { porClave, error };
}
