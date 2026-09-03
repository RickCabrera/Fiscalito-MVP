/**
 * Estado del flujo de nómina de un cliente (extraído de `NominaClientePage` en
 * E-06). DEMO: se borra en F2 con la épica.
 *
 * Todo lo que la pantalla SABE vive aquí; la pantalla sólo lo pinta. La razón
 * de partirlo no es sólo el tope de 300 líneas de `apps/store/CLAUDE.md`: las
 * reglas de abajo son invariantes de datos y se entienden mejor lejos del JSX.
 *
 * LA RUTA ES LA FUENTE DE VERDAD DEL CLIENTE
 * ------------------------------------------
 * El id viene de la ruta y **el contexto se sincroniza a ella**, nunca al
 * revés. Al revés, entrar por `/app/clientes/demo/nomina` con `taller` guardado
 * en `localStorage` dejaría el selector del header diciendo "Taller" y la
 * pantalla calculando `demo`.
 *
 * CADA DATO VIAJA CON EL CLIENTE QUE LO PRODUJO
 * ---------------------------------------------
 * Nada se limpia en un efecto: todo se **deriva** comparando contra el id de la
 * ruta. Un efecto de limpieza puede olvidarse de una pieza nueva; la derivación
 * no. Sin esto, entre el cambio de ruta y la llegada de la ficha nueva los
 * botones siguen habilitados sobre los datos del cliente anterior, y "Cerrar
 * quincena" en esa ventana cierra el periodo de quien no es.
 *
 * NO HAY NI UNA CONSTANTE FISCAL AQUÍ
 * -----------------------------------
 * Empleados, prima de riesgo, periodicidad y periodo salen de
 * `GET /despacho/clientes/{id}`. **El periodo NO se deduce de las checadas**:
 * del 16 al 31 de agosto son 16 días naturales y la primera checada es del 17
 * (el 16 es domingo), así que `min`/`max` daría 15 — un día menos de base para
 * las cuotas del IMSS y un día menos pagado.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  calcularNomina,
  cerrarPeriodo,
  type EmpleadoNominaRequest,
  obtenerEventos,
  type CierrePeriodo,
  type EventoChecada,
  type NominaPeriodo,
} from '../../services/nominaDemoApi';
import { useCartera } from '../../context/carteraStore';
import { plantillaDeNomina } from './plantillaDeNomina';
import { incidenciasConLlaveDeCalculo, llavesParaElCierre } from './llavesDelCierre';
import { contarSinVincular, type EmpleadoCartera } from '../../services/carteraApi';
import { obtenerCliente, type ClienteDetalle } from '../../services/despachoApi';
import { useClienteActivo } from '../../context/clienteActivoStore';
import { modoEmpresaUnica } from '../../services/modoEmpresa';
import { faltantesDeLaEmpresa } from '../../services/empresa';

const MS_POLLING = 3000;

/**
 * Qué fecha de pago mandar.
 *
 * Los dos inputs de fecha son libres, así que el operador puede mover el
 * periodo a otro mes. Mandar la `fecha_pago` de la quincena sugerida en ese
 * caso sería calcular un periodo con la vigencia de otro: de esa fecha dependen
 * la UMA, el salario mínimo, la tarifa del Anexo 8 y el transitorio de enero
 * del subsidio (§D18).
 *
 * Cuando el periodo cambió se manda `null` y **lo resuelve el backend**. No se
 * replica aquí el default (`fecha_pago ?? fin`): esa regla vive en un solo
 * lugar, y la respuesta trae `fecha_pago_efectiva` para que la pantalla y el
 * PDF impriman lo que el motor usó.
 */
function fechaDePago(cliente: ClienteDetalle, inicio: string, fin: string): string | null {
  const sugerido = cliente.periodo_sugerido;
  const sinTocar = inicio === sugerido.inicio && fin === sugerido.fin;
  return sinTocar ? sugerido.fecha_pago : null;
}

/** Un dato que pertenece a UN cliente. Si no trae su id, no se pinta. */
type DeCliente<T> = { id: string; valor: T };

function suyo<T>(dato: DeCliente<T> | null, clienteId: string, vacio: T): T {
  return dato && dato.id === clienteId ? dato.valor : vacio;
}

