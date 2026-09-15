/** Tab para generar la declaración DIOT */

import { useState } from 'react';
import { useProfile } from '../../context/ProfileContext';
import { useAuth } from '../../context/AuthContext';
import { generarDIOT, type CFDI, type DIOTResponse, tipoParaApi, facturasFiscales } from '../../services/fiscalAgentApi';
import { guardarDIOT } from '../../services/declaracionesHistory';
import { exportarDIOTPDF } from '../../services/pdfExportDIOT';
import { generarDIOTBatch, DIOT_BATCH_POR_VALIDAR } from '../../services/exportadores/diot';
import { descargarBytes } from '../../services/exportadores/descargar';
import { fmtMoney } from '../../utils/format';
import { thStyle, tdStyle, tdMonoStyle } from '../../utils/styles';
import XMLUploader from './XMLUploader';
import PeriodSelector from './PeriodSelector';
import ErrorAlert from '../common/ErrorAlert';
import SuccessNotice from '../common/SuccessNotice';
import { Loader, Download, RefreshCw, MessageSquare, AlertTriangle, FileDown } from 'lucide-react';

export default function DIOTTab() {
  const { profile } = useProfile();
  const { user } = useAuth();
  const [facturas, setFacturas] = useState<CFDI[]>([]);
  const [year, setYear] = useState(2025);
  const [month, setMonth] = useState(new Date().getMonth() + 1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [resultado, setResultado] = useState<DIOTResponse | null>(null);
  const [guardado, setGuardado] = useState(false);
  const [errorTxt, setErrorTxt] = useState('');
  const [transliterados, setTransliterados] = useState<string[]>([]);

  const handleGenerar = async () => {
    if (facturas.length === 0) { setError('Sube al menos una factura XML.'); return; }
    if (!profile.rfc || !profile.regimen) { setError('Completa tu RFC y régimen en tu perfil.'); return; }
    setLoading(true);
    setError('');
    setGuardado(false);
    try {
      const res = await generarDIOT({
        contribuyente: { rfc: profile.rfc, regimen: profile.regimen, contributor_type: tipoParaApi(profile.contributorType) },
        facturas: facturasFiscales(facturas), periodo_year: year, periodo_month: month, incluir_explicacion: true,
      });
      setResultado(res);
      if (user?.uid) {
        guardarDIOT(user.uid, res, facturas.length)
          .then(() => setGuardado(true))
          .catch(() => { /* silent */ });
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error inesperado');
    } finally {
      setLoading(false);
    }
  };

  /**
   * El .txt de carga batch. Se arma en el momento y no se guarda en el
   * historial: el historial guarda el RESULTADO del calculo, y este archivo es
   * una serializacion de ese mismo resultado con un layout que todavia puede
   * cambiar. Guardarlo congelaria el layout sin validar.
   */
  const descargarTxt = (data: DIOTResponse) => {
    setErrorTxt('');
    try {
      const archivo = generarDIOTBatch(data);
      setTransliterados(archivo.transliterados);
      descargarBytes(archivo.nombre, archivo.bytes);
    } catch (e) {
      setErrorTxt(e instanceof Error ? e.message : 'No se pudo generar el archivo.');
    }
  };

  if (resultado) {
    return (
      <div className="animate-in" style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
        {guardado && <SuccessNotice />}
        <div className="card" style={{ textAlign: 'center', background: 'linear-gradient(135deg, var(--purple-bg), var(--purple-bg-subtle))', border: '1px solid var(--border-hover)' }}>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 8 }}>
            DIOT — {resultado.periodo}
          </div>
          <div style={{ fontSize: '1.6rem', fontWeight: 800, fontFamily: "'JetBrains Mono', monospace" }}>
            {resultado.proveedores.length} proveedor{resultado.proveedores.length !== 1 ? 'es' : ''}
          </div>
        </div>

        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border)' }}>
                  {['RFC Proveedor', 'Nombre', 'Total operaciones', 'IVA pagado', '# Facturas'].map((h) => (
                    <th key={h} style={thStyle}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {resultado.proveedores.map((p, i) => (
                  <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                    <td style={{ ...tdStyle, fontFamily: "'JetBrains Mono', monospace", fontSize: '0.78rem' }}>{p.rfc}</td>
                    <td style={tdStyle}>{p.nombre}</td>
                    <td style={tdMonoStyle}>{fmtMoney(p.total_operaciones)}</td>
                    <td style={tdMonoStyle}>{fmtMoney(p.iva_pagado)}</td>
                    <td style={{ ...tdStyle, textAlign: 'center' }}>{p.cantidad_facturas}</td>
                  </tr>
                ))}
                <tr style={{ background: 'var(--teal-bg-subtle)' }}>
                  <td style={{ ...tdStyle, fontWeight: 700 }} colSpan={2}>Totales</td>
                  <td style={{ ...tdMonoStyle, fontWeight: 700 }}>{fmtMoney(resultado.total_operaciones)}</td>
                  <td style={{ ...tdMonoStyle, fontWeight: 700 }}>{fmtMoney(resultado.total_iva)}</td>
                  <td style={{ ...tdStyle, textAlign: 'center', fontWeight: 700 }}>{resultado.total_proveedores}</td>
                </tr>
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

        {/*
          * La advertencia va ARRIBA del boton, no debajo: quien esta a punto de
          * bajar un archivo para subirlo al portal del SAT tiene que leer que el
          * layout no esta validado ANTES de hacer clic. Mismo criterio que
          * `SelectorExportacion` con los formatos `por-validar`.
          */}
        <div className="card" style={{ background: 'var(--bg-card-hover)', border: '1px solid var(--border)' }}>
          <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
            <AlertTriangle size={16} color="var(--warning)" style={{ flexShrink: 0, marginTop: 2 }} />
            <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
              {DIOT_BATCH_POR_VALIDAR}
            </p>
          </div>
          {errorTxt && (
            <p style={{ fontSize: '0.8rem', color: 'var(--danger)', marginTop: 10 }}>{errorTxt}</p>
          )}
          {transliterados.length > 0 && (
            <p style={{ fontSize: '0.8rem', color: 'var(--warning)', marginTop: 10 }}>
              RFC transliterados a ASCII: {transliterados.join(', ')}
            </p>
          )}
        </div>

        <div style={{ display: 'flex', justifyContent: 'center', gap: 12, flexWrap: 'wrap' }}>
          <button className="btn-primary" onClick={() => exportarDIOTPDF(resultado, { nombre: profile.nombre, rfc: profile.rfc })}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
            <Download size={16} /> Descargar PDF
          </button>
          <button className="btn-secondary" onClick={() => descargarTxt(resultado)}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
            <FileDown size={16} /> Descargar DIOT (.txt)
          </button>
          <button className="btn-secondary" onClick={() => setResultado(null)}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
            <RefreshCw size={16} /> Nueva consulta
          </button>
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div className="card">
        <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: 6 }}>Declaración DIOT</h3>
        <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: 16 }}>
          Genera tu Declaración Informativa de Operaciones con Terceros.
        </p>
        <XMLUploader facturas={facturas} onChange={setFacturas} />
      </div>
      <div className="card" style={{ display: 'flex', alignItems: 'flex-end', gap: 16, flexWrap: 'wrap' }}>
        <PeriodSelector year={year} month={month} onYearChange={setYear} onMonthChange={setMonth} />
        <button className="btn-primary" onClick={handleGenerar} disabled={loading}
          style={{ display: 'inline-flex', alignItems: 'center', gap: 8, opacity: loading ? 0.7 : 1 }}>
          {loading ? <Loader size={16} className="spin" /> : null}
          {loading ? 'Generando...' : 'Generar DIOT'}
        </button>
      </div>
      {error && <ErrorAlert message={error} />}
    </div>
  );
}
