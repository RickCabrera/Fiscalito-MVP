/**
 * Nómina de un cliente del despacho (E-03; era la pantalla de D-07).
 * DEMO: se borra en F2.
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

import { Calculator, CalendarCheck, FileDown, Loader } from 'lucide-react';
import AvisoNomina from '../components/nomina/AvisoNomina';
import EncabezadoNomina from '../components/nomina/EncabezadoNomina';
import PanelChecador, { ContadorChecadas } from '../components/nomina/PanelChecador';
import PasoNomina, { type EstadoPaso } from '../components/nomina/PasoNomina';
import TablaIncidencias from '../components/nomina/TablaIncidencias';
import TablaRecibos from '../components/nomina/TablaRecibos';
import CuotasPorRamo from '../components/nomina/CuotasPorRamo';
import { useNominaCliente } from '../components/nomina/useNominaCliente';
import { exportarNominaPDF } from '../services/pdfExportNomina';
import { etiquetaOrigen } from '../services/despachoApi';
import { useParams } from 'react-router-dom';
import { labelStyle } from '../utils/styles';

/** Botón de acción: el icono y el texto en una línea, sin saltos. */
const ACCION: React.CSSProperties = { display: 'inline-flex', alignItems: 'center', gap: 8 };

const FILA_ACCION: React.CSSProperties = {
  display: 'flex',
  gap: 'var(--space-sm)',
  alignItems: 'center',
  flexWrap: 'wrap',
};

export default function NominaClientePage() {
  const { id: clienteId = '' } = useParams();
  const n = useNominaCliente(clienteId);
  const { cliente, cierre, nomina } = n;

  const exportar = () => {
    // Guarda propia, no sólo `disabled`: desde E-06 el botón se renderiza
    // siempre —para que el paso 4 exista en pantalla desde el principio— y
    // `disabled` es una propiedad del DOM, no una garantía del handler.
    if (!nomina || !cliente) return;
    exportarNominaPDF(nomina, cliente, n.sinVincular);
  };

  // Los estados se derivan en cascada: un paso está bloqueado mientras no
  // exista lo que produce el anterior.
  /**
   * El paso 2 espera también a la CARTERA, no sólo a la ficha.
   *
   * La ficha llega del backend (round-trip local) antes que Firestore (hasta
   * 2500 ms). En esa ventana `deLaCartera` es `null`, así que el cierre usaría
   * las llaves del catálogo en vez de las del aparato: para un empleado con
   * número propio, cero checadas encontradas. Y cuando la cartera llega, la
   * plantilla vuelve a cuadrar por `empleado_no` y nada levanta — sale un recibo
   * con faltas de más, en silencio. Es el mismo bug de G-02 entrando por la
   * puerta del tiempo.
   */
  const estadoPaso2: EstadoPaso = cierre
    ? 'listo'
    : cliente && !n.carteraCargando
      ? 'disponible'
      : 'bloqueado';
  const estadoPaso3: EstadoPaso = nomina ? 'listo' : cierre ? 'disponible' : 'bloqueado';
  const estadoPaso4: EstadoPaso = nomina ? 'disponible' : 'bloqueado';

  return (
    <div
      className="page-container"
      style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-lg)' }}
    >
      <EncabezadoNomina cliente={cliente} cargando={n.cargandoCliente} />

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
        motivoBloqueo="Espera a que cargue la plantilla del cliente."
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
            disabled={n.ocupado || !cliente || !n.inicio || !n.fin || n.carteraCargando}
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
            disabled={n.ocupado || !cierre}
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

      <PasoNomina
        numero={4}
        titulo="Exportar"
        descripcion="Genera el PDF con los recibos y las cuotas patronales del periodo."
        estado={estadoPaso4}
        motivoBloqueo="Calcula la nómina primero (paso 3)."
      >
        <div>
          <button
            className="btn-secondary"
            onClick={exportar}
            disabled={!nomina || !cliente}
            style={ACCION}
          >
            <FileDown size={16} /> Exportar PDF
          </button>
        </div>
      </PasoNomina>
    </div>
  );
}
