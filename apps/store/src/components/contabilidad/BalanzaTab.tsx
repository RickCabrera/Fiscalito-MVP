/**
 * Tab Balanza de comprobación de Contabilito (T7).
 *
 * El renglón del cuadre va ARRIBA de la tabla: es lo que se revisa primero y
 * lo único que decide si vale la pena mirar el resto.
 */

import { Scale, CheckCircle2, AlertTriangle } from 'lucide-react';
import type { Balanza } from '../../services/contabilidad/balanza';
import { fmtMoney } from '../../utils/format';
import { thStyle, tdStyle, tdMonoStyle } from '../../utils/styles';

interface Props {
  balanza: Balanza;
}

export default function BalanzaTab({ balanza }: Props) {
  if (balanza.renglones.length === 0) {
    return (
      <div className="card" style={{ textAlign: 'center', padding: 'var(--space-lg)' }}>
        <Scale size={28} color="var(--text-muted)" />
        <p style={{ margin: '12px 0 0', fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
          La balanza se arma con las pólizas del lote. Carga CFDI para verla.
        </p>
      </div>
    );
  }

  const ok = balanza.cuadra;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div
        role="status"
        style={{
          display: 'flex', alignItems: 'center', gap: 10,
          padding: '12px 14px', borderRadius: 'var(--radius)',
          background: ok ? 'var(--success-bg)' : 'var(--danger-bg)',
          border: `1px solid ${ok ? 'var(--success)' : 'var(--danger-border)'}`,
        }}
      >
        {ok
          ? <CheckCircle2 size={18} style={{ color: 'var(--success)', flexShrink: 0 }} />
          : <AlertTriangle size={18} style={{ color: 'var(--danger)', flexShrink: 0 }} />}
        <div style={{ fontSize: '0.85rem', color: ok ? 'var(--success)' : 'var(--danger)' }}>
          {ok ? (
            <>
              <strong>La balanza cuadra.</strong>{' '}
              <span style={{ color: 'var(--text-secondary)' }}>
                Σ cargos = Σ abonos = {fmtMoney(balanza.totalCargos)}
              </span>
            </>
          ) : (
            <>
              <strong>La balanza NO cuadra.</strong>{' '}
              <span style={{ color: 'var(--text-secondary)' }}>
                Diferencia de {fmtMoney(balanza.diferencia)} entre cargos y abonos.
              </span>
            </>
          )}
        </div>
      </div>

      <p style={{ margin: 0, fontSize: '0.78rem', color: 'var(--text-muted)' }}>
        Sin saldos iniciales: esta balanza es la del lote de comprobantes cargados, no la del
        ejercicio.
      </p>

      <div className="card" style={{ padding: 0, overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border)' }}>
              <th style={{ ...thStyle, width: 80 }}>Cuenta</th>
              <th style={thStyle}>Nombre</th>
              <th style={{ ...thStyle, textAlign: 'right' }}>Cargos</th>
              <th style={{ ...thStyle, textAlign: 'right' }}>Abonos</th>
              <th style={{ ...thStyle, textAlign: 'right' }}>Saldo deudor</th>
              <th style={{ ...thStyle, textAlign: 'right' }}>Saldo acreedor</th>
            </tr>
          </thead>
          <tbody>
            {balanza.renglones.map((r) => (
              <tr key={r.cuenta} style={{ borderBottom: '1px solid var(--border)' }}>
                <td style={{ ...tdStyle, fontFamily: "'JetBrains Mono', monospace", color: 'var(--teal-light)' }}>
                  {r.cuenta}
                </td>
                <td style={{ ...tdStyle, color: 'var(--text-primary)' }}>{r.nombre}</td>
                <td style={tdMonoStyle}>{fmtMoney(r.cargos)}</td>
                <td style={tdMonoStyle}>{fmtMoney(r.abonos)}</td>
                <td style={tdMonoStyle}>{r.saldoDeudor > 0 ? fmtMoney(r.saldoDeudor) : ''}</td>
                <td style={tdMonoStyle}>{r.saldoAcreedor > 0 ? fmtMoney(r.saldoAcreedor) : ''}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr style={{ borderTop: '2px solid var(--border-hover)', fontWeight: 600 }}>
              <td style={tdStyle} colSpan={2}>Sumas iguales</td>
              <td style={{ ...tdMonoStyle, color: 'var(--text-primary)' }}>{fmtMoney(balanza.totalCargos)}</td>
              <td style={{ ...tdMonoStyle, color: 'var(--text-primary)' }}>{fmtMoney(balanza.totalAbonos)}</td>
              <td style={{ ...tdMonoStyle, color: 'var(--text-primary)' }}>{fmtMoney(balanza.totalSaldoDeudor)}</td>
              <td style={{ ...tdMonoStyle, color: 'var(--text-primary)' }}>{fmtMoney(balanza.totalSaldoAcreedor)}</td>
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  );
}
