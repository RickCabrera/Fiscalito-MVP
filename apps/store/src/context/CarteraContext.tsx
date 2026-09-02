/**
 * Proveedor de la cartera del despacho (G-03).
 *
 * EL ORDEN DE ARRANQUE ES LO IMPORTANTE DE ESTE ARCHIVO
 * -----------------------------------------------------
 * Regla de Ricardo: la demo funciona en TODO momento. Por eso:
 *
 * 1. `cargarCartera` **nunca lanza**: si Firestore truena, tarda o devuelve
 *    vacío, vuelve con el catálogo del backend y el motivo. El primer pintado
 *    no depende de Firestore.
 * 2. La **siembra corre después y en segundo plano**. No es precondición de
 *    renderizar: si falla, el contador ya está viendo su cartera.
 * 3. Sólo se recarga desde Firestore si la siembra escribió algo. Recargar
 *    siempre convertiría un fallo de escritura en un parpadeo.
 *
 * SÓLO CARGA PARA UN CONTADOR, igual que `ClienteActivoContext`: un
 * contribuyente no tiene cartera y pedirla dispararía trabajo inútil en cada
 * arranque de sesión.
 */

import { useCallback, useEffect, useMemo, useState, ReactNode } from 'react';
import { useAuth } from './AuthContext';
import { useProfile } from './ProfileContext';
import { esContador } from '../services/navigation';
import type { EmpleadoCartera, ClienteCartera } from '../services/carteraApi';
import {
  borrarCliente as borrarClienteFs,
  borrarEmpleado as borrarEmpleadoFs,
  cargarCartera,
  guardarCliente as guardarClienteFs,
  guardarEmpleado as guardarEmpleadoFs,
  sembrarDemo,
  type OrigenCartera,
} from '../services/carteraFirestore';
import { CarteraContext } from './carteraStore';

/**
 * El estado guarda PARA QUÉ uid se cargó, y `loading` se DERIVA de comparar esa
 * clave con la actual. Es el patrón de `ClienteDetallePage` (`resultado.id === id`)
 * y evita llamar a setState sincrónicamente dentro del efecto, que dispara
 * renders en cascada. De paso arregla algo real: al cambiar de cuenta, la
 * cartera de la anterior deja de mostrarse sola.
 */
interface Estado {
  /** El uid al que pertenece esto. `undefined` = todavía no se cargó nada. */
  para: string | null | undefined;
  clientes: ClienteCartera[];
  origen: OrigenCartera;
  motivoFallback: string | null;
  error: string | null;
}

const INICIAL: Estado = {
  para: undefined,
  clientes: [],
  origen: 'backend',
  motivoFallback: null,
  error: null,
};

export function CarteraProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const { profile } = useProfile();
  const habilitado = esContador(profile.contributorType);
  const uid = user?.uid ?? null;

  const [estado, setEstado] = useState<Estado>(INICIAL);
  const [intento, setIntento] = useState(0);

  useEffect(() => {
    if (!habilitado) return;

    let cancelado = false;
    cargarCartera(uid)
      .then(async (cargada) => {
        if (cancelado) return;
        setEstado({
          para: uid,
          clientes: cargada.clientes,
          origen: cargada.origen,
          motivoFallback: cargada.motivoFallback,
          error: null,
        });

        // Siembra en segundo plano. La pantalla YA pintó. Si esto falla, el
        // contador sigue viendo el catálogo del backend y el motivo del
        // fallback ya está en pantalla: no se convierte un fallo de escritura
        // en una pantalla vacía.
        if (uid && cargada.origen === 'backend') {
          try {
            if (await sembrarDemo(uid)) {
              const conSemilla = await cargarCartera(uid);
              if (!cancelado && conSemilla.origen === 'firestore') {
                setEstado({
                  para: uid,
                  clientes: conSemilla.clientes,
                  origen: 'firestore',
                  motivoFallback: null,
                  error: null,
                });
              }
            }
          } catch {
            // Sembrar es best-effort por diseño. El estado de arriba se queda.
          }
        }
      })
      .catch((e: unknown) => {
        // `cargarCartera` no lanza; esto es la red por si algún día lo hace.
        if (cancelado) return;
        setEstado({
          ...INICIAL,
          para: uid,
          error: e instanceof Error ? e.message : 'No se pudo cargar la cartera',
        });
      });

    return () => { cancelado = true; };
  }, [habilitado, uid, intento]);

  const recargar = useCallback(() => setIntento((n) => n + 1), []);
  // `loading` derivado: cierto mientras lo cargado no sea de este uid.
  const alDia = estado.para === uid;
  const cargando = habilitado && !alDia;
  const soloLectura = !alDia || estado.origen === 'backend' || !uid;

  const escribir = useCallback(
    async (accion: () => Promise<void>) => {
      if (soloLectura) {
        throw new Error(
          'Esta cartera es el catálogo de demostración y no se puede modificar. ' +
            'Revisa que tu cuenta tenga permiso de escritura en Firestore.',
        );
      }
      await accion();
      setIntento((n) => n + 1);
    },
    [soloLectura],
  );

  const valor = useMemo(
    () => ({
      clientes: alDia ? estado.clientes : [],
      loading: cargando,
      origen: estado.origen,
      motivoFallback: alDia ? estado.motivoFallback : null,
      soloLectura,
      error: alDia ? estado.error : null,
      clientePorId: (id: string) =>
        (alDia ? estado.clientes.find((c) => c.id === id) : null) ?? null,
      guardarCliente: (c: Omit<ClienteCartera, 'empleados'>) =>
        escribir(() => guardarClienteFs(uid as string, c)),
      borrarCliente: (id: string) => escribir(() => borrarClienteFs(uid as string, id)),
      guardarEmpleado: (clienteId: string, e: EmpleadoCartera) =>
        escribir(() => guardarEmpleadoFs(uid as string, clienteId, e)),
      borrarEmpleado: (clienteId: string, empleadoNo: string) =>
        escribir(() => borrarEmpleadoFs(uid as string, clienteId, empleadoNo)),
      recargar,
    }),
    [estado, alDia, cargando, soloLectura, uid, escribir, recargar],
  );

  return <CarteraContext.Provider value={valor}>{children}</CarteraContext.Provider>;
}
