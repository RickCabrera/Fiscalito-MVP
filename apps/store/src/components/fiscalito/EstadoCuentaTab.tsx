/** Tab de estado de cuenta fiscal anual */

import { useState } from 'react';
import { useProfile } from '../../context/ProfileContext';
import { useAuth } from '../../context/AuthContext';
import { obtenerEstadoCuenta, type CFDI, type EstadoCuentaResponse } from '../../services/fiscalAgentApi';
import { guardarEstadoCuenta } from '../../services/declaracionesHistory';
import { exportarEstadoCuentaPDF } from '../../services/pdfExportEstado';
import { fmtMoney } from '../../utils/format';
import { labelStyle } from '../../utils/styles';
import XMLUploader from './XMLUploader';
import ErrorAlert from '../common/ErrorAlert';
import SuccessNotice from '../common/SuccessNotice';
import { Loader, Download, RefreshCw, AlertTriangle, MessageSquare } from 'lucide-react';

const YEARS = [2026, 2025, 2024, 2023];

function fmtPct(n: number): string {
  return `${n.toFixed(1)}%`;
}

export default function EstadoCuentaTab() {
  const { profile } = useProfile();
  const { user } = useAuth();
  const [facturas, setFacturas] = useState<CFDI[]>([]);
  const [year, setYear] = useState(2025);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [resultado, setResultado] = useState<EstadoCuentaResponse | null>(null);
  const [guardado, setGuardado] = useState(false);

  const handleGenerar = async () => {
    if (facturas.length === 0) { setError('Sube las facturas del año completo.'); return; }
    if (!profile.rfc || !profile.regimen) { setError('Completa tu RFC y régimen en tu perfil.'); return; }
    setLoading(true);
    setError('');
    setGuardado(false);
    try {
      const res = await obtenerEstadoCuenta({
        contribuyente: { rfc: profile.rfc, regimen: profile.regimen, contributor_type: profile.contributorType },
        facturas, periodo_year: year, incluir_explicacion: true,
      });
      setResultado(res);
      if (user?.uid) {
        guardarEstadoCuenta(user.uid, res)
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
    const r = resultado;
    return (
      <div className="animate-in" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        {guardado && <SuccessNotice />}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <div className="card" style={{ padding: '20px' }}>
            <div style={cardLabelStyle}>Ingresos acumulados</div>
            <div style={{ ...cardValueStyle, color: 'var(--teal-light)' }}>{fmtMoney(r.ingresos_acumulados)}</div>
            <div style={cardSubStyle}>Proyección anual: {fmtMoney(r.proyeccion_ingresos_anuales)}</div>
          </div>
          <div className="card" style={{ padding: '20px' }}>
            <div style={cardLabelStyle}>Egresos acumulados</div>
            <div style={{ ...cardValueStyle, color: 'var(--purple-light)' }}>{fmtMoney(r.egresos_acumulados)}</div>
            <div style={cardSubStyle}>Proporción gastos/ingresos: {fmtPct(r.proporcion_gastos_ingresos)}</div>
          </div>
        </div>

        <div className="card">
          <div style={cardLabelStyle}>ISR anual</div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 16, marginTop: 12 }}>
            <div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: 4 }}>Estimado</div>
              <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '1.1rem', fontWeight: 700 }}>
                {fmtMoney(r.isr_anual_estimado)}
              </div>
            </div>
            <div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: 4 }}>Retenido</div>
              <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '1.1rem', fontWeight: 700, color: 'var(--teal-light)' }}>
                {fmtMoney(r.isr_retenido_acumulado)}
              </div>
            </div>
            <div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: 4 }}>Faltante</div>
              <div style={{
                fontFamily: "'JetBrains Mono', monospace", fontSize: '1.1rem', fontWeight: 700,
                color: r.isr_faltante <= 0 ? 'var(--success)' : 'var(--warning)',
              }}>
                {r.isr_faltante <= 0 ? `${fmtMoney(Math.abs(r.isr_faltante))} a favor` : fmtMoney(r.isr_faltante)}
              </div>
            </div>
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12 }}>
          <div className="card" style={{ padding: '16px', textAlign: 'center' }}>
            <div style={cardLabelStyle}>IVA neto acumulado</div>
            <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '1.1rem', fontWeight: 700 }}>
              {fmtMoney(r.iva_cobrado_acumulado - r.iva_pagado_acumulado - r.iva_retenido_acumulado)}
            </div>
            <div style={cardSubStyle}>Cobrado: {fmtMoney(r.iva_cobrado_acumulado)} / Pagado: {fmtMoney(r.iva_pagado_acumulado)}</div>
          </div>
          <div className="card" style={{ padding: '16px', textAlign: 'center' }}>
            <div style={cardLabelStyle}>Mes con mas ingresos</div>
            <div style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--teal-light)' }}>{r.mes_mayor_ingreso}</div>
          </div>
          <div className="card" style={{ padding: '16px', textAlign: 'center' }}>
            <div style={cardLabelStyle}>Mes con mas gastos</div>
            <div style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--purple-light)' }}>{r.mes_mayor_gasto}</div>
          </div>
        </div>

        {r.explicacion && (
          <div className="card" style={{ background: 'var(--purple-bg-subtle)', border: '1px solid var(--purple-muted)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
              <MessageSquare size={16} color="var(--purple-light)" />
              <h3 style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--purple-light)' }}>Explicación</h3>
            </div>
            <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', lineHeight: 1.7, whiteSpace: 'pre-wrap' }}>
              {r.explicacion}
            </p>
          </div>
        )}

        {r.advertencias.length > 0 && (
          <div className="card" style={{ background: 'var(--teal-bg-subtle)', border: '1px solid var(--warning-border)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
              <AlertTriangle size={16} color="var(--warning)" />
              <h3 style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--warning)' }}>Advertencias</h3>
            </div>
            <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 8 }}>
              {r.advertencias.map((a, i) => (
                <li key={i} style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', paddingLeft: 8, borderLeft: '2px solid var(--warning)' }}>
                  {a}
                </li>
              ))}
            </ul>
          </div>
        )}

        <div style={{ display: 'flex', justifyContent: 'center', gap: 12 }}>
          <button className="btn-primary" onClick={() => exportarEstadoCuentaPDF(r, { nombre: profile.nombre, rfc: profile.rfc })}
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
        <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: 6 }}>Estado de cuenta fiscal</h3>
        <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: 16 }}>
          Sube todas las facturas del año para ver tu panorama fiscal completo.
        </p>
        <XMLUploader facturas={facturas} onChange={setFacturas} />
      </div>
      <div className="card" style={{ display: 'flex', alignItems: 'flex-end', gap: 16, flexWrap: 'wrap' }}>
        <div>
          <label style={labelStyle}>Año</label>
          <select className="input-field" value={year} onChange={(e) => setYear(Number(e.target.value))} style={{ width: 120, cursor: 'pointer' }}>
            {YEARS.map((y) => <option key={y} value={y}>{y}</option>)}
          </select>
        </div>
        <button className="btn-primary" onClick={handleGenerar} disabled={loading}
          style={{ display: 'inline-flex', alignItems: 'center', gap: 8, opacity: loading ? 0.7 : 1 }}>
          {loading ? <Loader size={16} className="spin" /> : null}
          {loading ? 'Generando...' : 'Generar estado de cuenta'}
        </button>
      </div>
      {error && <ErrorAlert message={error} />}
    </div>
  );
}

const cardLabelStyle: React.CSSProperties = { fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 6 };
const cardValueStyle: React.CSSProperties = { fontSize: '1.5rem', fontWeight: 800, fontFamily: "'JetBrains Mono', monospace" };
const cardSubStyle: React.CSSProperties = { fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: 4 };
