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
import { contarSinVincular } from '../../services/carteraApi';
import { obtenerCliente, type ClienteDetalle } from '../../services/despachoApi';
import { useClienteActivo } from '../../context/clienteActivoStore';

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
  const [inicio, setInicio] = useState('');
  const [fin, setFin] = useState('');
  const [errorPanel, setErrorPanel] = useState<string | null>(null);
  const [errorDe, setErrorDe] = useState<DeCliente<string | null> | null>(null);
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

  useEffect(() => {
    if (!clienteId) return;
    let cancelado = false;
    obtenerCliente(clienteId)
      .then((c) => {
        if (cancelado) return;
        setCargada({ id: clienteId, valor: c });
        setInicio(c.periodo_sugerido.inicio);
        setFin(c.periodo_sugerido.fin);
      })
      .catch((e: Error) => {
        if (cancelado) return;
        // Un cliente dado de alta por el contador **no tiene ficha en el
        // backend**: `GET /despacho/clientes/{id}` sólo conoce los tres de
        // demostración. Antes de G-03 eso era imposible; ahora es lo normal, y
        // dejar prendido el error apagaría la pantalla entera de un cliente
        // que sí existe. La cartera tiene todo lo que hace falta para calcular
        // —prima, periodicidad, zona, periodo sugerido y plantilla—, así que se
        // usa esa. El error sólo sobrevive si el cliente tampoco está ahí.
        const suyoEnCartera = carteraRef.current.clientePorId(clienteId);
        if (suyoEnCartera) {
          setInicio(suyoEnCartera.periodo_sugerido.inicio);
          setFin(suyoEnCartera.periodo_sugerido.fin);
          return;
        }
        setErrorDe({ id: clienteId, valor: e.message });
      });
    return () => { cancelado = true; };
  }, [clienteId]);

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

  const eventos = suyo(eventosDe, clienteId, [] as EventoChecada[]);
  const cierre = suyo(cierreDe, clienteId, null);
  const nomina = suyo(nominaDe, clienteId, null);
  const error = suyo(errorDe, clienteId, null);

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
  const deLaCartera =
    clienteId && !cartera.loading ? cartera.clientePorId(clienteId) : null;
  const empleadosCartera = deLaCartera?.empleados ?? null;
  const sinVincular = empleadosCartera ? contarSinVincular(empleadosCartera) : 0;

  // La decisión de quién entra vive en `plantillaDeNomina`, que se prueba
  // directo: es la que carga los dos criterios de la épica.
  const plantilla: EmpleadoNominaRequest[] = useMemo(
    () => plantillaDeNomina(cliente?.empleados ?? [], empleadosCartera),
    [cliente, empleadosCartera],
  );

  const cerrar = async () => {
    if (!cliente) return;
    const id = cliente.id;
    setConfirmarPara(null);
    setOcupado(true);
    setErrorDe(null);
    try {
      setNominaDe({ id, valor: null });
      setCierreDe({
        id,
        valor: await cerrarPeriodo(
          id,
          plantilla.map((e) => e.empleado_no),
          { inicio, fin },
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
      if (!cliente) return;
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
