/**
 * Reporte de conciliación al corte (P2-06): saldo según el banco y según
 * libros, partidas en tránsito y diferencia. Todo lo calcula el backend; aquí
 * sólo se pinta y se descarga el XLSX.
 */

import { useEffect, useState } from 'react';
import { CheckCircle2, Download, Loader, XCircle } from 'lucide-react';
import { descargarReporte, obtenerReporte, type ReporteConciliacion as Reporte } from '../../services/conciliacionApi';
import ErrorAlert from '../common/ErrorAlert';
import { descargarBlob, dinero, mensaje } from './comun';
import { tdMonoStyle, tdStyle } from '../../utils/styles';

interface Props { clave: string; cuentaId: number; corte: string }

const SECCIONES: [keyof Reporte, string][] = [
  ['depositos_en_transito', '(+) Depósitos en libros que el banco no refleja'],
  ['retiros_en_transito', '(−) Retiros en libros que el banco no refleja'],
  ['abonos_banco_no_registrados', '(+) Abonos del banco no registrados en libros'],
  ['cargos_banco_no_registrados', '(−) Cargos del banco no registrados en libros'],
];

export default function ReporteConciliacion({ clave, cuentaId, corte }: Props) {
  const [r, setR] = useState<Reporte | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [bajando, setBajando] = useState(false);

  useEffect(() => {
    let vivo = true;
    obtenerReporte(clave, cuentaId, corte)
      .then((x) => { if (vivo) { setR(x.reporte); setError(null); } })
      .catch((e: unknown) => { if (vivo) setError(mensaje(e, 'No se pudo armar el reporte.')); });
    return () => { vivo = false; };
  }, [clave, cuentaId, corte]);

  const bajar = async () => {
    setBajando(true);
    try { descargarBlob(`conciliacion-${corte}.xlsx`, await descargarReporte(clave, cuentaId, corte)); }
    catch (e) { setError(mensaje(e, 'No se pudo descargar el reporte.')); }
    finally { setBajando(false); }
  };

  if (error) return <ErrorAlert message={error} />;
  if (!r) return <Loader size={16} className="spin" />;
  const fila = (t: string, v: string, fuerte = false) => (
    <tr style={{ fontWeight: fuerte ? 700 : 400 }}><td style={tdStyle}>{t}</td><td style={tdMonoStyle}>{dinero(v, '0.00')}</td></tr>
  );
  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <strong style={{ fontSize: '0.9rem' }}>Conciliación al {r.corte}</strong>
        <span role="status" style={{ display: 'inline-flex', gap: 4, alignItems: 'center', fontSize: '0.82rem',
          color: r.cuadra ? 'var(--success)' : 'var(--danger)' }}>
          {r.cuadra ? <CheckCircle2 size={14} /> : <XCircle size={14} />}
          {r.cuadra ? 'Cuadra' : `Diferencia ${r.diferencia}`}
        </span>
        <span style={{ flex: 1 }} />
        <button type="button" className="btn-secondary" onClick={bajar} disabled={bajando}>
          {bajando ? <Loader size={14} className="spin" /> : <Download size={14} />} Excel
        </button>
      </div>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem' }}>
        <tbody>
          {fila('Saldo según el banco', r.saldo_banco, true)}
          {SECCIONES.slice(0, 2).map(([k, t]) => fila(t, r.totales[k as string]))}
          {fila('Saldo del banco conciliado', r.saldo_banco_conciliado, true)}
          {fila('Saldo según libros', r.saldo_libros, true)}
          {SECCIONES.slice(2).map(([k, t]) => fila(t, r.totales[k as string]))}
          {fila('Saldo de libros conciliado', r.saldo_libros_conciliado, true)}
        </tbody>
      </table>
      {r.advertencias.map((a) => <div key={a} style={{ fontSize: '0.8rem', color: 'var(--warning)' }}>{a}</div>)}
    </div>
  );
}
