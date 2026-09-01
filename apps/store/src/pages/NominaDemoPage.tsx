/**
 * Pantalla de la demo del checador (D-07). DEMO: se borra en F2.
 *
 * Tres pasos: el panel se llena solo → "Cerrar quincena" → "Calcular nómina".
 *
 * NO HAY NI UNA CONSTANTE FISCAL EN ESTE ARCHIVO
 * ----------------------------------------------
 * Los empleados, la prima de riesgo, la periodicidad y el periodo salen de
 * `GET /nomina/demo/plantilla`. En particular **el periodo NO se deduce de las
 * checadas**: del 16 al 31 de agosto son 16 días naturales y la primera checada
 * es del 17 (el 16 es domingo), así que `min`/`max` daría 15 — un día menos de
 * base para las cuotas del IMSS y un día menos pagado.
 */

import { useCallback, useEffect, useState } from 'react';
import { CalendarCheck, Calculator, FileDown, Loader } from 'lucide-react';
import PanelChecador from '../components/nomina/PanelChecador';
import TablaIncidencias from '../components/nomina/TablaIncidencias';
import TablaRecibos from '../components/nomina/TablaRecibos';
import CuotasPorRamo from '../components/nomina/CuotasPorRamo';
import { exportarNominaPDF } from '../services/pdfExportNomina';
import {
  CLIENTE_DEMO,
  calcularNomina,
  cerrarPeriodo,
  obtenerEventos,
  obtenerPlantillaDemo,
  type CierrePeriodo,
  type EventoChecada,
  type NominaPeriodo,
  type PlantillaDemo,
} from '../services/nominaDemoApi';

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
  plantilla: PlantillaDemo,
  inicio: string,
  fin: string,
): string | null {
  const sugerido = plantilla.periodo_sugerido;
  const sinTocar = inicio === sugerido.inicio && fin === sugerido.fin;
  return sinTocar ? sugerido.fecha_pago : null;
}

export default function NominaDemoPage() {
  const [plantilla, setPlantilla] = useState<PlantillaDemo | null>(null);
  const [eventos, setEventos] = useState<EventoChecada[]>([]);
  const [cierre, setCierre] = useState<CierrePeriodo | null>(null);
  const [nomina, setNomina] = useState<NominaPeriodo | null>(null);
  const [inicio, setInicio] = useState('');
  const [fin, setFin] = useState('');
  const [errorPanel, setErrorPanel] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);

  useEffect(() => {
    obtenerPlantillaDemo()
      .then((p) => {
        setPlantilla(p);
        setInicio(p.periodo_sugerido.inicio);
        setFin(p.periodo_sugerido.fin);
      })
      .catch((e: Error) => setError(e.message));
  }, []);

  const refrescar = useCallback(() => {
    obtenerEventos()
      .then((r) => {
        setEventos(r.eventos);
        setErrorPanel(null);
      })
      .catch((e: Error) => setErrorPanel(e.message));
  }, []);

  useEffect(() => {
    refrescar();
    const id = setInterval(refrescar, MS_POLLING);
    return () => clearInterval(id);
  }, [refrescar]);

  const alCerrar = async () => {
    if (!plantilla) return;
    setOcupado(true);
    setError(null);
    try {
      setNomina(null);
      setCierre(
        await cerrarPeriodo(
          CLIENTE_DEMO,
          plantilla.empleados.map((e) => e.empleado_no),
          { inicio, fin },
        ),
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setOcupado(false);
    }
  };

  const alCalcular = async () => {
    if (!plantilla || !cierre) return;
    setOcupado(true);
    setError(null);
    try {
      // Las incidencias van verbatim: `dias_periodo`, `faltas` y
      // `dias_ausentismo` alimentan la base de cuotas y los días pagados.
      setNomina(
        await calcularNomina(
          CLIENTE_DEMO,
          { inicio, fin, fecha_pago: fechaDePago(plantilla, inicio, fin) },
          cierre.incidencias,
          plantilla,
        ),
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setOcupado(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20, paddingBottom: 40 }}>
      <header>
        <h1 style={{ marginBottom: 4 }}>
          Nómina con checador{' '}
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
          Cliente de demostración · datos sintéticos con montos reales
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
        {plantilla && (
          <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', margin: 0, flexBasis: '100%' }}>
            Se calculará con fecha de pago <strong>{plantilla.periodo_sugerido.fecha_pago}</strong>.
            De ella dependen la UMA, el salario mínimo y la tarifa vigentes.
          </p>
        )}
        <button onClick={alCerrar} disabled={ocupado || !plantilla || !inicio || !fin}>
          <CalendarCheck size={16} /> Cerrar quincena
        </button>
        <button onClick={alCalcular} disabled={ocupado || !cierre}>
          <Calculator size={16} /> Calcular nómina
        </button>
        {nomina && (
          <button onClick={() => exportarNominaPDF(nomina)}>
            <FileDown size={16} /> Exportar PDF
          </button>
        )}
        {ocupado && <Loader size={16} className="spin" />}
      </section>

      {cierre && plantilla && (
        <TablaIncidencias cierre={cierre} empleados={plantilla.empleados} />
      )}

      {nomina && (
        <>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', margin: 0 }}>
            Calculado con fecha de pago <strong>{nomina.fecha_pago_efectiva}</strong> · plantilla{' '}
            <strong>{nomina.origen_plantilla}</strong>
          </p>
          <TablaRecibos nomina={nomina} />
          <CuotasPorRamo nomina={nomina} />
        </>
      )}
    </div>
  );
}
