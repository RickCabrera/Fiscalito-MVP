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
// R-07: quién es el dueño del dato lo decide `services/cartera.ts`. Este
// archivo no sabe si detrás hay Firestore o el backend, y ésa es la idea: el
// interruptor se prueba y se enciende en un solo lugar.
import {
  borrarCliente as borrarClienteFs,
  borrarEmpleado as borrarEmpleadoFs,
  cargarCartera,
  guardarCliente as guardarClienteFs,
  guardarEmpleado as guardarEmpleadoFs,
  sembrarDemo,
  type OrigenCartera,
} from '../services/cartera';
import { esClienteDemo, esCuentaDeDesarrollo } from '../services/entorno';
import { ID_EMPRESA, modoEmpresaUnica } from '../services/modoEmpresa';
import {
  EMPRESA_POR_DEFECTO,
  SIN_PERIODO,
  aClienteCartera,
  deClienteCartera,
  type ConfigEmpresa,
} from '../services/empresa';
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

/**
 * La ficha de la empresa, sin sus empleados.
 *
 * `guardarCliente` escribe el DOCUMENTO del cliente; los empleados son su
 * subcolección y se escriben aparte. Mandarlos aquí los duplicaría dentro del
 * documento padre, y la siguiente lectura los traería por dos caminos.
 */
function fichaSinEmpleados(
  config: ConfigEmpresa,
  guardado: ClienteCartera | null,
): Omit<ClienteCartera, 'empleados'> {
  const { empleados, ...ficha } = aClienteCartera(
    config,
    [],
    guardado?.periodo_sugerido ?? SIN_PERIODO,
  );
  void empleados;
  return ficha;
}

