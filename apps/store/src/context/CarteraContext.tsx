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
 * 2. La **siembra ya no corre sola**: es `sembrar()`, detrás de un botón. Ver
 *    su docstring — escribir salarios de terceros en un Firestore cuyas reglas
 *    nadie ha revisado no debe ser efecto colateral de un login.
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

  /**
   * Copia los tres clientes de demostración a la cuenta del contador.
   *
   * **Es un acto explícito, no automático, y eso es una desviación consciente
   * del enunciado de G-03** ("los 3 demo se siembran para cuentas nuevas").
   * Sembrar en el primer login escribiría el salario de trabajadores de terceros
   * —montos reales del CFDI, aunque con nombres anonimizados— en un Firestore
   * cuyas reglas **nadie ha revisado todavía**: `firestore.rules` está
   * versionado y sin desplegar. Hacerlo en segundo plano convertiría esa
   * escalada de sensibilidad en un efecto colateral en vez de una decisión.
   * Cuesta un clic y la demo funciona igual sin darlo.
   */
  const sembrar = useCallback(async () => {
    if (!uid) throw new Error('Hace falta una sesión para guardar la cartera.');
    await sembrarDemo(uid);
    setIntento((n) => n + 1);
  }, [uid]);
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
        escribir(() =>
          guardarClienteFs(uid as string, {
            ...c,
            // Un cliente nuevo no trae periodo sugerido y sin él su nómina
            // arrancaría con las fechas vacías. Se copia del que ya está en la
            // cartera en vez de calcularlo aquí: `quincena(hoy)` vive en
            // `demo_nomina.py` y replicarla en TypeScript sería una segunda
            // verdad sobre qué periodo se calcula.
            //
            // **Y lo copiado puede estar vencido**, que es distinto de lo que
            // decía este comentario antes: lo que hay en Firestore es un
            // snapshot del momento de sembrar, no `quincena(hoy)` reevaluado.
            // Por eso `cargarCartera` refresca el periodo de TODA la cartera
            // contra el backend al leerla; esto sólo tiene que dejar algo
            // coherente mientras tanto.
            periodo_sugerido: c.periodo_sugerido.inicio
              ? c.periodo_sugerido
              : estado.clientes[0]?.periodo_sugerido ?? c.periodo_sugerido,
          }),
        ),
      borrarCliente: (id: string) => escribir(() => borrarClienteFs(uid as string, id)),
      guardarEmpleado: (clienteId: string, e: EmpleadoCartera) =>
        escribir(() => guardarEmpleadoFs(uid as string, clienteId, e)),
      borrarEmpleado: (clienteId: string, empleadoNo: string) =>
        escribir(() => borrarEmpleadoFs(uid as string, clienteId, empleadoNo)),
      sembrar,
      recargar,
    }),
    [estado, alDia, cargando, soloLectura, uid, escribir, sembrar, recargar],
  );

  return <CarteraContext.Provider value={valor}>{children}</CarteraContext.Provider>;
}
