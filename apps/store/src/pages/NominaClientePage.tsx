/**
 * Nómina de un cliente del despacho (E-03; era la pantalla de D-07).
 * DEMO: se borra en F2.
 *
 * Tres pasos: el panel se llena solo → "Cerrar quincena" → "Calcular nómina".
 *
 * LA RUTA ES LA FUENTE DE VERDAD DEL CLIENTE
 * ------------------------------------------
 * El cliente sale de `useParams`, no del contexto, y **el contexto se
 * sincroniza a la ruta**, nunca al revés. Si fuera al revés, entrar por
 * `/app/clientes/demo/nomina` con `taller` guardado en `localStorage` dejaría
 * el selector del header diciendo "Taller" y la pantalla calculando `demo`.
 *
 * NO HAY NI UNA CONSTANTE FISCAL EN ESTE ARCHIVO
 * ----------------------------------------------
 * Los empleados, la prima de riesgo, la periodicidad y el periodo salen de
 * `GET /despacho/clientes/{id}`. En particular **el periodo NO se deduce de las
 * checadas**: del 16 al 31 de agosto son 16 días naturales y la primera checada
 * es del 17 (el 16 es domingo), así que `min`/`max` daría 15 — un día menos de
 * base para las cuotas del IMSS y un día menos pagado.
 *
 * LA PLANTILLA VIAJA SIEMPRE EN EL REQUEST
 * ----------------------------------------
 * `calcular-periodo` sólo acepta omitirla para el cliente `demo`, así que para
 * los sintéticos es obligatorio. Se manda para los tres, con lo que la
 * respuesta trae `origen_plantilla: "request"` siempre — y por eso la banda de
 * demostración del PDF **dejó de colgar de ese campo** y cuelga del cliente.
 */

