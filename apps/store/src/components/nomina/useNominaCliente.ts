/**
 * Estado del flujo de nómina de un cliente (extraído de `NominaClientePage` en E-06).
 *
 * Todo lo que la pantalla SABE vive aquí; la pantalla sólo lo pinta. Las acciones
 * (cerrar, calcular) viven en `useAccionesNomina` desde P4, por el tope de 300 líneas.
 *
 * LA RUTA ES LA FUENTE DE VERDAD DEL CLIENTE: el contexto se sincroniza a ella, nunca al
 * revés — si no, el header diría un cliente y la pantalla calcularía otro.
 *
 * CADA DATO VIAJA CON EL CLIENTE QUE LO PRODUJO (`DeCliente`): nada se limpia en un
 * efecto, todo se DERIVA comparando contra el id de la ruta. Un efecto de limpieza puede
 * olvidarse de una pieza nueva; la derivación no.
 *
 * NO HAY NI UNA CONSTANTE FISCAL AQUÍ. El periodo no se deduce de las checadas: del 16 al
 * 31 de agosto son 16 días y la primera checada es del 17 — `min`/`max` daría 15.
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import {
  obtenerEventos,
  type CierrePeriodo,
  type EmpleadoNominaRequest,
  type EventoChecada,
} from '../../services/nominaDemoApi';
import type { NominaCalculada, TipoNomina, VariablesEmpleado } from '../../services/nominaApi';
import { useCartera } from '../../context/carteraStore';
import { plantillaDeNomina } from './plantillaDeNomina';
import { contarSinVincular } from '../../services/carteraApi';
import { obtenerCliente, type ClienteDetalle } from '../../services/despachoApi';
import { useClienteActivo } from '../../context/clienteActivoStore';
import { useAccionesNomina, type DeCliente } from './useAccionesNomina';

const MS_POLLING = 3000;

function suyo<T>(dato: DeCliente<T> | null, clienteId: string, vacio: T): T {
  return dato && dato.id === clienteId ? dato.valor : vacio;
}

export function useNominaCliente(clienteId: string) {
  const { clienteId: activo, setClienteId } = useClienteActivo();
  const [cargada, setCargada] = useState<DeCliente<ClienteDetalle> | null>(null);
  const [eventosDe, setEventosDe] = useState<DeCliente<EventoChecada[]> | null>(null);
  const [cierreDe, setCierreDe] = useState<DeCliente<CierrePeriodo | null> | null>(null);
  const [nominaDe, setNominaDe] = useState<DeCliente<NominaCalculada | null> | null>(null);
  /** El periodo PERTENECE A UN CLIENTE: con dos `useState` sueltos quedaban las fechas
   *  del cliente anterior con el botón vivo (lo cazó el test de navegación). */
  const [periodoDe, setPeriodoDe] = useState<DeCliente<{ inicio: string; fin: string }> | null>(null);
  const [tipoDe, setTipoDe] = useState<DeCliente<TipoNomina> | null>(null);
  const [variablesDe, setVariablesDe] = useState<DeCliente<Record<string, VariablesEmpleado>> | null>(null);
  const [errorPanel, setErrorPanel] = useState<string | null>(null);
  const [errorDe, setErrorDe] = useState<DeCliente<string | null> | null>(null);
  /** El error de CARGAR la ficha, aparte del de las operaciones: sólo uno se descarta. */
  const [errorCargaDe, setErrorCargaDe] = useState<DeCliente<string | null> | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const [confirmarPara, setConfirmarPara] = useState<string | null>(null);
  const cartera = useCartera();
  // El efecto de carga NO depende de `cartera` (cambia de identidad en cada render y
  // revertiría las fechas que el operador movió): se lee por ref.
  const carteraRef = useRef(cartera);
  useEffect(() => {
    carteraRef.current = cartera;
  });

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
        setErrorCargaDe(null);
        setPeriodoDe({ id: clienteId, valor: { inicio: c.periodo_sugerido.inicio, fin: c.periodo_sugerido.fin } });
      })
      .catch((e: Error) => {
        if (cancelado) return;
        // Un cliente del contador no tiene ficha en el backend de demo: es lo normal.
        // El error se GUARDA siempre y se DECIDE al leer (ver `error`).
        const suyoEnCartera = carteraRef.current.clientePorId(clienteId);
        if (suyoEnCartera) {
          setPeriodoDe({
            id: clienteId,
            valor: { inicio: suyoEnCartera.periodo_sugerido.inicio, fin: suyoEnCartera.periodo_sugerido.fin },
          });
        }
        setErrorCargaDe({ id: clienteId, valor: e.message });
      });
    return () => {
      cancelado = true;
    };
  }, [clienteId]);

  useEffect(() => {
    if (!clienteId) return;
    const refrescar = () =>
      obtenerEventos(clienteId)
        .then((r) => {
          setEventosDe({ id: clienteId, valor: r.eventos });
          setErrorPanel(null);
        })
        .catch((e: Error) => setErrorPanel(e.message));
    refrescar();
    const id = setInterval(refrescar, MS_POLLING);
    return () => clearInterval(id);
  }, [clienteId]);

  const fichaBackend = suyo(cargada, clienteId, null);

  /** La ficha del backend cuando existe; si no, la de la cartera. */
  const cliente: ClienteDetalle | null = useMemo(() => {
    if (fichaBackend) return fichaBackend;
    const c = clienteId ? cartera.clientePorId(clienteId) : null;
    if (!c) return null;
    return {
      id: c.id, nombre: c.nombre, giro: c.giro, origen: c.origen,
      num_empleados: c.empleados.length, prima_riesgo: c.prima_riesgo,
      clase_riesgo: c.clase_riesgo, clave_periodicidad: c.clave_periodicidad, zona: c.zona,
      periodo_sugerido: c.periodo_sugerido, fecha_referencia: '', empleados: [],
    };
  }, [fichaBackend, clienteId, cartera]);

  // R-06: TRES estados — cargando, cargada con el cliente, cargada SIN él. Mientras
  // carga no se decide nada; sin él, no se calcula (otro conjunto de empleados en silencio).
  const carteraLista = Boolean(clienteId) && !cartera.loading;
  const deLaCartera = carteraLista ? cartera.clientePorId(clienteId as string) : null;
  const ajenoALaCartera = carteraLista && deLaCartera === null;
  const empleadosCartera = deLaCartera?.empleados ?? null;
  const sinVincular = empleadosCartera ? contarSinVincular(empleadosCartera) : 0;

  const { inicio, fin } = suyo(periodoDe, clienteId, { inicio: '', fin: '' });
  const setInicio = (v: string) => setPeriodoDe({ id: clienteId, valor: { inicio: v, fin } });
  const setFin = (v: string) => setPeriodoDe({ id: clienteId, valor: { inicio, fin: v } });
  const tipo = suyo(tipoDe, clienteId, 'ordinaria' as TipoNomina);
  const variablesPorEmpleado = suyo(variablesDe, clienteId, {} as Record<string, VariablesEmpleado>);

  const eventos = suyo(eventosDe, clienteId, [] as EventoChecada[]);
  const cierre = suyo(cierreDe, clienteId, null);
  const nomina = suyo(nominaDe, clienteId, null);
  /** Derivado: el error de CARGA sólo cuenta si el cliente tampoco está en la cartera. */
  const error =
    suyo(errorDe, clienteId, null) ??
    (deLaCartera || cartera.loading ? null : suyo(errorCargaDe, clienteId, null));

  /** Checadas DENTRO del periodo: el panel trae todo lo que hay en memoria. */
  const sinChecadasEnElPeriodo = !eventos.some((e) => {
    const dia = e.timestamp.slice(0, 10);
    return dia >= inicio && dia <= fin;
  });

  // Quién entra al CIERRE (G-01/G-02). El cálculo ya no la manda (P4-01): la lee el backend.
  const plantilla: EmpleadoNominaRequest[] = useMemo(
    () => plantillaDeNomina(cliente?.empleados ?? [], empleadosCartera),
    [cliente, empleadosCartera],
  );

  const acciones = useAccionesNomina({
    clienteId, cliente, cierre, carteraCargando: cartera.loading, ajenoALaCartera, plantilla,
    empleadosCartera, inicio, fin, sinChecadasEnElPeriodo, tipo,
    variables: Object.values(variablesPorEmpleado),
    setCierreDe, setNominaDe, setErrorDe, setOcupado, setConfirmarPara,
  });

  return {
    cliente,
    /** Empleados de la cartera que NO están vinculados al checador (G-02). */
    sinVincular,
    /** Los empleados de la CARTERA, para los exportadores de O-04 y la captura de P4-05. */
    empleadosDeLaCartera: empleadosCartera ?? [],
    /** Registro patronal y guía: de CADA cliente; vacíos hacen levantar al exportador. */
    registroPatronal: deLaCartera?.registro_patronal ?? '',
    guiaSubdelegacion: deLaCartera?.guia_subdelegacion ?? '',
    carteraCargando: cartera.loading,
    ajenoALaCartera,
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
    /** P4: tipo de nómina y variables capturadas por empleado. */
    tipo,
    setTipo: (t: TipoNomina) => {
      setTipoDe({ id: clienteId, valor: t });
      setNominaDe({ id: clienteId, valor: null });
    },
    variables: variablesPorEmpleado,
    setVariables: (v: VariablesEmpleado) =>
      setVariablesDe({ id: clienteId, valor: { ...variablesPorEmpleado, [v.empleado_no]: v } }),
    cargandoCliente: cliente === null && error === null,
    confirmarCierre: confirmarPara === clienteId,
    cancelarConfirmacion: () => setConfirmarPara(null),
    pedirCierre: acciones.pedirCierre,
    cerrar: acciones.cerrar,
    calcular: acciones.calcular,
    // Sin UNA checada: "a este cliente nadie le sembró", no "ausentismo prolongado".
    ausentesTotales: (cierre?.incidencias ?? []).filter((i) => i.dias_trabajados === 0).map((i) => i.empleado_no),
  };
}
