/**
 * Lo que impide cerrar un periodo (P2-08), tal como lo dice el backend: la
 * balanza que no cuadra (eso no se puede forzar) y la lista de CFDI vigentes
 * sin póliza (eso sí, con motivo, que queda en la bitácora).
 */

import { useState } from 'react';
import { AlertTriangle } from 'lucide-react';
import type { ValidacionCierre } from '../../services/contabilidadApi';
import { dinero } from './comun';
import { tdMonoStyle, tdStyle, thStyle } from '../../utils/styles';

interface Props {
  titulo: string;
  validacion: ValidacionCierre;
  ocupado: boolean;
  onCancelar: () => void;
  onForzar: (motivo: string) => void;
}

export default function ValidacionPeriodo({ titulo, validacion: v, ocupado, onCancelar, onForzar }: Props) {
  const [motivo, setMotivo] = useState('');
  return (
    <section className="card" aria-label={`Validación de ${titulo}`} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)', borderColor: 'var(--warning)' }}>
      <strong style={{ display: 'flex', gap: 6, alignItems: 'center', color: 'var(--warning)' }}>
        <AlertTriangle size={16} /> {titulo} no se puede cerrar todavía
      </strong>
      {!v.balanza_cuadra && (
        <div style={{ color: 'var(--danger)', fontSize: '0.85rem' }}>
          La balanza no cuadra (movimientos {v.diferencias.movimientos}, saldo final {v.diferencias.saldo_final}). Corrígela antes de cerrar.
        </div>
      )}
      {v.total_cfdi_sin_poliza > 0 && (
        <>
          <div style={{ fontSize: '0.85rem' }}>
            {v.total_cfdi_sin_poliza} CFDI vigentes del periodo no tienen póliza. Genera sus pólizas en el tab Pólizas, o cierra de todos modos con un motivo.
          </div>
          <div style={{ overflowX: 'auto', maxHeight: 260 }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.78rem' }}>
              <thead>
                <tr><th style={thStyle}>Fecha</th><th style={thStyle}>Tipo</th><th style={thStyle}>RFC</th><th style={thStyle}>UUID</th><th style={{ ...thStyle, textAlign: 'right' }}>Total</th></tr>
              </thead>
              <tbody>
                {v.cfdi_sin_poliza.map((c) => (
                  <tr key={c.uuid} style={{ borderTop: '1px solid var(--border)' }}>
                    <td style={tdStyle}>{c.fecha}</td>
                    <td style={tdStyle}>{c.tipo} {c.direccion}</td>
                    <td style={{ ...tdStyle, fontFamily: "'JetBrains Mono', monospace" }}>{c.rfc}</td>
                    <td style={{ ...tdStyle, fontFamily: "'JetBrains Mono', monospace" }}>{c.uuid}</td>
                    <td style={tdMonoStyle}>{dinero(c.total)} {c.moneda !== 'MXN' ? c.moneda : ''}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
      <div style={{ display: 'flex', gap: 'var(--space-sm)', flexWrap: 'wrap', alignItems: 'center' }}>
        {v.balanza_cuadra && v.total_cfdi_sin_poliza > 0 && (
          <>
            <input className="input-field" aria-label="Motivo para cerrar sin pólizas" placeholder="Motivo (queda en la bitácora)"
              value={motivo} onChange={(e) => setMotivo(e.target.value)} style={{ flex: 1, minWidth: 220 }} />
            <button type="button" className="btn-secondary" disabled={ocupado || motivo.trim().length < 5}
              onClick={() => onForzar(motivo.trim())}>Cerrar de todos modos</button>
          </>
        )}
        <button type="button" className="btn-secondary" onClick={onCancelar}>Volver</button>
      </div>
    </section>
  );
}