import { useCallback, useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { AlertTriangle, CalendarCheck, Calculator, FileDown, Loader } from 'lucide-react';
import PanelChecador from '../components/nomina/PanelChecador';
import TablaIncidencias from '../components/nomina/TablaIncidencias';
import TablaRecibos from '../components/nomina/TablaRecibos';
import CuotasPorRamo from '../components/nomina/CuotasPorRamo';
import { exportarNominaPDF } from '../services/pdfExportNomina';
import {
  calcularNomina,
  cerrarPeriodo,
  obtenerEventos,
  type CierrePeriodo,
  type EventoChecada,
  type NominaPeriodo,
} from '../services/nominaDemoApi';
import {
  etiquetaOrigen,
  obtenerCliente,
  type ClienteDetalle,
} from '../services/despachoApi';
import { useClienteActivo } from '../context/clienteActivoStore';

const MS_POLLING = 3000;

const CAJA: React.CSSProperties = {
  background: 'var(--bg-surface)',
  border: '1px solid var(--border)',
  borderRadius: 12,
  padding: 20,
};

/**
 * Qué fecha de pago mandar.
 *
 * Los dos inputs de fecha son libres, así que el operador puede mover el
 * periodo a otro mes. Mandar la `fecha_pago` de la quincena sugerida en ese
 * caso sería calcular un periodo con la vigencia de otro: de esa fecha
 * dependen la UMA, el salario mínimo, la tarifa del Anexo 8 y el transitorio
 * de enero del subsidio (§D18).
 *
 * Cuando el periodo cambió se manda `null` y **lo resuelve el backend**. No se
 * replica aquí el default (`fecha_pago ?? fin`): esa regla vive en un solo
 * lugar, y la respuesta trae `fecha_pago_efectiva` para que la pantalla y el
 * PDF impriman lo que el motor usó.
 */
function fechaDePago(
  cliente: ClienteDetalle,
  inicio: string,
  fin: string,
): string | null {
  const sugerido = cliente.periodo_sugerido;
  const sinTocar = inicio === sugerido.inicio && fin === sugerido.fin;
  return sinTocar ? sugerido.fecha_pago : null;
}

/**
 * La ficha se guarda JUNTO CON el id que la produjo, igual que en
 * `ClienteDetallePage`.
 *
 * Con un `cliente` a secas, entre el cambio de ruta y la llegada de la ficha
 * nueva la pantalla conserva la vieja: la URL y el selector dicen "Taller", el
 * encabezado dice "Servicios Administrativos Integrales" y **los botones siguen
 * habilitados**, así que "Cerrar quincena" en esa ventana cierra el periodo del
 * cliente anterior. Derivar `cliente` del id lo vuelve imposible por
 * construcción, en vez de depender de que la promesa resuelva rápido.
 */
type FichaCargada = { id: string; cliente: ClienteDetalle };

/**
 * Un dato que pertenece a UN cliente.
 *
 * Todo lo de la pantalla se etiqueta con el id que lo produjo y se **deriva**
 * comparándolo con el de la ruta, en vez de limpiarse en un efecto. Dos razones:
 * un `setState` síncrono dentro de un efecto dispara renders en cascada (y el
 * lint lo marca), y sobre todo esto no puede "olvidarse de limpiar" una pieza
 * nueva: si no lleva el id, no se pinta.
 */
type DeCliente<T> = { id: string; valor: T };

function suyo<T>(dato: DeCliente<T> | null, clienteId: string, vacio: T): T {
  return dato && dato.id === clienteId ? dato.valor : vacio;
}

export default function NominaClientePage() {
  const { id: clienteId = '' } = useParams();
  const { clienteId: activo, setClienteId } = useClienteActivo();
  const [cargada, setCargada] = useState<FichaCargada | null>(null);
  const [eventosDe, setEventosDe] = useState<DeCliente<EventoChecada[]> | null>(null);
  const [cierreDe, setCierreDe] = useState<DeCliente<CierrePeriodo | null> | null>(null);
  const [nominaDe, setNominaDe] = useState<DeCliente<NominaPeriodo | null> | null>(null);
  const [inicio, setInicio] = useState('');
  const [fin, setFin] = useState('');
  const [errorPanel, setErrorPanel] = useState<string | null>(null);
  const [errorDe, setErrorDe] = useState<DeCliente<string | null> | null>(null);
  const [ocupado, setOcupado] = useState(false);
  // La confirmación es estado, no `window.confirm`: E-04 sólo tiene que pintar
  // el diálogo, sin reescribir el flujo async de `alCerrar`. Guarda el id del
  // cliente al que corresponde, para que no sobreviva a un cambio de cliente.
  const [confirmarPara, setConfirmarPara] = useState<string | null>(null);

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
        setCargada({ id: clienteId, cliente: c });
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

  const alPedirCierre = () => {
    if (!cliente) return;
    // Sin checadas EN EL PERIODO, `cerrar_periodo` marca falta todo día
    // laborable y el cálculo NO sale en ceros: cada quien cobra los días no
    // laborables, así que la nómina se ve completa y creíble con la ausencia
    // escondida. Mejor preguntar que enseñar eso enfrente de alguien.
    if (sinChecadasEnElPeriodo) {
      setConfirmarPara(cliente.id);
      return;
    }
    void alCerrar();
  };

  const alCerrar = async () => {
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
          cliente.empleados.map((e) => e.empleado_no),
          { inicio, fin },
        ),
      });
    } catch (e) {
      setErrorDe({ id, valor: (e as Error).message });
    } finally {
      setOcupado(false);
    }
  };

  const alCalcular = async () => {
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
        ),
      });
    } catch (e) {
      setErrorDe({ id, valor: (e as Error).message });
    } finally {
      setOcupado(false);
    }
  };

  const cliente = cargada?.id === clienteId ? cargada.cliente : null;
  // Cada pieza se deriva del cliente de la RUTA: nada del anterior se pinta.
  const eventos = suyo(eventosDe, clienteId, [] as EventoChecada[]);
  const cierre = suyo(cierreDe, clienteId, null);
  const nomina = suyo(nominaDe, clienteId, null);
  const error = suyo(errorDe, clienteId, null);
  const confirmarCierre = confirmarPara === clienteId;
  const cargandoCliente = cliente === null && error === null;

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
  const checadasEnElPeriodo = eventos.filter((e) => {
    const dia = e.timestamp.slice(0, 10);
    return dia >= inicio && dia <= fin;
  }).length;
  const sinChecadasEnElPeriodo = checadasEnElPeriodo === 0;

  // Empleados sin UNA SOLA checada: es "a este cliente nadie le sembró", no
  // "ausentismo prolongado". Los dos se ven igual en la tabla de incidencias, y
  // el aviso del motor llega hasta abajo, después de leer los totales.
  const ausentesTotales = (cierre?.incidencias ?? [])
    .filter((i) => i.dias_trabajados === 0)
    .map((i) => i.empleado_no);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20, paddingBottom: 40 }}>
      <header>
        <h1 style={{ marginBottom: 4 }}>
          Nómina de {cliente?.nombre ?? 'cliente'}{' '}
          <span
            style={{
              fontSize: '0.7em',
              background: 'var(--accent-active)',
              color: 'var(--text-on-accent)',
              borderRadius: 6,
              padding: '2px 8px',
              verticalAlign: 'middle',
            }}
          >
            DEMO
          </span>
        </h1>
        <p style={{ color: 'var(--text-muted)', margin: 0 }}>
          {cliente
            ? `${cliente.giro} · ${etiquetaOrigen(cliente.origen)} · ${cliente.num_empleados} empleados`
            : cargandoCliente
              ? 'Cargando el cliente...'
              : 'No se pudo cargar el cliente'}
        </p>
      </header>

      {error && (
        <p
          role="alert"
          style={{ ...CAJA, borderColor: 'var(--danger)', color: 'var(--danger)' }}
        >
          {error}
        </p>
      )}

      {confirmarCierre && cliente && (
        <div
          role="alertdialog"
          aria-label="Confirmar cierre sin checadas"
          style={{ ...CAJA, borderColor: 'var(--warning)', display: 'flex', flexDirection: 'column', gap: 12 }}
        >
          <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
            <AlertTriangle size={18} color="var(--warning)" style={{ flexShrink: 0, marginTop: 2 }} />
            <span>
              No hay checadas de <strong>{cliente.nombre}</strong> entre {inicio} y {fin}. Si
              cierras el periodo, todos los días laborables se marcarán como falta y la nómina
              saldrá con <strong>sólo los días de descanso pagados</strong>, no en ceros.
            </span>
          </div>
          <div style={{ display: 'flex', gap: 10 }}>
            <button onClick={() => void alCerrar()}>Cerrar de todos modos</button>
            <button onClick={() => setConfirmarPara(null)}>Cancelar</button>
          </div>
        </div>
      )}

      <PanelChecador eventos={eventos} error={errorPanel} />

      <section style={{ ...CAJA, display: 'flex', gap: 16, flexWrap: 'wrap', alignItems: 'flex-end' }}>
        <label style={{ display: 'flex', flexDirection: 'column', fontSize: '0.85rem' }}>
          Inicio del periodo
          <input type="date" value={inicio} onChange={(e) => setInicio(e.target.value)} />
        </label>
        <label style={{ display: 'flex', flexDirection: 'column', fontSize: '0.85rem' }}>
          Fin del periodo
          <input type="date" value={fin} onChange={(e) => setFin(e.target.value)} />
        </label>
        {cliente && (
          <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', margin: 0, flexBasis: '100%' }}>
            Se calculará con fecha de pago <strong>{cliente.periodo_sugerido.fecha_pago}</strong>.
            De ella dependen la UMA, el salario mínimo y la tarifa vigentes.
          </p>
        )}
        <button onClick={alPedirCierre} disabled={ocupado || !cliente || !inicio || !fin}>
          <CalendarCheck size={16} /> Cerrar quincena
        </button>
        <button onClick={alCalcular} disabled={ocupado || !cierre}>
          <Calculator size={16} /> Calcular nómina
        </button>
        {nomina && cliente && (
          <button onClick={() => exportarNominaPDF(nomina, cliente)}>
            <FileDown size={16} /> Exportar PDF
          </button>
        )}
        {ocupado && <Loader size={16} className="spin" />}
      </section>

      {cierre && ausentesTotales.length > 0 && (
        <p
          role="alert"
          style={{
            ...CAJA,
            borderColor: 'var(--warning)',
            color: 'var(--warning)',
            display: 'flex',
            gap: 10,
            alignItems: 'flex-start',
            margin: 0,
          }}
        >
          <AlertTriangle size={18} style={{ flexShrink: 0, marginTop: 2 }} />
          <span>
            <strong>
              {ausentesTotales.length === cierre.incidencias.length
                ? 'Ningún empleado tiene checadas en este periodo.'
                : `${ausentesTotales.length} empleado(s) sin una sola checada: ${ausentesTotales.join(', ')}.`}
            </strong>{' '}
            La nómina que salga de aquí <strong>no será de ceros</strong>: se pagan los días no
            laborables del periodo. Si esperabas ver checadas, siembra el periodo de este cliente
            antes de calcular.
          </span>
        </p>
      )}

      {cierre && cliente && (
        <TablaIncidencias cierre={cierre} empleados={cliente.empleados} />
      )}

      {nomina && (
        <>
          {/* `origen_plantilla` vale "request" para los tres clientes desde
              E-03, así que ya no distingue nada: lo que importa decir es de
              QUIÉN es esta nómina. */}
          <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', margin: 0 }}>
            Calculado con fecha de pago <strong>{nomina.fecha_pago_efectiva}</strong> ·{' '}
            <strong>{cliente?.nombre}</strong> ({etiquetaOrigen(cliente?.origen ?? '')})
          </p>
          <TablaRecibos nomina={nomina} />
          <CuotasPorRamo nomina={nomina} />
        </>
      )}
    </div>
  );
}
