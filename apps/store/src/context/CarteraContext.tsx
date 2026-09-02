/**
 * Proveedor de la cartera del despacho (G-03, R-06).
 *
 * LA CARTERA ES DEL USUARIO, Y SÓLO DEL USUARIO
 * ---------------------------------------------
 * `cargarCartera` **nunca lanza**, pero desde R-06 tampoco sustituye. Devuelve
 * una de tres cosas, y las tres son verdad sobre ESTA cuenta:
 *
 * 1. sus clientes,
 * 2. una cartera **vacía y escribible** —que es lo que ve una cuenta nueva, y
 *    no es un error—,
 * 3. un error, para que la pantalla lo diga y ofrezca reintentar.
 *
 * Lo que ya **no** hace es enseñar el catálogo de demostración cuando lo de
 * arriba falla. G-03 lo hacía a propósito para que la demo no se rompiera, y
 * este archivo lo declaraba: el fallback derrotaba el criterio de G-03 porque
 * dos cuentas veían los mismos tres clientes.
 *
 * `soloLectura` se deriva de `origen`, así que ese campo decide si el botón de
 * alta funciona: una cartera vacía tiene que venir con `origen: 'firestore'` o
 * el contador no puede crear su primer cliente.
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
  error: string | null;
}

const INICIAL: Estado = {
  para: undefined,
  clientes: [],
  origen: 'backend',
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
          error: cargada.error,
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
   * **Explícito, y desde R-06 sólo para cuentas de desarrollo.** La razón
   * original —las reglas de Firestore sin revisar— la cerró R-01. La que queda
   * es más simple: escribe el salario de trabajadores de terceros, incluido el
   * caso real con montos reales, y eso no tiene por qué acabar en la cuenta de
   * nadie que no lo haya pedido. Quién ve el botón lo decide
   * `esCuentaDeDesarrollo` (`services/entorno.ts`).
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
      soloLectura,
      error: alDia ? estado.error : null,
      clientePorId: (id: string) =>
        (alDia ? estado.clientes.find((c) => c.id === id) : null) ?? null,
      guardarCliente: (c: Omit<ClienteCartera, 'empleados'>) =>
        escribir(() =>
          guardarClienteFs(uid as string, {
            ...c,
            // Se copia del cliente que ya esté en la cartera en vez de
            // calcularlo aquí: `quincena(hoy)` vive en `demo_nomina.py` y
            // replicarla en TypeScript sería una segunda verdad sobre qué
            // periodo se calcula. Lo copiado puede estar vencido —es un
            // snapshot—, y por eso `cargarCartera` lo refresca al leer.
            //
            // **El primer cliente de una cuenta vacía nace SIN periodo, y eso
            // está bien.** Hasta R-06 este `?? ` nunca se ejercitaba porque el
            // fallback garantizaba que `estado.clientes[0]` existiera; quitado
            // el fallback, es el caso normal de toda cuenta nueva.
            //
            // Se descartó pedirle el periodo al backend aquí. Copiar la
            // QUINCENA del cliente de demostración a un cliente que puede ser
            // mensual, semanal o diario siembra el peligro que
            // `useNominaCliente` documenta —tarifa mensual del Art. 96 sobre
            // base de 15-16 días, ISR subestimado con recibo creíble— y además
            // haría que el alta de un cliente real dependiera del endpoint del
            // catálogo demo, que es la costura que R-06 viene a cortar.
            //
            // `conPeriodoAlDia` ya repara esto al LEER, con cota y tolerando el
            // fallo. Y la pantalla de nómina avisa cuando el periodo llega
            // vacío, que es donde las fechas se usan y donde el operador puede
            // hacer algo: sus dos inputs son libres.
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
