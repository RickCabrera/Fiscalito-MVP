/**
 * El selector de fuente de facturas de Fiscalito y Contabilito (P1-06).
 *
 * "Bóveda del cliente" es la fuente por defecto: enseña cuántos CFDI vigentes hay
 * en el periodo (emitidos/recibidos), qué se dejó fuera (cancelados, nómina) y, si
 * no hay nada, lleva a la Bóveda y a la Descarga SAT. "Archivos sueltos" es el
 * uploader de siempre, y lo que se sube ahí se puede mandar a la bóveda con un clic.
 *
 * Un solo componente para todos los tabs: la lógica vive en `useFuenteFacturas`.
 */

import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Archive, FileUp, Loader, RefreshCw, Save } from 'lucide-react';
import type { CFDI } from '../../services/fiscalAgentApi';
import { importarCfdi } from '../../services/bovedaApi';
import ErrorAlert from '../common/ErrorAlert';
import XMLUploader from './XMLUploader';
import type { FuenteFacturas, ModoFuente } from './useFuenteFacturas';

interface Props {
  fuente: FuenteFacturas;
  clave: string | null;
  manual: CFDI[];
  onManual: (facturas: CFDI[]) => void;
}

const MODOS: { id: ModoFuente; label: string; icon: React.ReactNode }[] = [
  { id: 'boveda', label: 'Bóveda del cliente', icon: <Archive size={14} /> },
  { id: 'archivos', label: 'Usar archivos sueltos', icon: <FileUp size={14} /> },
];

const nota: React.CSSProperties = { fontSize: '0.8rem', color: 'var(--text-muted)', margin: 0 };

export default function FuenteFacturasPanel({ fuente, clave, manual, onManual }: Props) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {fuente.hayBoveda && (
        <div role="radiogroup" aria-label="Fuente de las facturas" style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {MODOS.map((m) => {
            const activo = fuente.modo === m.id;
            return (
              <button key={m.id} type="button" role="radio" aria-checked={activo}
                onClick={() => fuente.setModo(m.id)}
                style={{
                  display: 'inline-flex', alignItems: 'center', gap: 6, padding: '6px 14px',
                  borderRadius: 'var(--radius-full)', fontSize: '0.8rem', cursor: 'pointer',
                  fontWeight: activo ? 600 : 400,
                  background: activo ? 'var(--accent-gradient)' : 'var(--bg-input)',
                  color: activo ? 'var(--text-on-accent)' : 'var(--text-secondary)',
                  border: `1px solid ${activo ? 'transparent' : 'var(--border)'}`,
                }}>
                {m.icon} {m.label}
              </button>
            );
          })}
        </div>
      )}
      {fuente.modo === 'boveda'
        ? <DesdeBoveda fuente={fuente} />
        : <ArchivosSueltos fuente={fuente} clave={clave} manual={manual} onManual={onManual} />}
    </div>
  );
}

function DesdeBoveda({ fuente }: { fuente: FuenteFacturas }) {
  const b = fuente.boveda;
  if (b.estado === 'cargando' || b.estado === 'sin-cliente') {
    return (
      <div role="status" style={{ display: 'flex', alignItems: 'center', gap: 8, ...nota }}>
        <Loader size={14} className="spin" /> Leyendo la bóveda del cliente…
      </div>
    );
  }
  if (b.estado === 'error') {
    return (
      <div style={{ display: 'grid', gap: 8 }}>
        <ErrorAlert message={b.error} />
        <button type="button" className="btn-secondary" style={{ justifySelf: 'start' }} onClick={b.recargar}>
          Reintentar
        </button>
      </div>
    );
  }
  const r = b.datos.resumen;
  const fuera = [
    r.cancelados_excluidos > 0 && `${r.cancelados_excluidos} cancelado${r.cancelados_excluidos > 1 ? 's' : ''}`,
    r.nomina_excluidos > 0 && `${r.nomina_excluidos} de nómina`,
  ].filter(Boolean);
  return (
    <div style={{
      padding: '12px 16px', borderRadius: 'var(--radius-md)', display: 'grid', gap: 6,
      background: 'var(--teal-bg-subtle)', border: '1px solid var(--border)',
    }}>
      {r.comprobantes === 0 ? (
        <>
          <strong style={{ fontSize: '0.88rem' }}>
            La bóveda no tiene CFDI vigentes de {fuente.etiqueta}.
          </strong>
          <p style={nota}>
            Súbelos en la <Link to="/app/boveda">Bóveda</Link> o bájalos con la{' '}
            <Link to="/app/sat">Descarga SAT</Link>; también puedes usar archivos sueltos.
          </p>
        </>
      ) : (
        <strong style={{ fontSize: '0.88rem' }}>
          {r.comprobantes} CFDI de {fuente.etiqueta} en la bóveda: {r.emitidos} emitido
          {r.emitidos === 1 ? '' : 's'} y {r.recibidos} recibido{r.recibidos === 1 ? '' : 's'}.
        </strong>
      )}
      {fuera.length > 0 && (
        <p style={nota}>No entran al cálculo: {fuera.join(' y ')}.</p>
      )}
      {r.relacionados_fuera_del_periodo > 0 && (
        <p style={nota}>
          {r.relacionados_fuera_del_periodo} factura{r.relacionados_fuera_del_periodo > 1 ? 's' : ''} PPD
          de otro periodo se usa{r.relacionados_fuera_del_periodo > 1 ? 'n' : ''} sólo para cruzar sus pagos.
        </p>
      )}
      {b.datos.advertencias.map((a) => (
        <p key={a} style={{ ...nota, color: 'var(--warning)' }}>{a}</p>
      ))}
      <button type="button" onClick={b.recargar}
        style={{ justifySelf: 'start', background: 'none', border: 'none', padding: 0, cursor: 'pointer',
          color: 'var(--teal-light)', fontSize: '0.78rem', display: 'inline-flex', alignItems: 'center', gap: 4 }}>
        <RefreshCw size={12} /> Actualizar
      </button>
    </div>
  );
}

function ArchivosSueltos({ fuente, clave, manual, onManual }: Props) {
  const [pendientes, setPendientes] = useState<File[]>([]);
  const [guardando, setGuardando] = useState(false);
  const [aviso, setAviso] = useState('');
  const [error, setError] = useState('');

  const guardar = async () => {
    if (!clave || pendientes.length === 0) return;
    setGuardando(true);
    setError('');
    setAviso('');
    try {
      const r = await importarCfdi(clave, pendientes);
      setPendientes([]);
      setAviso(`Guardados en la bóveda: ${r.importados}. Ya estaban: ${r.duplicados}.`
        + (r.rechazados.length ? ` Rechazados: ${r.rechazados.length}.` : ''));
      if (r.importados > 0) fuente.boveda.recargar();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudieron guardar en la bóveda.');
    } finally {
      setGuardando(false);
    }
  };

  return (
    <div style={{ display: 'grid', gap: 10 }}>
      <XMLUploader facturas={manual} onArchivos={(a) => setPendientes((p) => [...p, ...a])}
        onChange={(f) => { if (f.length === 0) setPendientes([]); onManual(f); }} />
      {clave && pendientes.length > 0 && (
        <button type="button" className="btn-secondary" onClick={guardar} disabled={guardando}
          style={{ justifySelf: 'start', display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          {guardando ? <Loader size={14} className="spin" /> : <Save size={14} />}
          Guardar en la bóveda ({pendientes.length})
        </button>
      )}
      {aviso && <p role="status" style={nota}>{aviso}</p>}
      {error && <ErrorAlert message={error} />}
    </div>
  );
}
