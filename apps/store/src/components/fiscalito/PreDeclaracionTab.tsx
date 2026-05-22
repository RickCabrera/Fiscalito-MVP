/** Tab de pre-declaración: subir XMLs, ver tabla de facturas, calcular */

import { useState, useRef, useCallback, useEffect } from 'react';
import { useProfile } from '../../context/ProfileContext';
import { useAuth } from '../../context/AuthContext';
import { parseMultipleCFDI } from '../../services/cfdiParser';
import { calcularPreDeclaracion } from '../../services/fiscalAgentApi';
import { guardarDeclaracion, obtenerAcumuladoAnterior } from '../../services/declaracionesHistory';
import { useAgent } from '../../agent/AgentContext';
import { labelStyle } from '../../utils/styles';
import ErrorAlert from '../common/ErrorAlert';
import SuccessNotice from '../common/SuccessNotice';
import FacturaTable from './FacturaTable';
import ResultadoDeclaracion from './ResultadoDeclaracion';
import { Upload, AlertCircle, Loader, CheckCircle } from 'lucide-react';

const MESES = [
  'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
  'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre',
];
const YEARS = [2026, 2025, 2024, 2023];

export default function PreDeclaracionTab() {
  const { profile } = useProfile();
  const { user } = useAuth();
  const agent = useAgent();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const facturas = agent.facturas;
  const resultado = agent.resultado;
  const year = agent.periodoYear;
  const month = agent.periodoMonth;

  const [parseErrors, setParseErrors] = useState<{ fileName: string; error: string }[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [dragging, setDragging] = useState(false);
  const [guardado, setGuardado] = useState(false);
  const [pagosAnteriores, setPagosAnteriores] = useState(0);
  const [pagosAnterioresAuto, setPagosAnterioresAuto] = useState<number | null>(null);
  const [loadingPagos, setLoadingPagos] = useState(false);
  const [modoManual, setModoManual] = useState(false);
  const [predialPagado, setPredialPagado] = useState(0);
  const [incluyePredial, setIncluyePredial] = useState(false);
  const [acumuladoAnterior, setAcumuladoAnterior] = useState<{
    ingresos_acumulados: number;
    deducciones_acumuladas: number;
    isr_pagado_anterior: number;
    meses_encontrados: number[];
    meses_faltantes: number[];
  } | null>(null);
  const [loadingAcumulado, setLoadingAcumulado] = useState(false);

  const esArrendamiento = profile.regimen === '606';
  const esEmpresarialOArr = ['612', '606'].includes(profile.regimen || '');

  useEffect(() => {
    if (!esEmpresarialOArr || month <= 1 || !user?.uid) {
      setAcumuladoAnterior(null);
      setPagosAnterioresAuto(null);
      return;
    }
    let cancelled = false;
    setLoadingAcumulado(true);
    setLoadingPagos(true);
    obtenerAcumuladoAnterior(user.uid, year, month)
      .then((result) => {
        if (cancelled) return;
        setAcumuladoAnterior(result);
        setPagosAnterioresAuto(result.isr_pagado_anterior);
        if (!modoManual) setPagosAnteriores(result.isr_pagado_anterior);
      })
      .catch(() => {
        if (!cancelled) {
          setAcumuladoAnterior(null);
          setPagosAnterioresAuto(null);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoadingAcumulado(false);
          setLoadingPagos(false);
        }
      });
    return () => { cancelled = true; };
  }, [year, month, user?.uid, esEmpresarialOArr, modoManual]);

  const handleFiles = useCallback(async (files: FileList | File[]) => {
    const xmlFiles = Array.from(files).filter((f) => f.name.endsWith('.xml'));
    if (xmlFiles.length === 0) return;
    const result = await parseMultipleCFDI(xmlFiles);
    const existingUuids = new Set(agent.facturas.map((f) => f.uuid));
    const nuevas = result.success.filter((f) => !existingUuids.has(f.uuid));
    if (nuevas.length > 0) agent.setFacturas([...agent.facturas, ...nuevas]);
    if (result.errors.length > 0) {
      setParseErrors((prev) => [...prev, ...result.errors]);
    }
  }, [agent]);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    handleFiles(e.dataTransfer.files);
  }, [handleFiles]);

  const removeCFDI = (uuid: string) => {
    agent.setFacturas(agent.facturas.filter((f) => f.uuid !== uuid));
  };

  const handleCalcular = async () => {
    if (facturas.length === 0) { setError('Sube al menos una factura XML.'); return; }
    if (!profile.rfc || !profile.regimen) { setError('Completa tu RFC y régimen en tu perfil.'); return; }
    setLoading(true);
    setError('');
    setGuardado(false);
    try {
      const res = await calcularPreDeclaracion({
        contribuyente: {
          rfc: profile.rfc,
          regimen: profile.regimen,
          contributor_type: profile.contributorType,
        },
        facturas,
        periodo_year: year,
        periodo_month: month,
        incluir_explicacion: true,
        pagos_provisionales_anteriores:
          esEmpresarialOArr && month > 1 ? pagosAnteriores : undefined,
        ingresos_acumulados_anteriores:
          esEmpresarialOArr && month > 1 && acumuladoAnterior
            ? acumuladoAnterior.ingresos_acumulados : undefined,
        deducciones_acumuladas_anteriores:
          esEmpresarialOArr && month > 1 && acumuladoAnterior
            ? acumuladoAnterior.deducciones_acumuladas : undefined,
        predial_pagado: esArrendamiento ? predialPagado : undefined,
      });
      agent.setResultado(res);
      if (user?.uid) {
        guardarDeclaracion(user.uid, {
          tipo: 'mensual', periodo: res.periodo, regimen: res.regimen, fecha_calculo: new Date(),
          desglose: {
            total_ingresos_facturados: res.desglose.total_ingresos_facturados,
            total_ingresos_gravados: res.desglose.total_ingresos_gravados,
            cantidad_facturas_ingreso: res.desglose.cantidad_facturas_ingreso ?? 0,
            total_egresos: res.desglose.total_egresos ?? 0,
            total_deducciones_autorizadas: res.desglose.total_deducciones_autorizadas ?? 0,
            cantidad_facturas_egreso: res.desglose.cantidad_facturas_egreso ?? 0,
            base_isr: res.desglose.base_isr, tasa_isr: res.desglose.tasa_isr,
            isr_causado: res.desglose.isr_causado, isr_retenido: res.desglose.isr_retenido ?? 0,
            isr_a_pagar: res.desglose.isr_a_pagar,
            iva_trasladado_cobrado: res.desglose.iva_trasladado_cobrado ?? 0,
            iva_trasladado_pagado: res.desglose.iva_trasladado_pagado ?? 0,
            iva_retenido: res.desglose.iva_retenido ?? 0,
            iva_a_pagar: res.desglose.iva_a_pagar, total_a_pagar: res.desglose.total_a_pagar,
          },
          explicacion: res.explicacion ?? null,
          advertencias: res.advertencias ?? [], recomendaciones: res.recomendaciones ?? [],
          facturas_count: facturas.length,
        }).then(() => setGuardado(true)).catch(() => { /* silent */ });
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error inesperado');
    } finally {
      setLoading(false);
    }
  };

  const resetAll = () => {
    agent.setFacturas([]);
    agent.setResultado(null);
    setParseErrors([]);
    setError('');
  };

  if (resultado) {
    return (
      <div>
        {guardado && <div style={{ marginBottom: 16 }}><SuccessNotice /></div>}
        <ResultadoDeclaracion resultado={resultado} onNuevaDeclaracion={resetAll} />
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Drop zone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        style={{
          border: `2px dashed ${dragging ? 'var(--teal-light)' : 'var(--border-hover)'}`,
          borderRadius: 'var(--radius)', padding: '40px 24px', textAlign: 'center',
          cursor: 'pointer', transition: 'all 0.2s',
          background: dragging ? 'var(--teal-bg-subtle)' : 'transparent',
        }}
      >
        <Upload size={32} color="var(--text-secondary)" style={{ marginBottom: 12 }} />
        <div style={{ fontSize: '0.95rem', color: 'var(--text-secondary)', marginBottom: 4 }}>Arrastra tus archivos XML aquí</div>
        <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>o haz clic para seleccionar archivos CFDI</div>
        <input ref={fileInputRef} type="file" accept=".xml" multiple hidden
          onChange={(e) => e.target.files && handleFiles(e.target.files)} />
      </div>

      {parseErrors.length > 0 && (
        <div style={{ padding: '12px 16px', borderRadius: 'var(--radius-xs)', background: 'var(--danger-bg)', border: '1px solid var(--danger-border)' }}>
          {parseErrors.map((err, i) => (
            <div key={i} style={{ fontSize: '0.8rem', color: 'var(--danger)', display: 'flex', alignItems: 'center', gap: 6 }}>
              <AlertCircle size={14} /> {err.fileName}: {err.error}
            </div>
          ))}
        </div>
      )}

      <FacturaTable facturas={facturas} onRemove={removeCFDI} />

      {/* Estado del acumulado Art. 106 LISR (612/606 con mes > 1) */}
      {esEmpresarialOArr && month > 1 && (
        <>
          {loadingAcumulado && (
            <div style={{
              padding: '12px 16px', borderRadius: 'var(--radius-md)',
              background: 'var(--teal-bg-subtle)', border: '1px solid var(--border-hover)',
              display: 'flex', alignItems: 'center', gap: 10,
              fontSize: '0.82rem', color: 'var(--text-secondary)',
            }}>
              <Loader size={14} className="spin" />
              Cargando datos de meses anteriores…
            </div>
          )}
          {!loadingAcumulado && acumuladoAnterior && acumuladoAnterior.meses_faltantes.length === 0 && acumuladoAnterior.meses_encontrados.length > 0 && (
            <div style={{
              padding: '12px 16px', borderRadius: 'var(--radius-md)',
              background: 'var(--success-bg)', border: '1px solid var(--success-border)',
              display: 'flex', alignItems: 'flex-start', gap: 10,
            }}>
              <CheckCircle size={16} color="var(--success)" style={{ flexShrink: 0, marginTop: 2 }} />
              <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                <strong style={{ color: 'var(--text-primary)' }}>Art. 106</strong> — Datos de{' '}
                {acumuladoAnterior.meses_encontrados.map((m) => MESES[m - 1].toLowerCase()).join(', ')}
                {' '}cargados automáticamente desde tu historial.
              </div>
            </div>
          )}
          {!loadingAcumulado && acumuladoAnterior && acumuladoAnterior.meses_faltantes.length > 0 && acumuladoAnterior.meses_encontrados.length > 0 && (
            <div style={{
              padding: '12px 16px', borderRadius: 'var(--radius-md)',
              background: 'var(--warning-bg)', border: '1px solid var(--warning-border)',
              display: 'flex', alignItems: 'flex-start', gap: 10,
            }}>
              <AlertCircle size={16} color="var(--warning)" style={{ flexShrink: 0, marginTop: 2 }} />
              <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                Faltan pre-declaraciones de{' '}
                <strong style={{ color: 'var(--text-primary)' }}>
                  {acumuladoAnterior.meses_faltantes.map((m) => MESES[m - 1].toLowerCase()).join(', ')}
                </strong>.
                El cálculo será parcial. Calcula esos meses primero para mayor precisión.
              </div>
            </div>
          )}
          {!loadingAcumulado && (!acumuladoAnterior || acumuladoAnterior.meses_encontrados.length === 0) && (
            <div style={{
              padding: '12px 16px', borderRadius: 'var(--radius-md)',
              background: 'var(--warning-bg)', border: '1px solid var(--warning-border)',
              display: 'flex', alignItems: 'flex-start', gap: 10,
            }}>
              <AlertCircle size={16} color="var(--warning)" style={{ flexShrink: 0, marginTop: 2 }} />
              <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                No se encontraron declaraciones anteriores de este ejercicio.
                Se calculará solo con datos de este mes (tabla simple).
              </div>
            </div>
          )}
        </>
      )}

      {/* Periodo selector + calcular */}
      <div className="card" style={{ display: 'flex', alignItems: 'flex-end', gap: 16, flexWrap: 'wrap' }}>
        <div>
          <label style={labelStyle}>Año</label>
          <select className="input-field" value={year} onChange={(e) => agent.setPeriodo(Number(e.target.value), month)} style={{ width: 120, cursor: 'pointer' }}>
            {YEARS.map((y) => <option key={y} value={y}>{y}</option>)}
          </select>
        </div>
        <div>
          <label style={labelStyle}>Mes</label>
          <select className="input-field" value={month} onChange={(e) => agent.setPeriodo(year, Number(e.target.value))} style={{ width: 160, cursor: 'pointer' }}>
            {MESES.map((m, i) => <option key={i} value={i + 1}>{m}</option>)}
          </select>
        </div>
        {esEmpresarialOArr && month > 1 && (
          <div style={{ minWidth: 220 }}>
            <label style={labelStyle}>ISR pagado en meses anteriores</label>
            {loadingPagos ? (
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '12px', fontSize: '0.82rem', color: 'var(--text-muted)' }}>
                <Loader size={14} className="spin" /> Consultando historial…
              </div>
            ) : modoManual ? (
              <>
                <input type="number" className="input-field" value={pagosAnteriores || ''} onChange={(e) => setPagosAnteriores(Number(e.target.value) || 0)} placeholder="0.00" min={0} step={0.01} style={{ width: 180 }} />
                <button onClick={() => { setModoManual(false); if (pagosAnterioresAuto !== null) setPagosAnteriores(pagosAnterioresAuto); }}
                  style={{ background: 'none', border: 'none', color: 'var(--purple-light)', fontSize: '0.75rem', cursor: 'pointer', padding: 0, marginTop: 4, display: 'block' }}>
                  Usar automático
                </button>
              </>
            ) : (
              <div style={{ background: 'var(--success-bg)', border: '1px solid var(--success-border)', borderRadius: 'var(--radius-md)', padding: 12 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <CheckCircle size={16} color="var(--success)" />
                  <span style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 600, fontSize: '0.95rem', color: 'var(--text-primary)' }}>
                    ${pagosAnteriores.toLocaleString('es-MX', { minimumFractionDigits: 2 })}
                  </span>
                </div>
                <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', display: 'block', marginTop: 4 }}>
                  {pagosAnterioresAuto === 0 ? 'Sin pagos anteriores registrados' : 'Calculado desde tu historial'}
                </span>
                <button onClick={() => setModoManual(true)}
                  style={{ background: 'none', border: 'none', color: 'var(--purple-light)', fontSize: '0.75rem', cursor: 'pointer', padding: 0, marginTop: 4 }}>
                  Editar manualmente
                </button>
              </div>
            )}
          </div>
        )}
        {esArrendamiento && (
          <div style={{ flexBasis: '100%' }}>
            <div style={{ background: 'var(--teal-bg-subtle)', border: '1px solid var(--border-hover)', borderRadius: 'var(--radius-md)', padding: 12 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, cursor: 'pointer' }}
                onClick={() => { setIncluyePredial(prev => { if (prev) setPredialPagado(0); return !prev; }); }}>
                <div style={{
                  width: 40, height: 22, borderRadius: 11, position: 'relative',
                  background: incluyePredial ? 'var(--success)' : 'var(--text-muted)', transition: 'background 0.2s', flexShrink: 0,
                }}>
                  <div style={{ width: 18, height: 18, borderRadius: '50%', background: '#fff', position: 'absolute', top: 2, left: incluyePredial ? 20 : 2, transition: 'left 0.2s' }} />
                </div>
                <span style={{ fontSize: '0.85rem', fontWeight: 500, color: 'var(--text-primary)' }}>¿Pagaste impuesto predial este periodo?</span>
              </div>
              <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: 6, marginBottom: 0, lineHeight: 1.5 }}>
                El predial es el impuesto municipal por ser dueño del inmueble que rentas. Es el único gasto que se puede sumar a la deducción ciega del 35%.
              </p>
            </div>
            {incluyePredial && (
              <div style={{ marginTop: 12 }}>
                <label style={labelStyle}>Monto del predial pagado</label>
                <input type="number" className="input-field" value={predialPagado || ''} onChange={(e) => setPredialPagado(Number(e.target.value) || 0)} placeholder="Ej: 1,500.00" min={0} step={0.01} style={{ width: 200 }} />
                <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', display: 'block', marginTop: 4 }}>Monto total del predial pagado en este mes/bimestre</span>
              </div>
            )}
          </div>
        )}
        <button className="btn-primary" onClick={handleCalcular} disabled={loading}
          style={{ display: 'inline-flex', alignItems: 'center', gap: 8, opacity: loading ? 0.7 : 1 }}>
          {loading ? <Loader size={16} className="spin" /> : null}
          {loading ? 'Calculando...' : 'Calcular pre-declaración'}
        </button>
      </div>

      {error && <ErrorAlert message={error} />}
    </div>
  );
}
