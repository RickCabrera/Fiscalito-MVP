/**
 * Cómo la cartera se colapsa a UNA empresa. (O-01)
 *
 * VIVE APARTE DE `CarteraContext` POR EL TOPE DE 300 LÍNEAS
 * ---------------------------------------------------------
 * `apps/store/CLAUDE.md` lo pone en la sección NUNCA, y esta tarea llevó ese
 * archivo de 223 a 413. La deuda de archivos por encima del tope lleva dos
 * corridas anotada en `backlog.md` §G punto 4; ésta no se suma a la pila.
 *
 * El corte no es arbitrario: aquí queda **todo lo que sólo existe en modo
 * empresa única** —la proyección, la ficha y sus dos escrituras— y allá se
 * queda la cartera, que es lo que los dos modos comparten.
 *
 * UN SOLO ORIGEN: EL DOCUMENTO `users/{uid}/clientes/empresa`
 * -----------------------------------------------------------
 * La ficha, los empleados y el periodo salen de ahí. No hay una segunda copia
 * en el perfil: la prima de riesgo entra directo al ramo de Riesgos de Trabajo
 * de `cuotas.py`, y dos copias de ese número es cobrar mal el día que divergen.
 */

import { useCallback, useMemo } from 'react';
import type { ClienteCartera } from '../services/carteraApi';
import { guardarCliente as guardarClienteFs } from '../services/cartera';
import {
  SIN_PERIODO,
  aClienteCartera,
  deClienteCartera,
  type ConfigEmpresa,
} from '../services/empresa';
import { ID_EMPRESA } from '../services/modoEmpresa';

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

  /**
   * **El periodo vacío se OMITE del documento, no se escribe.**
   *
   * `SIN_PERIODO` son cadenas vacías, que es lo que la pantalla necesita para
   * pintar dos inputs de fecha en blanco. Pero escribirlas al documento rompe
   * el contrato del backend en cuanto se encienda el interruptor de R-07:
   * `ClienteCarteraSchema.periodo_sugerido` es `PeriodoNomina | None` y `''`
   * **no es una fecha válida** — el primer guardado de la Configuración de
   * empresa daría 422, con la app rota justo el día de encender el backend.
   *
   * Omitir el campo sí es válido en los dos lados: el schema lo declara con
   * default `None`, y `setDoc(..., { merge: true })` simplemente no lo toca.
   *
   * El cast es deliberado y está acotado a esta línea: `guardarCliente` recibe
   * la ficha completa por tipo, y ésta es la única que legítimamente viaja sin
   * periodo. Ensanchar la firma del despachador para expresarlo obligaría a
   * tocar sus dos implementaciones y sus tests por un caso de borde.
   */
  if (!ficha.periodo_sugerido.inicio) {
    const { periodo_sugerido: _sinPeriodo, ...sinFechas } = ficha;
    void _sinPeriodo;
    return sinFechas as Omit<ClienteCartera, 'empleados'>;
  }
  return ficha;
}

/**
 * Lo que `CarteraProvider` necesita saber de la empresa única.
 *
 * Recibe `escribir` en vez de reimplementar la comprobación de `soloLectura`:
 * es la misma puerta por la que pasan las otras cuatro escrituras de la
 * cartera, y tener dos sería tener dos criterios.
 */
export function useEmpresaEnLaCartera({
  empresaUnica,
  uid,
  guardados,
  visibles,
  escribir,
}: {
  empresaUnica: boolean;
  uid: string | null;
  /** Lo que se leyó del almacén, sin filtrar. */
  guardados: ClienteCartera[];
  /** Lo que el modo despacho enseñaría, ya filtrado por R-06. */
  visibles: ClienteCartera[];
  escribir: (accion: () => Promise<void>) => Promise<void>;
}) {
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
  const guardadoDeLaEmpresa = useMemo(
    () => guardados.find((c) => c.id === ID_EMPRESA) ?? null,
    [guardados],
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
   * duplica nada.
   *
   * **NO ESCRIBE CUANDO NO HAY FICHA GUARDADA, Y ESO ES EL ARREGLO.**
   *
   * Una versión anterior caía a `EMPRESA_POR_DEFECTO` en ese caso y decía "no
   * pisa lo capturado". Era falso: `aClienteCartera` **siempre** emite
   * `nombre: ''` y `prima_riesgo: ''`, y `setDoc(..., { merge: true })` no
   * protege un campo que viaja con valor vacío — lo sobrescribe. Dos caminos
   * reales llegaban ahí con la ficha ya guardada:
   *
   * 1. Guardar la empresa en Perfil e ir a dar de alta un empleado **antes** de
   *    que resuelva la relectura: en esa ventana `guardadoDeLaEmpresa` sigue en
   *    `null` aunque el documento ya exista en Firestore.
   * 2. Una segunda pestaña abierta desde antes, con su estado frío.
   *
   * En los dos, el alta de un empleado borraba la razón social y **la prima de
   * riesgo**, que entra directo al ramo de Riesgos de Trabajo de `cuotas.py`:
   * dejar de cobrar una cuota patronal, en silencio, por dar de alta a alguien.
   *
   * Que no escriba es seguro porque el documento sólo puede faltar si la
   * empresa nunca se configuró, y ese caso lo bloquea `guardarEmpleado` con su
   * propio motivo (abajo) además de la pantalla. Quien crea el documento es
   * `guardarEmpresa`, que es el único lugar donde alguien captura esos datos.
   */
  const asegurarEmpresa = useCallback(async () => {
    if (!empresaUnica || !uid || !guardadoDeLaEmpresa) return;
    await guardarClienteFs(
      uid,
      fichaSinEmpleados(deClienteCartera(guardadoDeLaEmpresa), guardadoDeLaEmpresa),
    );
  }, [empresaUnica, uid, guardadoDeLaEmpresa]);

  /**
   * Guarda la Configuración de empresa (O-01).
   *
   * Escribe **el mismo documento** que todo lo demás lee, y por el mismo
   * despachador (`services/cartera.ts`), así que el día que se encienda el
   * interruptor de R-07 esto pasa por el backend sin cambiar de camino.
   *
   * Pasa por `escribir`, como las otras cuatro escrituras: era la única que no
   * lo hacía, así que no comprobaba `soloLectura`. Hoy lo tapaba el `disabled`
   * del botón, que es una propiedad del DOM y no una garantía — el defecto que
   * la corrida G reintrodujo dos veces.
   */
  const guardarEmpresa = useCallback(
    async (config: ConfigEmpresa) =>
      escribir(async () => {
        if (!uid) throw new Error('Hace falta una sesión para guardar la empresa.');
        await guardarClienteFs(uid, fichaSinEmpleados(config, guardadoDeLaEmpresa));
      }),
    [uid, guardadoDeLaEmpresa, escribir],
  );
  return { guardadoDeLaEmpresa, clientesDelModo, asegurarEmpresa, guardarEmpresa };
}
