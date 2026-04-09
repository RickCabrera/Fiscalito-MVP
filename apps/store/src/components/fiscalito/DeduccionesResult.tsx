/** Result display for deducciones personales calculation */

import type { DeduccionesPersonalesResponse } from '../../services/fiscalAgentApi';
import { formatMoney } from '../../utils/format';
import SuccessNotice from '../common/SuccessNotice';
import { AlertTriangle, RefreshCw, MessageSquare } from 'lucide-react';

interface Props {
  resultado: DeduccionesPersonalesResponse;
  guardado: boolean;
  onReset: () => void;
}

export default function DeduccionesResult({ resultado, guardado, onReset }: Props) {
  return (
    <div className="animate-in" style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {guardado && <SuccessNotice />}

      {/* Total deducible */}
      <div className="card" style={{
        textAlign: 'center',
        background: 'linear-gradient(135deg, var(--success-bg), var(--teal-bg))',
        border: '1px solid var(--success-border)',
      }}>
        <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 8 }}>
          Saldo a favor estimado
        </div>
        <div style={{ fontSize: '2.4rem', fontWeight: 800, fontFamily: "'JetBrains Mono', monospace", color: 'var(--success)' }}>
          {formatMoney(resultado.saldo_a_favor_estimado)}
        </div>
      </div>

      <div className="card" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        <div style={{ padding: '14px', borderRadius: 'var(--radius-xs)', background: 'var(--teal-bg-subtle)' }}>
          <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: 4 }}>Total deducible</div>
          <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '1.1rem', fontWeight: 700, color: 'var(--teal-light)' }}>
            {formatMoney(resultado.total_deducible)}
          </div>
        </div>
        <div style={{ padding: '14px', borderRadius: 'var(--radius-xs)', background: 'rgba(73,33,83,0.06)' }}>
          <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: 4 }}>Tope global ({resultado.tope_tipo})</div>
          <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '1.1rem', fontWeight: 700, color: 'var(--purple-light)' }}>
            {formatMoney(resultado.tope_global)}
          </div>
        </div>
      </div>

      {/* Desglose por concepto */}
      {resultado.desglose && resultado.desglose.length > 0 && (
        <div className="card">
          <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: 14 }}>Desglose por concepto</h3>
          {resultado.desglose.map((d, i) => (
            <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
              <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', textTransform: 'capitalize' }}>{d.concepto.replace(/_/g, ' ')}</span>
              <div style={{ display: 'flex', gap: 16, fontFamily: "'JetBrains Mono', monospace", fontSize: '0.82rem' }}>
                <span style={{ color: 'var(--text-muted)' }}>Solicitado: {formatMoney(d.monto_solicitado)}</span>
                <span style={{ color: 'var(--teal-light)', fontWeight: 600 }}>Aceptado: {formatMoney(d.monto_aceptado)}</span>
              </div>
            </div>
          ))}
        </div>
      )}

      {resultado.explicacion && (
        <div className="card" style={{ background: 'var(--purple-bg-subtle)', border: '1px solid rgba(73,33,83,0.2)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
            <MessageSquare size={16} color="var(--purple-light)" />
            <h3 style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--purple-light)' }}>Explicación</h3>
          </div>
          <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', lineHeight: 1.7, whiteSpace: 'pre-wrap' }}>{resultado.explicacion}</p>
        </div>
      )}

      {resultado.excedente_no_aprovechado > 0 && (
        <div className="card" style={{ background: 'var(--teal-bg-subtle)', border: '1px solid var(--warning-border)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
            <AlertTriangle size={16} color="var(--warning)" />
            <h3 style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--warning)' }}>Excedente no aprovechado</h3>
          </div>
          <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
            {formatMoney(resultado.excedente_no_aprovechado)} exceden el tope y no pueden deducirse.
          </div>
        </div>
      )}

      <div style={{ textAlign: 'center', marginTop: 8 }}>
        <button className="btn-secondary" onClick={onReset} style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
          <RefreshCw size={16} /> Nuevo cálculo
        </button>
      </div>
    </div>
  );
}