export function CarteraProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const { profile } = useProfile();
  const habilitado = esContador(profile.contributorType);
  const uid = user?.uid ?? null;

  const [estado, setEstado] = useState<Estado>(INICIAL);
  const [intento, setIntento] = useState(0);
  const cuentaDeDesarrollo = esCuentaDeDesarrollo(user?.email);

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

  /**
   * R-06(b): los clientes de DEMOSTRACIÓN sólo existen para una cuenta de
   * desarrollo, **incluso si ya están escritos en su Firestore**.
   *
   * Se filtra aquí y no en la pantalla porque la cartera alimenta cuatro cosas
   * —la lista, el selector superior, la ficha y la nómina— y filtrar en una
   * sola dejaba a las otras tres enseñándolos. Y hace falta de verdad: no basta
   * con que R-06 quite el fallback. Cualquier cuenta donde se haya clickeado
   * "Guardar esta cartera en mi cuenta" durante G-03 o la demo **ya tiene los
   * tres escritos**, y sin este filtro los seguiría viendo en producción — el
   * del caso real incluido, con el salario de nueve personas.
   *
   * **No se borran de Firestore.** Ocultar es reversible y borrar no; si hay
   * que limpiarlos, es una decisión de Ricardo y una tarea propia.
   */
  const visibles = useMemo(
    () =>
      cuentaDeDesarrollo
        ? estado.clientes
        : estado.clientes.filter((c) => !esClienteDemo(c.origen)),
    [estado.clientes, cuentaDeDesarrollo],
  );

  /**
   * O-01 · LA CARTERA SE COLAPSA A UNA SOLA EMPRESA.
   *
   * Se proyecta aquí, en el proveedor, y no en cada pantalla, por la misma
   * razón por la que R-06 puso aquí el filtro de clientes de demostración: la
   * cartera alimenta cuatro cosas —empleados, dispositivos, nómina y el
   * encabezado— y hacerlo en una sola dejaba a las otras tres viendo otra cosa.
   *
   * **Un solo origen: el documento `users/{uid}/clientes/empresa`.** La ficha,
   * los empleados y el periodo salen de ahí; si no existe todavía —cuenta
   * recién creada— se proyectan los defaults, que es una empresa sin configurar
   * y no un error. Es a propósito que no haya una segunda copia en el perfil:
   * la prima de riesgo entra directo al ramo de Riesgos de Trabajo de
   * `cuotas.py`, y dos copias de ese número es cobrar mal el día que divergen.
   *
   * El filtro de R-06 no se aplica en este modo y no hace falta: la empresa
   * nace con `origen: 'propio'` y los clientes de demostración que pudiera
   * tener la cuenta —de la siembra de G-03— simplemente no se proyectan.
   * Quedan invisibles por construcción, no por filtro.
   */
  const empresaUnica = modoEmpresaUnica();
  const guardadoDeLaEmpresa = useMemo(
    () => estado.clientes.find((c) => c.id === ID_EMPRESA) ?? null,
    [estado.clientes],
  );

  const clientesDelModo = useMemo(() => {
    if (!empresaUnica) return visibles;
    return [
      aClienteCartera(
        deClienteCartera(guardadoDeLaEmpresa),
        guardadoDeLaEmpresa?.empleados ?? [],
        guardadoDeLaEmpresa?.periodo_sugerido ?? SIN_PERIODO,
      ),
    ];
  }, [empresaUnica, visibles, guardadoDeLaEmpresa]);

  /**
   * Se asegura de que el documento de la empresa exista antes de escribirle un
   * empleado.
   *
   * Hace falta de verdad: `leerDeFirestore` lista los DOCUMENTOS de
   * `users/{uid}/clientes`, y en Firestore un documento que sólo tiene
   * subcolecciones **no aparece** en esa lista. Sin esto, el primer empleado se
   * guardaría bien y la cartera volvería vacía en la siguiente lectura — el
   * empleado existiría, invisible, y el operador lo daría de alta otra vez.
   *
   * Es `setDoc` idempotente sobre el mismo id, así que llamarlo de más no
   * duplica nada; y va antes de cada alta, no una sola vez al arrancar, porque
   * el documento puede haberse borrado desde otra pestaña.
   *
   * **No pisa lo capturado**: si el documento ya existe, se reescribe con lo
   * que ya tenía. Sólo cuando no existe nace con los defaults.
   */
  const asegurarEmpresa = useCallback(async () => {
    if (!empresaUnica || !uid) return;
    const config = guardadoDeLaEmpresa
      ? deClienteCartera(guardadoDeLaEmpresa)
      : EMPRESA_POR_DEFECTO;
    await guardarClienteFs(uid, fichaSinEmpleados(config, guardadoDeLaEmpresa));
  }, [empresaUnica, uid, guardadoDeLaEmpresa]);

  /**
   * Guarda la Configuración de empresa (O-01).
   *
   * Escribe **el mismo documento** que todo lo demás lee, y por el mismo
   * despachador (`services/cartera.ts`), así que el día que se encienda el
   * interruptor de R-07 esto pasa por el backend sin tocar una línea.
   */
  const guardarEmpresa = useCallback(
    async (config: Parameters<typeof aClienteCartera>[0]) => {
      if (!uid) throw new Error('Hace falta una sesión para guardar la empresa.');
      await guardarClienteFs(uid, fichaSinEmpleados(config, guardadoDeLaEmpresa));
      setIntento((n) => n + 1);
    },
    [uid, guardadoDeLaEmpresa],
  );

  const valor = useMemo(
    () => ({
      clientes: alDia ? clientesDelModo : [],
      loading: cargando,
      origen: estado.origen,
      soloLectura,
      error: alDia ? estado.error : null,
      // Por `clientesDelModo`, no por `estado.clientes`: si la ficha resolviera
      // un cliente que la lista oculta, se podría entrar a su nómina por URL y
      // el filtro sería decorativo. En modo empresa única eso es lo que impide
      // que `/app/clientes/demo/nomina` —o cualquier id tecleado— resuelva algo:
      // el único id que existe es el de la empresa.
      clientePorId: (id: string) =>
        (alDia ? clientesDelModo.find((c) => c.id === id) : null) ?? null,
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
            // `conPeriodoAlDia` lo repara al LEER, con cota y tolerando el
            // fallo, así que el hueco sólo se ve con el backend caído o lento.
            // Y cuando se ve, **la pantalla de nómina lo dice**: bloquea el paso
            // 2 con el motivo y pide capturar las fechas, que sus dos inputs son
            // libres. Eso hubo que construirlo — este comentario afirmaba que
            // ya avisaba y no era cierto.
            // `clientesDelModo`, que en modo despacho ES `visibles`: son la
            // misma lista y así la lista de dependencias del `useMemo` dice la
            // verdad. En modo empresa única este camino no se alcanza — no hay
            // alta de clientes— y si algún día se alcanzara, copiaría el
            // periodo de la propia empresa, que es lo correcto.
            periodo_sugerido: c.periodo_sugerido.inicio
              ? c.periodo_sugerido
              : clientesDelModo[0]?.periodo_sugerido ?? c.periodo_sugerido,
          }),
        ),
      borrarCliente: (id: string) => escribir(() => borrarClienteFs(uid as string, id)),
      guardarEmpleado: (clienteId: string, e: EmpleadoCartera) =>
        escribir(async () => {
          await asegurarEmpresa();
          await guardarEmpleadoFs(uid as string, clienteId, e);
        }),
      borrarEmpleado: (clienteId: string, empleadoNo: string) =>
        escribir(() => borrarEmpleadoFs(uid as string, clienteId, empleadoNo)),
      sembrar,
      recargar,
      empresa: deClienteCartera(guardadoDeLaEmpresa),
      guardarEmpresa,
    }),
    [
      estado, clientesDelModo, alDia, cargando, soloLectura, uid, escribir,
      sembrar, recargar, asegurarEmpresa, guardadoDeLaEmpresa, guardarEmpresa,
    ],
  );

  return <CarteraContext.Provider value={valor}>{children}</CarteraContext.Provider>;
}
