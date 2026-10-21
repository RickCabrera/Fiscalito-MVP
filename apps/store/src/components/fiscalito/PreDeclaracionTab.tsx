/**
 * Tab de pre-declaración: facturas del mes (de la bóveda del cliente o de archivos
 * sueltos, P1-06), tabla y cálculo.
 */

import { useState, useEffect } from 'react';
import { usePerfilFiscal } from '../../context/usePerfilFiscal';
import { contribuyenteParaApi, mensajeFalta } from '../../context/perfilFiscal';
import { useAuth } from '../../context/AuthContext';
import { calcularPreDeclaracion } from '../../services/fiscalAgentApi';
import { guardarDeclaracion, obtenerAcumuladoAnterior, desgloseRecordDesde } from '../../services/declaracionesHistory';
import { useAgent } from '../../agent/AgentContext';
import { labelStyle } from '../../utils/styles';
import ErrorAlert from '../common/ErrorAlert';
import SuccessNotice from '../common/SuccessNotice';
import FacturaTable from './FacturaTable';
import ResultadoDeclaracion from './ResultadoDeclaracion';
import FaltaDatoFiscal from './FaltaDatoFiscal';
import FuenteFacturasPanel from './FuenteFacturasPanel';
import AvisoAcumulado106, { type Acumulado106 } from './AvisoAcumulado106';
import { useFuenteFacturas } from './useFuenteFacturas';
import { Loader, CheckCircle } from 'lucide-react';

const MESES = [
  'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
  'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre',
];
const YEARS = [2026, 2025, 2024, 2023];

export default function PreDeclaracionTab() {
  const perfil = usePerfilFiscal();
  const { user } = useAuth();
  const agent = useAgent();

  const facturas = agent.facturas;
  const resultado = agent.resultado;
  const year = agent.periodoYear;
  const month = agent.periodoMonth;

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [guardado, setGuardado] = useState(false);
  const [pagosAnteriores, setPagosAnteriores] = useState(0);
  const [pagosAutoCargados, setPagosAnterioresAuto] = useState<number | null>(null);
  const [modoManual, setModoManual] = useState(false);
  const [predialPagado, setPredialPagado] = useState(0);
  const [incluyePredial, setIncluyePredial] = useState(false);
  const [acumuladoCargado, setAcumuladoAnterior] = useState<Acumulado106 | null>(null);
  // Consulta del acumulado que ya respondió; "cargando" = la vigente aún no.
  const [consultaResuelta, setConsultaResuelta] = useState<string | null>(null);

  // P1-06: por defecto, los CFDI del mes salen de la bóveda del cliente activo. Si el
  // asistente ya cargó XML (demo), se arranca en archivos sueltos para no esconderlos.
  const fuente = useFuenteFacturas({
    clave: perfil.clienteId, anio: year, mes: month, manual: facturas,
    conRelacionados: true, preferirArchivos: facturas.length > 0,
  });

  const esArrendamiento = perfil.regimen === '606';
  const esEmpresarialOArr = ['612', '606'].includes(perfil.regimen);

  // El acumulado del Art. 106 sólo aplica a 612/606 desde febrero y con sesión;
  // fuera de eso se deriva `null` en el render en vez de borrarlo en el efecto.
  const aplicaAcumulado = esEmpresarialOArr && month > 1 && !!user?.uid;
  const acumuladoAnterior = aplicaAcumulado ? acumuladoCargado : null;
  const pagosAnterioresAuto = aplicaAcumulado ? pagosAutoCargados : null;
  const consultaVigente = aplicaAcumulado
    ? `${year}|${month}|${user?.uid}|${perfil.clienteId ?? ''}|${modoManual}`
    : null;
  const loadingAcumulado = consultaVigente !== null && consultaResuelta !== consultaVigente;
  const loadingPagos = loadingAcumulado;

  useEffect(() => {
    if (!esEmpresarialOArr || month <= 1 || !user?.uid) return;
    let cancelled = false;
    const consulta = `${year}|${month}|${user.uid}|${perfil.clienteId ?? ''}|${modoManual}`;
    obtenerAcumuladoAnterior(user.uid, year, month, perfil.clienteId)
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
        if (!cancelled) setConsultaResuelta(consulta);
      });
    return () => { cancelled = true; };
  }, [year, month, user?.uid, esEmpresarialOArr, modoManual, perfil.clienteId]);

  const removeCFDI = (uuid: string) => {
    agent.setFacturas(agent.facturas.filter((f) => f.uuid !== uuid));
  };

  const handleCalcular = async () => {
    if (fuente.paraCalcular.length === 0) { setError(fuente.motivoVacio); return; }
    if (perfil.falta) { setError(mensajeFalta(perfil.falta)); return; }
    setLoading(true);
    setError('');
    setGuardado(false);
    try {
      const res = await calcularPreDeclaracion({
        contribuyente: contribuyenteParaApi(perfil),
        facturas: fuente.paraCalcular,
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
          desglose: desgloseRecordDesde(res.desglose),
          explicacion: res.explicacion ?? null,
          advertencias: res.advertencias ?? [], recomendaciones: res.recomendaciones ?? [],
          facturas_count: fuente.delPeriodo.length,
        }, 'predeclaracion', perfil.clienteId).then(() => setGuardado(true)).catch(() => { /* silent */ });
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
    setError('');
  };

  // C-02: un cliente sin RFC (o sin régimen) no llega a cargar XML: se le pide aquí.
  if (perfil.sujeto === 'cliente' && perfil.falta) return <FaltaDatoFiscal perfil={perfil} />;
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
      <div className="card">
        <FuenteFacturasPanel fuente={fuente} clave={perfil.clienteId} manual={facturas} onManual={agent.setFacturas} />
      </div>

      <FacturaTable facturas={fuente.delPeriodo} onRemove={fuente.modo === 'archivos' ? removeCFDI : undefined} />

      {/* Estado del acumulado Art. 106 LISR (612/606 con mes > 1) */}
      {esEmpresarialOArr && month > 1 && (
        <AvisoAcumulado106 cargando={loadingAcumulado} acumulado={acumuladoAnterior} />
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
