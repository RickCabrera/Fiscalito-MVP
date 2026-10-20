/**
 * Nómina del cliente del despacho (E-03). Era la pantalla de D-07.
 *
 * CUATRO PASOS NUMERADOS (E-06)
 * -----------------------------
 * Checadas → cerrar quincena → calcular → exportar. Cada uno con una línea de
 * qué hace, y los pasos 2-4 habilitados **en orden**: quien ve la pantalla por
 * primera vez —proyectada, en la demo— no tenía cómo saber que tres botones
 * sueltos se usaban de izquierda a derecha.
 *
 * El estado de cada paso se **deriva** de los datos que ya hay (ficha, cierre,
 * nómina). Un `useState` de "paso actual" sería un segundo origen de verdad,
 * capaz de decir "listo" sobre una tabla que no está.
 *
 * ESTE ARCHIVO SÓLO PINTA. Todo lo que la pantalla sabe —y las reglas de por
 * qué lo sabe así— vive en `useNominaCliente`.
 */

import { Calculator, CalendarCheck, Loader } from 'lucide-react';
import AvisoNomina from '../components/nomina/AvisoNomina';
import EncabezadoNomina from '../components/nomina/EncabezadoNomina';
import PanelChecador, { ContadorChecadas } from '../components/nomina/PanelChecador';
import PasoNomina, { type EstadoPaso } from '../components/nomina/PasoNomina';
import TablaIncidencias from '../components/nomina/TablaIncidencias';
import TablaRecibos from '../components/nomina/TablaRecibos';
import CuotasPorRamo from '../components/nomina/CuotasPorRamo';
import { useNominaCliente } from '../components/nomina/useNominaCliente';
import { etiquetaOrigen } from '../services/despachoApi';
import { useParams } from 'react-router-dom';
import { motivoDelPaso2 } from '../components/nomina/motivoDelPaso2';
import { labelStyle } from '../utils/styles';
import { useState } from 'react';
import PasoExportar from '../components/nomina/PasoExportar';
import SelectorTipoNomina, { type VistaNomina } from '../components/nomina/SelectorTipoNomina';
import CapturaVariables from '../components/nomina/CapturaVariables';
import DesgloseRecibos, { type ReciboDesglosado } from '../components/nomina/DesgloseRecibos';
import HistorialNominas from '../components/nomina/HistorialNominas';
import NominaExtraordinaria from '../components/nomina/NominaExtraordinaria';

/** Botón de acción: el icono y el texto en una línea, sin saltos. */
const ACCION: React.CSSProperties = { display: 'inline-flex', alignItems: 'center', gap: 8 };

const FILA_ACCION: React.CSSProperties = {
  display: 'flex',
  gap: 'var(--space-sm)',
  alignItems: 'center',
  flexWrap: 'wrap',
};

interface Props {
  /**
   * De quién es esta nómina, si se fija desde fuera. Sin prop, manda
   * `useParams` — E-03: *"la ruta es la fuente de verdad del cliente"*, para
   * que entrar por `/app/clientes/demo/nomina` con otro cliente guardado en
   * `localStorage` no deje el header diciendo uno y la pantalla calculando otro.
   */
  clienteId?: string;
}

