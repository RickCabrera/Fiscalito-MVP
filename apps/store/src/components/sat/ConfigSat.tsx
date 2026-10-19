/**
 * Panel de configuración de la descarga diaria del SAT (P1-02): interruptores,
 * fecha desde y hora. Guarda con un botón (no en cada clic) para que un cambio
 * a medias no active la descarga de un cliente.
 */

import { useState } from 'react';
import { Loader } from 'lucide-react';
import type { ConfigDescarga } from '../../services/satDescargaApi';

export type CambiosConfig = Pick<ConfigDescarga,
  'activa' | 'emitidos' | 'recibidos' | 'metadata' | 'cancelados' | 'desde' | 'hora'>;

interface Props {
  config: ConfigDescarga;
  guardando: boolean;
  onGuardar: (c: CambiosConfig) => void;
}

const INTERRUPTORES: { campo: keyof Pick<CambiosConfig, 'emitidos' | 'recibidos' | 'metadata' | 'cancelados'>; etiqueta: string; ayuda: string }[] = [
  { campo: 'emitidos', etiqueta: 'Emitidos', ayuda: 'XML que el cliente facturó.' },
  { campo: 'recibidos', etiqueta: 'Recibidos', ayuda: 'XML que le facturaron (sólo vigentes: el SAT no entrega cancelados).' },
  { campo: 'metadata', etiqueta: 'Metadata', ayuda: 'Resumen de cada CFDI: sirve para ver lo que falta en la bóveda.' },
  { campo: 'cancelados', etiqueta: 'Cancelados', ayuda: 'Marca en la bóveda los CFDI que el SAT reporta cancelados.' },
];

export default function ConfigSat({ config, guardando, onGuardar }: Props) {
  const [borrador, setBorrador] = useState<CambiosConfig>({
    activa: config.activa, emitidos: config.emitidos, recibidos: config.recibidos,
    metadata: config.metadata, cancelados: config.cancelados, desde: config.desde,
    hora: config.hora,
  });
  const poner = <K extends keyof CambiosConfig>(k: K, v: CambiosConfig[K]) =>
    setBorrador((b) => ({ ...b, [k]: v }));

  return (
    <form className="card" style={{ padding: 'var(--space-md)', display: 'grid', gap: 'var(--space-sm)' }}
      onSubmit={(e) => { e.preventDefault(); onGuardar(borrador); }}>
      <h3 style={{ margin: 0 }}>Descarga diaria</h3>
      <label style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
        <input type="checkbox" checked={borrador.activa}
          onChange={(e) => poner('activa', e.target.checked)} />
        <strong>Descargar del SAT todos los días</strong>
      </label>
      {config.pausada_por === 'efirma' && (
        <p role="status" style={{ margin: 0, color: 'var(--warning)', fontSize: '0.85rem' }}>
          En pausa: falta una e.firma vigente.
        </p>
      )}
      {INTERRUPTORES.map(({ campo, etiqueta, ayuda }) => (
        <label key={campo} style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
          <input type="checkbox" checked={borrador[campo]}
            onChange={(e) => poner(campo, e.target.checked)} />
          <span>
            {etiqueta}
            <span style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)' }}>{ayuda}</span>
          </span>
        </label>
      ))}
      <div style={{ display: 'flex', gap: 'var(--space-sm)', flexWrap: 'wrap' }}>
        <label style={{ display: 'grid', gap: 4, fontSize: '0.85rem' }}>
          Desde
          <input type="date" value={borrador.desde ?? ''}
            onChange={(e) => poner('desde', e.target.value || null)} />
        </label>
        <label style={{ display: 'grid', gap: 4, fontSize: '0.85rem' }}>
          Hora (Ciudad de México)
          <input type="time" value={borrador.hora}
            onChange={(e) => poner('hora', e.target.value)} />
        </label>
      </div>
      <button type="submit" className="btn-primary" disabled={guardando} style={{ justifySelf: 'start' }}>
        {guardando ? <Loader size={16} className="spin" /> : 'Guardar configuración'}
      </button>
    </form>
  );
}
