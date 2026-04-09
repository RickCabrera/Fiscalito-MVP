/** Table displaying uploaded CFDI facturas with type badges and delete action */

import type { CFDI } from '../../services/fiscalAgentApi';
import { tdStyle } from '../../utils/styles';
import { FileText, Trash2 } from 'lucide-react';

interface Props {
  facturas: CFDI[];
  onRemove: (uuid: string) => void;
}

export default function FacturaTable({ facturas, onRemove }: Props) {
  if (facturas.length === 0) return null;

  return (
    <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
      <div style={{ padding: '14px 20px', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <FileText size={16} color="var(--teal-light)" />
          <span style={{ fontSize: '0.9rem', fontWeight: 600 }}>{facturas.length} factura{facturas.length > 1 ? 's' : ''}</span>
        </div>
      </div>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border)' }}>
              {['Fecha', 'Emisor', 'RFC Emisor', 'Subtotal', 'IVA', 'Tipo', ''].map((h) => (
                <th key={h} style={{ padding: '10px 14px', textAlign: 'left', color: 'var(--text-muted)', fontWeight: 500, fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: 0.5 }}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {facturas.map((f) => (
              <tr key={f.uuid} style={{ borderBottom: '1px solid var(--border)' }}>
                <td style={tdStyle}>{f.fecha.substring(0, 10)}</td>
                <td style={tdStyle}>{f.rfc_emisor}</td>
                <td style={{ ...tdStyle, fontFamily: "'JetBrains Mono', monospace", fontSize: '0.78rem' }}>{f.rfc_emisor}</td>
                <td style={{ ...tdStyle, fontFamily: "'JetBrains Mono', monospace" }}>${f.subtotal.toLocaleString('es-MX')}</td>
                <td style={{ ...tdStyle, fontFamily: "'JetBrains Mono', monospace" }}>${(f.iva_trasladado ?? 0).toLocaleString('es-MX')}</td>
                <td style={tdStyle}>
                  <span style={{
                    padding: '2px 8px', borderRadius: 'var(--radius-full)', fontSize: '0.7rem', fontWeight: 600,
                    background: f.tipo === 'I' ? 'rgba(46,204,113,0.12)' : f.tipo === 'E' ? 'var(--danger-bg)' : 'var(--teal-bg)',
                    color: f.tipo === 'I' ? 'var(--success)' : f.tipo === 'E' ? 'var(--danger)' : 'var(--teal-light)',
                  }}>
                    {f.tipo === 'I' ? 'Ingreso' : f.tipo === 'E' ? 'Egreso' : f.tipo}
                  </span>
                </td>
                <td style={tdStyle}>
                  <button onClick={() => onRemove(f.uuid)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', padding: 4 }}>
                    <Trash2 size={14} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