export default function NominaClientePage({ clienteId: fijo }: Props = {}) {
  const { id: deLaRuta = '' } = useParams();
  const clienteId = fijo ?? deLaRuta;
  const n = useNominaCliente(clienteId);
  const { cliente, cierre, nomina } = n;
  // P4: qué nómina se corre. Las de un solo pago y el historial tienen su propia pantalla.
  const [vista, setVista] = useState<VistaNomina>('ordinaria');
  const cambiarVista = (v: VistaNomina) => {
    setVista(v);
    if (v === 'ordinaria' || v === 'asimilados' || v === 'extraordinaria') n.setTipo(v);
  };
  const asimilados = n.tipo === 'asimilados';
  const deEsteRegimen = n.empleadosDeLaCartera.filter(
    (e) => ((e.tipo_regimen ?? '02') !== '02') === asimilados,
  );


  /**
   * Los estados se derivan en cascada. El paso 2 espera también a la CARTERA: en la
   * ventana en que sólo hay ficha, el cierre usaría las llaves del catálogo (bug de G-02
   * por la puerta del tiempo). El porqué de cada bloqueo vive en `motivoDelPaso2`.
   */
  const sinPeriodo = Boolean(cliente) && (!n.inicio || !n.fin);
  const estadoPaso2: EstadoPaso = cierre
    ? 'listo'
    : cliente && !n.carteraCargando && !n.ajenoALaCartera && !sinPeriodo
      ? 'disponible'
      : 'bloqueado';
  const estadoPaso3: EstadoPaso = nomina ? 'listo' : cierre || asimilados ? 'disponible' : 'bloqueado';
  const estadoPaso4: EstadoPaso = nomina ? 'disponible' : 'bloqueado';

  return (
    <div
      className="page-container"
      style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-lg)' }}
    >
      <EncabezadoNomina cliente={cliente} cargando={n.cargandoCliente} />
      <SelectorTipoNomina vista={vista} onCambiar={cambiarVista} />
      {vista === 'historial' && clienteId && <HistorialNominas key={clienteId} clienteId={clienteId} />}
      {(vista === 'finiquito' || vista === 'aguinaldo' || vista === 'ptu') && clienteId && (
        <NominaExtraordinaria key={vista} tipo={vista} clienteId={clienteId} empleados={n.empleadosDeLaCartera} />
      )}
      {(vista === 'ordinaria' || vista === 'asimilados' || vista === 'extraordinaria') && (
      <>

      {n.error && (
        <AvisoNomina severidad="error" conIcono={false}>
          <strong style={{ color: 'var(--danger)' }}>No se pudo completar la operación.</strong>{' '}
          {n.error}
        </AvisoNomina>
      )}

      {/* G-02: el conteo sale de la CARTERA, no del flujo de checadas.
          `empleados_desconocidos` (TablaIncidencias, herencia D-04) responde la
          pregunta contraria —un employeeNo que checó y no está en la
          plantilla—. Los dos conjuntos no se tocan, y con sólo uno de los dos
          hay gente que desaparece del cálculo sin que nadie lo note. */}
      {n.sinVincular > 0 && (
        <AvisoNomina severidad="advertencia">
          <strong>
            {n.sinVincular}{' '}
            {n.sinVincular === 1
              ? 'empleado no está vinculado al checador'
              : 'empleados no están vinculados al checador'}
            .
          </strong>{' '}
          Sin <code>employeeNo</code> no hay forma de atribuirle sus checadas, así que{' '}
          {n.sinVincular === 1 ? 'no entra' : 'no entran'} en este cálculo. Captura su número
          del aparato en la ficha del cliente, pestaña Empleados.
        </AvisoNomina>
      )}

      <PasoNomina
        numero={1}
        titulo="Checadas recibidas"
        descripcion="El checador manda cada entrada y salida; el panel se refresca solo cada 3 segundos."
        estado={n.eventos.length > 0 ? 'listo' : 'disponible'}
        extra={<ContadorChecadas total={n.eventos.length} />}
      >
        <PanelChecador eventos={n.eventos} error={n.errorPanel} />
      </PasoNomina>

      <PasoNomina
        numero={2}
        titulo="Cerrar quincena"
        descripcion="Convierte las checadas en días trabajados, faltas y retardos."
        estado={estadoPaso2}
        motivoBloqueo={motivoDelPaso2(n, { sinPeriodo })}
      >
        <div style={{ display: 'flex', gap: 'var(--space-md)', flexWrap: 'wrap' }}>
          <label style={{ flex: '0 1 190px' }}>
            <span style={labelStyle}>Inicio del periodo</span>
            <input
              className="input-field"
              type="date"
              value={n.inicio}
              onChange={(e) => n.setInicio(e.target.value)}
            />
          </label>
          <label style={{ flex: '0 1 190px' }}>
            <span style={labelStyle}>Fin del periodo</span>
            <input
              className="input-field"
              type="date"
              value={n.fin}
              onChange={(e) => n.setFin(e.target.value)}
            />
          </label>
        </div>

        {cliente && (
          <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', margin: 0 }}>
            Se calculará con fecha de pago{' '}
            <strong style={{ color: 'var(--text-secondary)' }}>
              {cliente.periodo_sugerido.fecha_pago}
            </strong>
            . De ella dependen la UMA, el salario mínimo y la tarifa vigentes.
          </p>
        )}

        <div style={FILA_ACCION}>
          <button
            className="btn-primary"
            onClick={n.pedirCierre}
            // `ajenoALaCartera` va TAMBIÉN aquí y no sólo en el badge del
            // paso. Ponerlo sólo en el letrero dejaba el botón encendido, en
            // color, sin hacer nada — que es exactamente lo que el encabezado
            // de este archivo critica de la corrida G, reintroducido a tres
            // líneas de distancia. El handler ya lo bloquea; esto es que se vea.
            disabled={
              n.ocupado || !cliente || !n.inicio || !n.fin ||
              n.carteraCargando || n.ajenoALaCartera
            }
            style={ACCION}
          >
            <CalendarCheck size={16} /> Cerrar quincena
          </button>
          {n.ocupado && !cierre && <Loader size={16} className="spin" color="var(--accent-active)" />}
        </div>

        {n.confirmarCierre && cliente && (
          <AvisoNomina
            severidad="advertencia"
            rol="alertdialog"
            etiqueta="Confirmar cierre sin checadas"
            pie={
              <div style={{ display: 'flex', gap: 'var(--space-sm)', flexWrap: 'wrap' }}>
                <button className="btn-primary" onClick={() => void n.cerrar()}>
                  Cerrar de todos modos
                </button>
                <button className="btn-secondary" onClick={n.cancelarConfirmacion}>
                  Cancelar
                </button>
              </div>
            }
          >
            No hay checadas de <strong>{cliente.nombre}</strong> entre {n.inicio} y {n.fin}. Si
            cierras el periodo, todos los días laborables se marcarán como falta y la nómina
            saldrá con <strong>sólo los días de descanso pagados</strong>, no en ceros.
          </AvisoNomina>
        )}
      </PasoNomina>

      {cierre && n.ausentesTotales.length > 0 && (
        <AvisoNomina severidad="advertencia">
          <strong>
            {n.ausentesTotales.length === cierre.incidencias.length
              ? 'Ningún empleado tiene checadas en este periodo.'
              : `${n.ausentesTotales.length} empleado(s) sin una sola checada: ${n.ausentesTotales.join(', ')}.`}
          </strong>{' '}
          La nómina que salga de aquí <strong>no será de ceros</strong>: se pagan los días no
          laborables del periodo. Si esperabas ver checadas, siembra el periodo de este cliente
          antes de calcular.
        </AvisoNomina>
      )}

      {cierre && cliente && <TablaIncidencias cierre={cierre} empleados={cliente.empleados} />}

      <PasoNomina
        numero={3}
        titulo="Calcular nómina"
        descripcion="Aplica el motor: percepciones, ISR retenido, cuotas del IMSS y neto por empleado."
        estado={estadoPaso3}
        motivoBloqueo="Cierra la quincena primero (paso 2)."
      >
        <div style={FILA_ACCION}>
          <button
            className="btn-primary"
            onClick={n.calcular}
            disabled={n.ocupado || (!cierre && !asimilados)}
            style={ACCION}
          >
            <Calculator size={16} /> Calcular nómina
          </button>
          {n.ocupado && cierre && <Loader size={16} className="spin" color="var(--accent-active)" />}
        </div>
      </PasoNomina>

      {nomina && (
        <>
          {/* `origen_plantilla` vale "request" para los tres clientes desde
              E-03, así que ya no distingue nada: lo que importa decir es de
              QUIÉN es esta nómina. */}
          <p style={{ color: 'var(--text-muted)', fontSize: '0.82rem', margin: 0 }}>
            Calculado con fecha de pago{' '}
            <strong style={{ color: 'var(--text-secondary)' }}>{nomina.fecha_pago_efectiva}</strong>{' '}
            · <strong style={{ color: 'var(--text-secondary)' }}>{cliente?.nombre}</strong> (
            {etiquetaOrigen(cliente?.origen ?? '')})
          </p>
          <TablaRecibos nomina={nomina} />
          <CuotasPorRamo nomina={nomina} />
        </>
      )}

      {(cierre || asimilados) && (
        <CapturaVariables
          empleados={deEsteRegimen}
          variables={n.variables}
          onCambiar={n.setVariables}
          deshabilitado={n.ocupado}
        />
      )}
      {nomina && <DesgloseRecibos recibos={nomina.recibos as ReciboDesglosado[]} />}
      <PasoExportar
        estado={estadoPaso4}
        nomina={nomina}
        cliente={cliente}
        empleados={n.empleadosDeLaCartera}
        registroPatronal={n.registroPatronal}
        guia={n.guiaSubdelegacion}
        sinVincular={n.sinVincular}
      />
      </>
      )}
    </div>
  );
}