export function useNominaCliente(clienteId: string) {
  const { clienteId: activo, setClienteId } = useClienteActivo();
  const [cargada, setCargada] = useState<DeCliente<ClienteDetalle> | null>(null);
  const [eventosDe, setEventosDe] = useState<DeCliente<EventoChecada[]> | null>(null);
  const [cierreDe, setCierreDe] = useState<DeCliente<CierrePeriodo | null> | null>(null);
  const [nominaDe, setNominaDe] = useState<DeCliente<NominaPeriodo | null> | null>(null);
  /**
   * El periodo PERTENECE A UN CLIENTE, con el mismo patrón `DeCliente` que ya
   * usan la ficha, las checadas, el cierre y la nómina de este archivo.
   *
   * Eran dos `useState` sueltos, y funcionaba **por accidente**: durante la
   * ventana en que la ficha del cliente nuevo viajaba, `cliente` valía `null`
   * —la cartera venía vacía en ese camino— y el botón quedaba deshabilitado por
   * esa otra razón. R-06 puebla la cartera, así que `cliente` ya resuelve al
   * instante desde ella y esa protección de rebote desapareció: quedaban las
   * fechas del cliente ANTERIOR con el botón vivo, y cerrar ahí habría cerrado
   * el periodo equivocado. Lo cazó el test de navegación entre clientes, que
   * existe justo para esto.
   */
  const [periodoDe, setPeriodoDe] = useState<DeCliente<{ inicio: string; fin: string }> | null>(null);
  const [errorPanel, setErrorPanel] = useState<string | null>(null);
  const [errorDe, setErrorDe] = useState<DeCliente<string | null> | null>(null);
  /**
   * El error de CARGAR la ficha, aparte del de las operaciones.
   *
   * Compartir estado con `errorDe` haría que anular el de carga —cuando el
   * cliente sí está en la cartera— tapara también un fallo real de cerrar o
   * calcular. Son dos cosas distintas y sólo una se puede descartar.
   */
  const [errorCargaDe, setErrorCargaDe] = useState<DeCliente<string | null> | null>(null);
  const [ocupado, setOcupado] = useState(false);
  // La confirmación es estado, no `window.confirm`. Guarda el id del cliente al
  // que corresponde, para que no sobreviva a un cambio de cliente.
  const [confirmarPara, setConfirmarPara] = useState<string | null>(null);
  const cartera = useCartera();
  // El efecto de carga NO puede depender de `cartera`: el valor del contexto
  // cambia de identidad en cada render, así que el efecto volvería a correr y
  // **revertiría las fechas que el operador acaba de mover** — lo cazó el test
  // de la fecha de pago. Se lee por ref, y el ref se actualiza en un efecto y
  // no durante el render: tocar `.current` mientras se renderiza es lo que
  // hace que un componente no se actualice como se espera.
  const carteraRef = useRef(cartera);
  useEffect(() => {
    carteraRef.current = cartera;
  });

  // El contexto SIGUE a la ruta. Al revés, el header afirmaría un cliente y la
  // pantalla calcularía otro.
  useEffect(() => {
    if (clienteId && clienteId !== activo) setClienteId(clienteId);
  }, [clienteId, activo, setClienteId]);

  /**
   * O-01: en modo empresa única **no se pide la ficha al backend**.
   *
   * `GET /despacho/clientes/{id}` sólo conoce los tres clientes de
   * demostración, así que con el id de la empresa responde 404 — en **cada
   * montaje de la pantalla principal**. Funciona igual, porque el camino del
   * `catch` ya cae a la cartera (es el caso normal desde G-03), pero es un 404
   * permanente en la red de la pantalla estrella y el error queda guardado por
   * si acaso. No hay nada que ir a buscar: la ficha de la empresa está entera
   * en la cartera, que es su único dueño.
   */
  const empresaUnica = modoEmpresaUnica();

  useEffect(() => {
    if (!clienteId || empresaUnica) return;
    let cancelado = false;
    obtenerCliente(clienteId)
      .then((c) => {
        if (cancelado) return;
        setCargada({ id: clienteId, valor: c });
        // Se limpia el error de carga: navegar A → B → A tras un reinicio de la
        // API dejaba pintado el error viejo de A aunque la ficha ya llegó bien.
        setErrorCargaDe(null);
        setPeriodoDe({
          id: clienteId,
          valor: { inicio: c.periodo_sugerido.inicio, fin: c.periodo_sugerido.fin },
        });
      })
      .catch((e: Error) => {
        if (cancelado) return;
        // Un cliente dado de alta por el contador **no tiene ficha en el
        // backend**: `GET /despacho/clientes/{id}` sólo conoce los tres de
        // demostración. Antes de G-03 eso era imposible; ahora es lo normal.
        //
        // El error se GUARDA siempre y se DECIDE al leer (ver `error`, abajo).
        // Consultar la cartera aquí dejaba el error latcheado para siempre
        // cuando el 404 ganaba la carrera —lo normal en una recarga directa: el
        // 404 es un round-trip local y la cartera es Firestore con 2500 ms de
        // tope—, porque el efecto no vuelve a correr cuando la cartera llega.
        const suyoEnCartera = carteraRef.current.clientePorId(clienteId);
        if (suyoEnCartera) {
          setPeriodoDe({
            id: clienteId,
            valor: {
              inicio: suyoEnCartera.periodo_sugerido.inicio,
              fin: suyoEnCartera.periodo_sugerido.fin,
            },
          });
        }
        setErrorCargaDe({ id: clienteId, valor: e.message });
      });
    return () => { cancelado = true; };
  }, [clienteId, empresaUnica]);



  const refrescar = useCallback(() => {
    if (!clienteId) return;
    obtenerEventos(clienteId)
      .then((r) => {
        setEventosDe({ id: clienteId, valor: r.eventos });
        setErrorPanel(null);
      })
      .catch((e: Error) => setErrorPanel(e.message));
  }, [clienteId]);

  useEffect(() => {
    refrescar();
    const id = setInterval(refrescar, MS_POLLING);
    return () => clearInterval(id);
  }, [refrescar]);

  const fichaBackend = suyo(cargada, clienteId, null);

  /**
   * El cliente con el que se calcula.
   *
   * La ficha del backend cuando existe —trae `fecha_referencia` y los factores
   * observados que la pantalla Plantilla enseña—, y si no, la de la cartera. Un
   * cliente dado de alta por el contador sólo existe en la cartera, y tiene que
   * poder correr su nómina igual.
   */
  const cliente: ClienteDetalle | null = useMemo(() => {
    if (fichaBackend) return fichaBackend;
    const c = clienteId ? cartera.clientePorId(clienteId) : null;
    if (!c) return null;
    return {
      id: c.id,
      nombre: c.nombre,
      giro: c.giro,
      origen: c.origen,
      num_empleados: c.empleados.length,
      prima_riesgo: c.prima_riesgo,
      clase_riesgo: c.clase_riesgo,
      clave_periodicidad: c.clave_periodicidad,
      zona: c.zona,
      periodo_sugerido: c.periodo_sugerido,
      // No hay fecha de referencia: este cliente no se midió contra ninguna.
      fecha_referencia: '',
      empleados: [],
    };
  }, [fichaBackend, clienteId, cartera]);

  // G-01/G-02: los empleados del CÁLCULO salen de la cartera del uid, no de la
  // ficha del backend. Si esto siguiera leyendo `cliente.empleados`, un alta
  // nueva no entraría a la nómina y el criterio de G-01 fallaría en silencio.
  //
  // Y sólo entran los VINCULADOS: sin `employee_no` no hay checadas que
  // atribuirle, y mandarlo al cierre con una llave vacía lo haría colisionar
  // con cualquier otro sin vincular. Los excluidos NO desaparecen callados —
  // `sinVincular` los cuenta y la pantalla lo dice.
  // **Mientras la cartera carga no se decide nada.** Sin esta guardia,
  // `clientePorId` devuelve `null`, la plantilla cae a la ficha del backend
  // —con todos, vinculados o no— y `sinVincular` vale 0, así que tampoco sale
  // el aviso. Entrar directo a la nómina con el proveedor frío y cerrar en esa
  // ventana calcularía una plantilla distinta a la de un segundo después.
  // R-06: SON TRES ESTADOS, NO DOS. Hasta aquí se distinguía "cargando" de
  // "cargada", y con el fallback de G-03 daba igual: `clientePorId('demo')`
  // siempre devolvía algo porque el catálogo del backend poblaba la cartera.
  //
  // Quitado ese fallback, aparece el tercero: **cargada, y el cliente NO está
  // en ella**. Entrar por URL a `/app/clientes/demo/nomina` desde una cuenta
  // cuya cartera no tiene `demo` daba `clientePorId → null`, y entonces
  // `plantillaDeNomina` caía a `deLaFicha` — la ficha COMPLETA del backend, sin
  // filtrar `estaVinculado`— con `sinVincular` en 0, así que **el aviso tampoco
  // salía**. Un conjunto distinto de empleados entrando a
  // `POST /nomina/calcular-periodo`, en silencio.
  //
  // No es hipotético: es el modo de falla que el comentario de arriba describe
  // y que la guarda de `cartera.loading` existía para evitar, reaparecido por
  // otra puerta.
  const carteraLista = Boolean(clienteId) && !cartera.loading;
  const deLaCartera = carteraLista ? cartera.clientePorId(clienteId as string) : null;
  /**
   * El cliente no es de esta cuenta. **No se calcula.**
   *
   * Distinto de "la cartera está cargando" (ahí se espera) y de "el cliente
   * está y no tiene empleados" (ahí se calcula con cero, que es correcto).
   */
  const ajenoALaCartera = carteraLista && deLaCartera === null;
  const empleadosCartera = deLaCartera?.empleados ?? null;
  const sinVincular = empleadosCartera ? contarSinVincular(empleadosCartera) : 0;

  /**
   * O-01: lo que le falta a la empresa para que su nómina signifique algo.
   *
   * Sale de `cartera.empresa` y **no** de leerle campos al cliente proyectado.
   * Son el mismo dato —los dos salen de `users/{uid}/clientes/empresa`, uno por
   * `deClienteCartera` y el otro por `aClienteCartera`— así que no hay dos
   * verdades que puedan divergir.
   *
   * La razón de preferir éste es concreta: leerle dos propiedades más a
   * `deLaCartera` aquí hacía que el React Compiler **desoptimizara el `useMemo`
   * de la plantilla** que viaja a `POST /nomina/calcular-periodo`
   * (`react-hooks/preserve-manual-memoization`: *this dependency may be modified
   * later*). Se probó moverlo antes, después y envuelto en su propio `useMemo`;
   * las tres empeoraban o no arreglaban. Leer del objeto que el proveedor ya
   * calculó no toca esa cadena.
   */
  const faltaDeLaEmpresa = empresaUnica
    ? faltantesDeLaEmpresa(cartera.empresa.razonSocial, cartera.empresa.primaRiesgo)
    : [];

  const { inicio, fin } = suyo(periodoDe, clienteId, { inicio: '', fin: '' });
  const setInicio = (v: string) => setPeriodoDe({ id: clienteId, valor: { inicio: v, fin } });
  const setFin = (v: string) => setPeriodoDe({ id: clienteId, valor: { inicio, fin: v } });

  const eventos = suyo(eventosDe, clienteId, [] as EventoChecada[]);
  const cierre = suyo(cierreDe, clienteId, null);
  const nomina = suyo(nominaDe, clienteId, null);
  /**
   * **Derivado, no latcheado.** El error de CARGA sólo cuenta si el cliente
   * tampoco está en la cartera: si la cartera llega después del 404 —lo normal
   * en una recarga directa, porque el 404 es un round-trip local y la cartera
   * es Firestore con 2500 ms de tope—, esto se auto-sana. Guardarlo ya resuelto
   * lo dejaba pegado para siempre, porque el efecto no vuelve a correr.
   *
   * El error de las OPERACIONES (cerrar, calcular) no se descarta nunca.
   */
  const error =
    suyo(errorDe, clienteId, null) ??
    // `cartera.loading` cuenta como "todavía no se sabe": sin esto, una recarga
    // directa sobre un cliente propio pintaba el 404 en rojo hasta 2500 ms y
    // luego lo quitaba solo.
    (deLaCartera || cartera.loading ? null : suyo(errorCargaDe, clienteId, null));

  /**
   * Checadas que caen DENTRO del periodo que se va a cerrar.
   *
   * No basta con `eventos.length === 0`: `obtenerEventos` no manda `desde` —a
   * propósito, ver `nominaDemoApi`— así que el panel trae todo lo que haya en
   * memoria. Sembrar el día 15 y demostrar el 16 son **dos quincenas
   * distintas** (lo advierte `demo_nomina.quincena()`): habría checadas en el
   * panel, ninguna en el periodo, y `cerrar_periodo` marcaría falta todos los
   * días sin que nadie preguntara nada.
   */
  const sinChecadasEnElPeriodo = !eventos.some((e) => {
    const dia = e.timestamp.slice(0, 10);
    return dia >= inicio && dia <= fin;
  });

  // La decisión de quién entra vive en `plantillaDeNomina`, que se prueba
  // directo: es la que carga los dos criterios de la épica.
  const plantilla: EmpleadoNominaRequest[] = useMemo(
    () => plantillaDeNomina(cliente?.empleados ?? [], empleadosCartera),
    [cliente, empleadosCartera],
  );

  /**
   * O-01: en modo empresa única el periodo se siembra desde la CARTERA.
   *
   * En modo despacho lo siembran las dos ramas del efecto de arriba. Aquí ese
   * efecto no corre, así que sin esto los dos inputs de fecha arrancarían
   * vacíos **siempre** y el paso 2 quedaría bloqueado en la pantalla principal
   * con el mensaje de R-06 ("captura las fechas"), que ahí sería un estorbo
   * permanente en vez de un aviso.
   *
   * DOS CUIDADOS QUE ESTE ARCHIVO YA PAGÓ CAROS:
   *
   * 1. **No depende de `cartera`.** El valor del contexto cambia de identidad
   *    en cada render, así que el efecto volvería a correr y revertiría las
   *    fechas que el operador acaba de mover — es el bug que cazó el test de la
   *    fecha de pago. Depende de `cartera.loading`, que es un booleano y sólo
   *    cambia una vez.
   * 2. **No pisa lo que ya hay.** El `setPeriodoDe` funcional sólo siembra si
   *    todavía no hay periodo de ESTE cliente. Sembrar incondicionalmente sería
   *    el mismo bug por la otra puerta.
   */
  useEffect(() => {
    if (!empresaUnica || !clienteId) return;
    const c = carteraRef.current.clientePorId(clienteId);
    if (!c?.periodo_sugerido.inicio) return;
    setPeriodoDe((actual) =>
      actual && actual.id === clienteId
        ? actual
        : {
            id: clienteId,
            valor: { inicio: c.periodo_sugerido.inicio, fin: c.periodo_sugerido.fin },
          },
    );
  }, [empresaUnica, clienteId, cartera.loading]);

  /**
   * El cierre vuelve con la llave del checador; los recibos se indexan por la
   * del cálculo. Sin cartera no hay con qué traducir y se deja tal cual: es el
   * camino del catálogo de demostración, donde las dos llaves coinciden.
   */
  const incidenciasDelCierre = (
    resultado: CierrePeriodo,
    deLaCarteraAhora: EmpleadoCartera[] | null,
  ): CierrePeriodo =>
    deLaCarteraAhora
      ? {
          ...resultado,
          incidencias: incidenciasConLlaveDeCalculo(resultado.incidencias, deLaCarteraAhora),
        }
      : resultado;

  /**
   * Un cliente **mensual, semanal o diario** al que se le va a calcular una
   * quincena.
   *
   * **Cubre una sola dirección, y hay que decirlo.** El caso simétrico —cliente
   * quincenal y el operador arrastra las fechas a un mes completo— aplica la
   * tarifa quincenal sobre base mensual y **tampoco lo detecta nadie**: los dos
   * inputs de fecha son libres y `periodo.py` sólo compara las incidencias
   * entre sí. Ese hueco es preexistente y sigue abierto; esto no lo tapa.
   *
   * **Nadie más lo valida.** `periodo.py` sólo comprueba que todas las
   * incidencias midan lo mismo, no que el periodo case con la clave. Un cliente
   * marcado Mensual (05) recibiría la tarifa mensual del Art. 96 sobre una base
   * de 15-16 días: **ISR subestimado, con recibo creíble y sin un solo error**.
   *
   * El alta ya sólo ofrece quincenal, pero eso no alcanza: un cliente guardado
   * antes con otra clave —o capturado durante el desarrollo de esta rama— sigue
   * vivo en Firestore y nada lo detecta. Aquí se detiene el cálculo en vez de
   * emitirlo mal.
   */
  const dias = cliente
    ? Math.round(
        (new Date(`${fin}T00:00:00`).getTime() - new Date(`${inicio}T00:00:00`).getTime()) /
          86_400_000,
      ) + 1
    : 0;
  const periodicidadNoCuadra =
    Boolean(cliente) &&
    // Diaria, semanal y mensual: las tres que tienen tarifa propia en
    // `tablas_isr_periodicas.py` **y que no son la del periodo que se está
    // calculando**. La `04` también tiene la suya —es justamente la que
    // corresponde a 14-17 días—, y por eso se excluye: no hay discrepancia que
    // avisar. Las demás claves (catorcenal, bimestral, unidad de obra,
    // comisión…) no tienen tarifa y el motor las rechaza con su propio mensaje,
    // que es mejor que uno inventado aquí.
    ['01', '02', '05'].includes(cliente!.clave_periodicidad) &&
    dias >= 14 &&
    dias <= 17;

  const cerrar = async () => {
    if (!cliente) return;
    // **La guarda va AQUÍ, no en el badge del paso.** `PasoNomina` es
    // presentacional: pinta `bloqueado` en gris y renderiza `{children}` sin
    // condición, así que el botón seguía vivo. Y `disabled` es una propiedad
    // del DOM, no una garantía del handler.
    //
    // Cerrar mientras la cartera carga usaría las llaves del CATÁLOGO en vez de
    // las del aparato: cero checadas encontradas para quien tenga número
    // propio, y cuando la cartera llegue la plantilla vuelve a cuadrar por
    // `empleado_no`, así que nada levanta — recibo con faltas de más y en
    // silencio. Es el bug de G-02 entrando por la puerta del tiempo.
    // SON TRES PUERTAS, NO DOS, y este comentario decía que eran dos.
    // `cerrar` se exporta y el diálogo de confirmación la llama DIRECTO
    // ("Cerrar de todos modos"), sin pasar por `pedirCierre`. El camino es
    // real: se pide el cierre con el cliente presente, la cartera se recarga
    // sin él —otra pestaña lo borró, o `recargar()`—, `confirmarPara` sigue
    // apuntando al mismo id y el diálogo sigue en pantalla. El clic mandaba al
    // backend la ficha COMPLETA del catálogo, sin filtrar vinculados.
    //
    // No produce un recibo con ISR mal —esa puerta sí estaba cerrada— pero sí
    // un cierre con el conjunto de empleados equivocado, que es el insumo del
    // cálculo.
    if (cartera.loading || ajenoALaCartera) return;
    // O-01: misma disciplina que `ajenoALaCartera` — la guarda va en el
    // HANDLER, no sólo en el `disabled` del botón, que es una propiedad del DOM
    // y no una garantía. Es literalmente el defecto que este archivo critica de
    // la corrida G tres bloques más abajo.
    if (faltaDeLaEmpresa.length > 0) return;
    const id = cliente.id;
    setConfirmarPara(null);
    setOcupado(true);
    setErrorDe(null);
    try {
      setNominaDe({ id, valor: null });
      setCierreDe({
        id,
        // **La llave del CHECADOR**, no la del cálculo: `cerrar_periodo` casa
        // `evento.empleado_no` —el `employeeNoString` del aparato— contra esta
        // lista. Mandar la interna hacía que un empleado con llaves distintas
        // no encontrara ni una de sus checadas: falta todo el periodo, menos
        // días pagados y menores cuotas, en silencio.
        valor: incidenciasDelCierre(
          await cerrarPeriodo(id, llavesParaElCierre(plantilla, empleadosCartera), { inicio, fin }),
          empleadosCartera,
        ),
      });
    } catch (e) {
      setErrorDe({ id, valor: (e as Error).message });
    } finally {
      setOcupado(false);
    }
  };

  const calcular = async () => {
    if (!cliente || !cierre) return;
    // R-06. Misma guarda que en `pedirCierre`, y no es redundante: se puede
    // llegar aquí con un cierre viejo en estado y la cartera ya resuelta a "no
    // es tuyo". Cerrar una sola de las dos puertas deja la otra abierta.
    if (ajenoALaCartera) {
      setErrorDe({
        id: cliente.id,
        valor:
          'Este cliente no está en la cartera de tu cuenta, así que no se puede calcular su ' +
          'nómina: la plantilla saldría del catálogo de demostración y no de tus empleados. ' +
          'Ábrelo desde tu lista de clientes.',
      });
      return;
    }
    if (faltaDeLaEmpresa.length > 0) {
      setErrorDe({
        id: cliente.id,
        valor:
          `Falta ${faltaDeLaEmpresa.join(' y ')} de la empresa. Sin eso no se pueden ` +
          'calcular las cuotas patronales. Captúralo en Perfil → Configuración de empresa.',
      });
      return;
    }
    if (periodicidadNoCuadra) {
      setErrorDe({
        id: cliente.id,
        valor:
          `Este cliente está registrado con periodicidad "${cliente.clave_periodicidad}" y el ` +
          `periodo mide ${dias} días, que es una quincena. Calcularlo aplicaría la tarifa de ` +
          'ISR de otra periodicidad y el resultado sería incorrecto sin avisar. ' +
          'Corrige la periodicidad del cliente, o el periodo, antes de calcular. ' +
          'Si lo que quieres es un periodo PARCIAL de un cliente mensual (un alta o una baja ' +
          'a mitad de mes), eso todavía no se puede calcular aquí.',
      });
      return;
    }
    const id = cliente.id;
    setOcupado(true);
    setErrorDe(null);
    try {
      // Las incidencias van verbatim: `dias_periodo`, `faltas` y
      // `dias_ausentismo` alimentan la base de cuotas y los días pagados.
      setNominaDe({
        id,
        valor: await calcularNomina(
          id,
          { inicio, fin, fecha_pago: fechaDePago(cliente, inicio, fin) },
          cierre.incidencias,
          cliente,
          // La plantilla va aparte y explícita: es lo que hace que un empleado
          // dado de alta hoy aparezca en los recibos de hoy, sin tener que
          // fabricar una ficha con campos inventados.
          plantilla,
        ),
      });
    } catch (e) {
      setErrorDe({ id, valor: (e as Error).message });
    } finally {
      setOcupado(false);
    }
  };

  return {
    cliente,
    /** Empleados de la cartera que NO están vinculados al checador (G-02). */
    sinVincular,
    /** `true` mientras no se sabe con qué llaves cerrar. Bloquea el paso 2. */
    carteraCargando: cartera.loading,
    /**
     * R-06: el cliente no está en la cartera de esta cuenta. **No se calcula.**
     * Sin esto, la plantilla caía a la ficha del backend sin filtrar
     * vinculados y con el aviso apagado — otro conjunto de empleados entrando
     * al cálculo, en silencio.
     */
    ajenoALaCartera,
    /**
     * O-01: qué le falta a la empresa para poder calcular. Vacío = nada.
     *
     * **Sin prima de riesgos de trabajo no hay cuota patronal que calcular**, y
     * el motor la acota a [0.005, 0.150] (Arts. 72 y 73 LSS): mandarla vacía
     * devuelve un 422 de pydantic sobre un campo que el operador no sabe que
     * existe. Se para aquí, con el motivo en palabras y el camino para
     * arreglarlo, en vez de dejar que el error llegue del backend.
     *
     * En modo despacho va siempre vacío: ahí la prima es del cliente y ya la
     * valida `ModalCliente` al capturarla.
     */
    faltaDeLaEmpresa,
    eventos,
    cierre,
    nomina,
    error,
    errorPanel,
    ocupado,
    inicio,
    setInicio,
    fin,
    setFin,
    cargandoCliente: cliente === null && error === null,
    confirmarCierre: confirmarPara === clienteId,
    cancelarConfirmacion: () => setConfirmarPara(null),
    // Sin checadas EN EL PERIODO el cálculo NO sale en ceros: cada quien cobra
    // los días no laborables, así que la nómina se ve completa y creíble con la
    // ausencia escondida. Mejor preguntar que enseñar eso enfrente de alguien.
    pedirCierre: () => {
      // La guarda va en la ACCIÓN, no en el badge del paso. En la corrida G se
      // puso en el letrero y el botón quedó vivo, en gris, sin impedir nada.
      if (!cliente || cartera.loading || ajenoALaCartera) return;
      if (sinChecadasEnElPeriodo) setConfirmarPara(cliente.id);
      else void cerrar();
    },
    cerrar,
    calcular,
    // Empleados sin UNA SOLA checada: es "a este cliente nadie le sembró", no
    // "ausentismo prolongado". Los dos se ven igual en la tabla de incidencias.
    ausentesTotales: (cierre?.incidencias ?? [])
      .filter((i) => i.dias_trabajados === 0)
      .map((i) => i.empleado_no),
  };
}
