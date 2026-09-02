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

import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  calcularNomina,
  cerrarPeriodo,
  obtenerEventos,
  type CierrePeriodo,
  type EventoChecada,
  type NominaPeriodo,
} from '../../services/nominaDemoApi';
import { useCartera } from '../../context/carteraStore';
import { estaVinculado, contarSinVincular } from '../../services/carteraApi';
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
        if (!cancelado) setErrorDe({ id: clienteId, valor: e.message });
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

  const cliente = suyo(cargada, clienteId, null);
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
  const deLaCartera = clienteId ? cartera.clientePorId(clienteId) : null;
  const empleadosCartera = deLaCartera?.empleados ?? null;
  const sinVincular = empleadosCartera ? contarSinVincular(empleadosCartera) : 0;

  /** La plantilla que se manda al backend: la de la cartera si la hay. */
  const plantilla = useMemo(() => {
    if (!cliente) return [];
    if (!empleadosCartera) return cliente.empleados;
    return empleadosCartera.filter(estaVinculado).map((e) => ({
      empleado_no: e.empleado_no,
      nombre: e.nombre,
      puesto: e.puesto,
      salario_diario: e.salario_diario,
      salario_diario_integrado: e.salario_diario_integrado,
      zona: e.zona,
      fecha_alta: e.fecha_alta,
      antiguedad_anios: null,
      factor: '0',
      factor_implicito: false,
    }));
  }, [cliente, empleadosCartera]);

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
          // La ficha con la plantilla de la cartera: es lo que hace que un
          // empleado dado de alta hoy aparezca en los recibos de hoy.
          { ...cliente, empleados: plantilla },
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
