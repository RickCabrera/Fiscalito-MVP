/**
 * "Descargar ahora" (rango personalizado) y "Descarga histórica" (por meses).
 * Los dos sólo ENCOLAN: el SAT puede tardar horas o días, y la pantalla lo
 * muestra en el calendario y en la lista de solicitudes.
 */

import { useState } from 'react';
import { Download, History, Loader } from 'lucide-react';

interface Props {
  deshabilitado: boolean;
  ocupado: 'ahora' | 'historica' | null;
  onAhora: (desde: string, hasta: string) => void;
  onHistorica: (desde: string) => void;
}

function hoyMenos(dias: number): string {
  const d = new Date();
  d.setDate(d.getDate() - dias);
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  return `${d.getFullYear()}-${mm}-${dd}`;
}

export default function AccionesSat({ deshabilitado, ocupado, onAhora, onHistorica }: Props) {
  const [desde, setDesde] = useState(hoyMenos(7));
  const [hasta, setHasta] = useState(hoyMenos(1));
  const [desdeHistorica, setDesdeHistorica] = useState(`${new Date().getFullYear() - 1}-01-01`);

  return (
    <div className="card" style={{ padding: 'var(--space-md)', display: 'grid', gap: 'var(--space-md)' }}>
      <div style={{ display: 'grid', gap: 'var(--space-xs)' }}>
        <h3 style={{ margin: 0 }}>Descargar ahora</h3>
        <div style={{ display: 'flex', gap: 'var(--space-sm)', flexWrap: 'wrap', alignItems: 'end' }}>
          <label style={{ display: 'grid', gap: 4, fontSize: '0.85rem' }}>
            Desde
            <input type="date" value={desde} onChange={(e) => setDesde(e.target.value)} aria-label="Descargar desde" />
          </label>
          <label style={{ display: 'grid', gap: 4, fontSize: '0.85rem' }}>
            Hasta
            <input type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} aria-label="Descargar hasta" />
          </label>
          <button type="button" className="btn-primary" disabled={deshabilitado || ocupado !== null || !desde || !hasta}
            onClick={() => onAhora(desde, hasta)}>
            {ocupado === 'ahora' ? <Loader size={16} className="spin" /> : <Download size={16} />} Descargar ahora
          </button>
        </div>
      </div>
      <div style={{ display: 'grid', gap: 'var(--space-xs)' }}>
        <h3 style={{ margin: 0 }}>Descarga histórica</h3>
        <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
          Pide al SAT un mes a la vez desde la fecha que elijas hasta ayer. El SAT guarda hasta seis años.
        </p>
        <div style={{ display: 'flex', gap: 'var(--space-sm)', flexWrap: 'wrap', alignItems: 'end' }}>
          <label style={{ display: 'grid', gap: 4, fontSize: '0.85rem' }}>
            Desde
            <input type="date" value={desdeHistorica} onChange={(e) => setDesdeHistorica(e.target.value)} aria-label="Histórica desde" />
          </label>
          <button type="button" className="btn-secondary" disabled={deshabilitado || ocupado !== null || !desdeHistorica}
            onClick={() => onHistorica(desdeHistorica)}>
            {ocupado === 'historica' ? <Loader size={16} className="spin" /> : <History size={16} />} Descarga histórica
          </button>
        </div>
      </div>
    </div>
  );
}
