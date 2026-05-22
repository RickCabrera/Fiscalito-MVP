/** Tab de cálculo multi-periodo con gráfica de barras CSS */

import { useState } from 'react';
import { useProfile } from '../../context/ProfileContext';
import { useAuth } from '../../context/AuthContext';
import { calcularMultiPeriodo, type CFDI, type MultiPeriodoResponse } from '../../services/fiscalAgentApi';
import { guardarMultiPeriodo } from '../../services/declaracionesHistory';
import { exportarMultiPeriodoPDF } from '../../services/pdfExportMulti';
import { fmtMoney } from '../../utils/format';
import { thStyle, tdStyle, tdMonoStyle, labelStyle } from '../../utils/styles';
import XMLUploader from './XMLUploader';
import ErrorAlert from '../common/ErrorAlert';
import SuccessNotice from '../common/SuccessNotice';
import { Loader, Download, RefreshCw, MessageSquare } from 'lucide-react';

const MESES = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];
const YEARS = [2026, 2025, 2024, 2023];
const TENDENCIA_EMOJI: Record<string, string> = { subiendo: '📈', bajando: '📉', estable: '➡️' };

export default function MultiPeriodoTab() {
  const { profile } = useProfile();
  const { user } = useAuth();
  const [facturas, setFacturas] = useState<CFDI[]>([]);
  const [year, setYear] = useState(2025);
  const [selected, setSelected] = useState<number[]>([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [resultado, setResultado] = useState<MultiPeriodoResponse | null>(null);
  const [guardado, setGuardado] = useState(false);

  const toggleMonth = (m: number) => {
    setSelected((prev) => prev.includes(m) ? prev.filter((x) => x !== m) : [...prev, m].sort((a, b) => a - b));
  };

  const toggleAll = () => {
    setSelected(selected.length === 12 ? [] : [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]);
  };

  const handleCalcular = async () => {
    if (facturas.length === 0) { setError('Sube al menos una factura XML.'); return; }
    if (selected.length === 0) { setError('Selecciona al menos un periodo.'); return; }
    if (!profile.rfc || !profile.regimen) { setError('Completa tu RFC y régimen en tu perfil.'); return; }
    setLoading(true);
    setError('');
    setGuardado(false);
    try {
      const res = await calcularMultiPeriodo({
        contribuyente: { rfc: profile.rfc, regimen: profile.regimen, contributor_type: profile.contributorType },
        facturas, periodo_year: year, periodos: selected, incluir_explicacion: true,
      });
      setResultado(res);
      if (user?.uid) {
        guardarMultiPeriodo(user.uid, res)
          .then(() => setGuardado(true))
          .catch(() => { /* silent */ });
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error inesperado');
    } finally {
      setLoading(false);
    }
  };

  if (resultado) {
    const { acumulado } = resultado;
    const maxTotal = Math.max(...resultado.resultados.map((r) => Math.abs(r.desglose.total_a_pagar)), 1);

    return (
      <div className="animate-in" style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
        {guardado && <SuccessNotice />}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
          {[
            { label: 'Total ISR', value: fmtMoney(acumulado.total_isr_pagado), color: 'var(--teal-light)' },
            { label: 'Total IVA', value: fmtMoney(acumulado.total_iva_pagado), color: 'var(--purple-light)' },
            { label: 'Promedio mensual', value: fmtMoney(acumulado.promedio_mensual), color: 'var(--text-primary)' },
            { label: 'Tendencia', value: `${TENDENCIA_EMOJI[acumulado.tendencia] ?? '➡️'} ${acumulado.tendencia}`, color: 'var(--warning)' },
          ].map((s) => (
            <div key={s.label} className="card" style={{ textAlign: 'center', padding: '16px 12px' }}>
              <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 6 }}>{s.label}</div>
              <div style={{ fontSize: '1.1rem', fontWeight: 700, fontFamily: "'JetBrains Mono', monospace", color: s.color }}>{s.value}</div>
            </div>
          ))}
        </div>

        <div className="card">
          <h3 style={{ fontSize: '0.95rem', fontWeight: 600, marginBottom: 16 }}>Total por periodo</h3>
          <div style={{ display: 'flex', alignItems: 'flex-end', gap: 6, height: 160 }}>
            {resultado.resultados.map((r, i) => {
              const total = r.desglose.total_a_pagar;
              const height = Math.max((Math.abs(total) / maxTotal) * 140, 4);
              const esNeg = total <= 0;
              return (
                <div key={i} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
                  <div style={{ fontSize: '0.65rem', fontFamily: "'JetBrains Mono', monospace", color: esNeg ? 'var(--success)' : 'var(--text-secondary)' }}>
                    {fmtMoney(Math.abs(total))}
                  </div>
                  <div style={{
                    width: '100%', maxWidth: 40, height, borderRadius: '4px 4px 0 0',
                    background: esNeg
                      ? 'linear-gradient(180deg, rgba(46,204,113,0.6), rgba(46,204,113,0.2))'
                      : 'var(--accent-gradient)',
                    transition: 'height 0.3s',
                  }} />
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{r.periodo}</div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border)' }}>
                  {['Periodo', 'ISR', 'IVA', 'Total', 'Facturas'].map((h) => (
                    <th key={h} style={thStyle}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {resultado.resultados.map((r, i) => (
                  <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                    <td style={{ ...tdStyle, fontWeight: 500 }}>{r.periodo}</td>
                    <td style={tdMonoStyle}>{fmtMoney(r.desglose.isr_a_pagar)}</td>
                    <td style={tdMonoStyle}>{fmtMoney(r.desglose.iva_a_pagar)}</td>
                    <td style={{ ...tdMonoStyle, fontWeight: 700, color: r.desglose.total_a_pagar <= 0 ? 'var(--success)' : 'var(--text-primary)' }}>
                      {fmtMoney(r.desglose.total_a_pagar)}
                    </td>
                    <td style={{ ...tdStyle, textAlign: 'center' }}>{r.desglose.cantidad_facturas_ingreso ?? 0}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {resultado.explicacion && (
          <div className="card" style={{ background: 'var(--purple-bg-subtle)', border: '1px solid var(--purple-muted)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
              <MessageSquare size={16} color="var(--purple-light)" />
              <h3 style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--purple-light)' }}>Explicación</h3>
            </div>
            <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', lineHeight: 1.7, whiteSpace: 'pre-wrap' }}>
              {resultado.explicacion}
            </p>
          </div>
        )}

        <div style={{ display: 'flex', justifyContent: 'center', gap: 12 }}>
          <button className="btn-primary" onClick={() => exportarMultiPeriodoPDF(resultado, { nombre: profile.nombre, rfc: profile.rfc })}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
            <Download size={16} /> Descargar PDF
          </button>
          <button className="btn-secondary" onClick={() => setResultado(null)}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
            <RefreshCw size={16} /> Nuevo cálculo
          </button>
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div className="card">
        <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: 6 }}>Cálculo multi-periodo</h3>
        <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: 16 }}>
          Calcula varios meses a la vez y visualiza la tendencia fiscal del año.
        </p>
        <XMLUploader facturas={facturas} onChange={setFacturas} />
      </div>

      <div className="card">
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 16 }}>
          <div>
            <label style={labelStyle}>Año</label>
            <select className="input-field" value={year} onChange={(e) => setYear(Number(e.target.value))} style={{ width: 120, cursor: 'pointer' }}>
              {YEARS.map((y) => <option key={y} value={y}>{y}</option>)}
            </select>
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
              <label style={labelStyle}>Periodos</label>
              <button onClick={toggleAll} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '0.78rem', color: 'var(--teal-light)' }}>
                {selected.length === 12 ? 'Deseleccionar todo' : 'Seleccionar todo'}
              </button>
            </div>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {MESES.map((m, i) => {
                const active = selected.includes(i + 1);
                return (
                  <button key={i} onClick={() => toggleMonth(i + 1)} style={{
                    padding: '6px 12px', borderRadius: 'var(--radius-full)', fontSize: '0.78rem', fontWeight: active ? 600 : 400,
                    background: active ? 'var(--accent-gradient)' : 'var(--bg-input)',
                    color: active ? 'var(--text-on-accent)' : 'var(--text-muted)',
                    border: `1px solid ${active ? 'transparent' : 'var(--border)'}`, cursor: 'pointer', transition: 'all 0.2s',
                  }}>
                    {m}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
        <button className="btn-primary" onClick={handleCalcular} disabled={loading}
          style={{ display: 'inline-flex', alignItems: 'center', gap: 8, opacity: loading ? 0.7 : 1 }}>
          {loading ? <Loader size={16} className="spin" /> : null}
          {loading ? 'Calculando...' : 'Calcular periodos'}
        </button>
      </div>

      {error && <ErrorAlert message={error} />}
    </div>
  );
}
