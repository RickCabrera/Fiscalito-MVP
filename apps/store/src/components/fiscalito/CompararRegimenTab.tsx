/** Tab para comparar todos los regímenes fiscales de personas físicas entre sí */

import { useState } from 'react';
import { useProfile } from '../../context/ProfileContext';
import { compararRegimenes, type CompararRegimenResponse, type ResultadoRegimen } from '../../services/fiscalAgentApi';
import { formatMoney } from '../../utils/format';
import { labelStyle } from '../../utils/styles';
import ErrorAlert from '../common/ErrorAlert';
import { BarChart3, Loader, MessageSquare, RefreshCw, Trophy, AlertCircle, Info } from 'lucide-react';

const COLORES_REGIMEN: Record<string, string> = {
  '626': 'var(--teal-light)',
  '612': 'var(--purple-light)',
  '606': 'var(--warning)',
  '625': 'var(--success)',
  '605': 'var(--text-secondary)',
};

const POSICION_LABEL = ['1°', '2°', '3°', '4°', '5°'];

function RegimenRow({ resultado, posicion, esMejor }: { resultado: ResultadoRegimen; posicion: number; esMejor: boolean }) {
  const [expandido, setExpandido] = useState(false);
  const color = COLORES_REGIMEN[resultado.regimen] ?? 'var(--text-secondary)';

  return (
    <div style={{
      borderRadius: 'var(--radius-sm)',
      border: `1px solid ${esMejor ? color : 'var(--border)'}`,
      background: esMejor ? `${color}08` : 'var(--bg-card)',
      opacity: resultado.disponible ? 1 : 0.55,
      transition: 'all 0.2s',
    }}>
      <div style={{
        display: 'flex', alignItems: 'center', gap: 12,
        padding: '14px 16px', cursor: resultado.notas.length > 0 ? 'pointer' : 'default',
      }} onClick={() => resultado.notas.length > 0 && setExpandido(e => !e)}>

        {/* Posición */}
        <div style={{
          width: 28, height: 28, borderRadius: '50%', flexShrink: 0,
          background: esMejor ? color : 'var(--bg-surface)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: '0.7rem', fontWeight: 700,
          color: esMejor ? 'var(--bg-dark)' : 'var(--text-muted)',
        }}>
          {resultado.disponible ? (esMejor ? <Trophy size={13} /> : POSICION_LABEL[posicion]) : '—'}
        </div>

        {/* Nombre y badge */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <span style={{ fontWeight: esMejor ? 700 : 500, fontSize: '0.92rem', color: esMejor ? color : 'var(--text-primary)' }}>
              {resultado.nombre}
            </span>
            <span style={{ fontSize: '0.68rem', color: 'var(--text-muted)', background: 'var(--bg-surface)', padding: '2px 7px', borderRadius: 4 }}>
              {resultado.regimen}
            </span>
            {!resultado.disponible && (
              <span style={{ fontSize: '0.68rem', color: 'var(--danger)', background: 'var(--danger-bg)', padding: '2px 7px', borderRadius: 4, border: '1px solid var(--danger-border)' }}>
                No disponible
              </span>
            )}
            {esMejor && (
              <span style={{ fontSize: '0.68rem', color: 'var(--bg-dark)', background: color, padding: '2px 8px', borderRadius: 4, fontWeight: 700 }}>
                Recomendado
              </span>
            )}
          </div>
        </div>

        {/* ISR mensual / anual */}
        <div style={{ textAlign: 'right', flexShrink: 0 }}>
          <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '1rem', fontWeight: 700, color: resultado.disponible ? color : 'var(--text-muted)' }}>
            {formatMoney(resultado.isr_mensual)}<span style={{ fontSize: '0.7rem', fontWeight: 400, color: 'var(--text-muted)', marginLeft: 3 }}>/mes</span>
          </div>
          <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '0.78rem', color: 'var(--text-muted)' }}>
            {formatMoney(resultado.isr_anual)} /año
          </div>
        </div>

        {resultado.notas.length > 0 && (
          <Info size={14} color="var(--text-muted)" style={{ flexShrink: 0 }} />
        )}
      </div>

      {/* Notas expandidas */}
      {expandido && resultado.notas.length > 0 && (
        <div style={{ padding: '0 16px 14px 56px', display: 'flex', flexDirection: 'column', gap: 4 }}>
          {resultado.notas.map((nota, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 6 }}>
              <AlertCircle size={12} color="var(--text-muted)" style={{ flexShrink: 0, marginTop: 2 }} />
              <span style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>{nota}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function CompararRegimenTab() {
  const { profile } = useProfile();
  const [ingresos, setIngresos] = useState('');
  const [gastos, setGastos] = useState('');
  const [predial, setPredial] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [resultado, setResultado] = useState<CompararRegimenResponse | null>(null);

  const handleComparar = async () => {
    const ingNum = parseFloat(ingresos);
    const gasNum = parseFloat(gastos) || 0;
    const predNum = parseFloat(predial) || 0;
    if (!ingNum || ingNum <= 0) { setError('Ingresa tus ingresos mensuales estimados.'); return; }
    setLoading(true);
    setError('');
    try {
      const res = await compararRegimenes({
        ingresos_mensuales_estimados: ingNum,
        gastos_mensuales_estimados: gasNum,
        predial_mensual: predNum,
        tipo_actividad: profile.actividad || '',
        incluir_explicacion: true,
      });
      setResultado(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error inesperado');
    } finally {
      setLoading(false);
    }
  };

  const reset = () => { setResultado(null); setIngresos(''); setGastos(''); setPredial(''); setError(''); };

  if (resultado) {
    const disponibles = resultado.resultados.filter(r => r.disponible);

    return (
      <div className="animate-in" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        {/* Header resumen */}
        <div className="card" style={{ background: 'var(--bg-surface)', padding: '16px 20px' }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
            <div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 4 }}>Régimen más conveniente</div>
              <div style={{ fontSize: '1.4rem', fontWeight: 800, color: COLORES_REGIMEN[resultado.regimen_recomendado] ?? 'var(--teal-light)' }}>
                {resultado.nombre_recomendado}
              </div>
              <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginTop: 4, maxWidth: 480 }}>
                {resultado.recomendacion}
              </div>
            </div>
            {resultado.ahorro_maximo > 0 && (
              <div style={{ textAlign: 'right' }}>
                <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginBottom: 2 }}>Ahorro máximo vs más caro</div>
                <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '1.3rem', fontWeight: 700, color: 'var(--success)' }}>
                  {formatMoney(resultado.ahorro_maximo)}<span style={{ fontSize: '0.75rem', fontWeight: 400 }}>/año</span>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Ranking de regímenes */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 1, padding: '0 4px' }}>
            Comparativa ISR anual estimado — {disponibles.length} regímenes disponibles
          </div>
          {resultado.resultados.map((r, i) => {
            const posDisp = resultado.resultados.filter(x => x.disponible).indexOf(r);
            return (
              <RegimenRow
                key={r.regimen}
                resultado={r}
                posicion={posDisp >= 0 ? posDisp : i}
                esMejor={r.regimen === resultado.regimen_recomendado}
              />
            );
          })}
          <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', padding: '4px 4px 0', display: 'flex', alignItems: 'center', gap: 4 }}>
            <Info size={11} /> Toca cada régimen para ver sus condiciones y restricciones.
          </div>
        </div>

        {/* Explicación IA */}
        {resultado.explicacion && (
          <div className="card" style={{ background: 'var(--purple-bg-subtle)', border: '1px solid var(--purple-muted)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
              <MessageSquare size={16} color="var(--purple-light)" />
              <h3 style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--purple-light)' }}>Análisis detallado</h3>
            </div>
            <p style={{ fontSize: '0.88rem', color: 'var(--text-secondary)', lineHeight: 1.7, whiteSpace: 'pre-wrap' }}>
              {resultado.explicacion}
            </p>
          </div>
        )}

        <div>
          <button className="btn-secondary" onClick={reset} style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
            <RefreshCw size={16} /> Nueva comparación
          </button>
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div className="card">
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
          <BarChart3 size={20} color="var(--teal-light)" />
          <h3 style={{ fontSize: '1rem', fontWeight: 600 }}>Comparar todos los regímenes</h3>
        </div>
        <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: 20 }}>
          Simula cuánto pagarías de ISR en los 5 regímenes de personas físicas (626, 612, 606, 625, 605) con los mismos ingresos.
        </p>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16 }}>
          <div>
            <label style={labelStyle}>Ingresos mensuales estimados *</label>
            <input className="input-field" type="number" placeholder="Ej: 35,000" value={ingresos}
              onChange={(e) => setIngresos(e.target.value)}
              style={{ fontFamily: "'JetBrains Mono', monospace" }} />
          </div>
          <div>
            <label style={labelStyle}>Gastos mensuales deducibles</label>
            <input className="input-field" type="number" placeholder="Ej: 12,000" value={gastos}
              onChange={(e) => setGastos(e.target.value)}
              style={{ fontFamily: "'JetBrains Mono', monospace" }} />
          </div>
          <div>
            <label style={labelStyle}>Predial mensual (606 Arrendamiento)</label>
            <input className="input-field" type="number" placeholder="Ej: 800" value={predial}
              onChange={(e) => setPredial(e.target.value)}
              style={{ fontFamily: "'JetBrains Mono', monospace" }} />
            <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: 4, display: 'block' }}>
              Solo relevante si tienes ingresos por renta
            </span>
          </div>
        </div>
      </div>

      <button className="btn-primary" onClick={handleComparar} disabled={loading}
        style={{ alignSelf: 'flex-start', display: 'inline-flex', alignItems: 'center', gap: 8, opacity: loading ? 0.7 : 1 }}>
        {loading ? <Loader size={16} className="spin" /> : <BarChart3 size={16} />}
        {loading ? 'Comparando...' : 'Comparar los 5 regímenes'}
      </button>

      {error && <ErrorAlert message={error} />}
    </div>
  );
}
