/**
 * Tab Balanza de Contabilito (P2-04): balanza de comprobación por periodo y
 * nivel, con saldos iniciales (de periodos anteriores + los capturados al
 * arrancar), cargos, abonos y saldo final, y la comprobación del cuadre que
 * calcula el backend. Clic en una cuenta → su auxiliar (`AuxiliarCuenta`) →
 * la póliza o el XML del CFDI.
 */

import { useEffect, useState } from 'react';
import { CheckCircle2, Loader, XCircle } from 'lucide-react';
import { obtenerBalanza, type Balanza, type FiltroBalanza, type RenglonBalanza } from '../../services/contabilidadApi';
import ErrorAlert from '../common/ErrorAlert';
import AuxiliarCuenta from './AuxiliarCuenta';
import SaldosIniciales from './SaldosIniciales';
import { dinero, mensaje, mesDe } from './comun';
import { labelStyle, tdMonoStyle, tdStyle, thStyle } from '../../utils/styles';

interface Props {
  clave: string;
  onAbrirPoliza: (id: number) => void;
}

const COLUMNAS: [keyof RenglonBalanza, string][] = [
  ['inicial_deudor', 'Inicial deudor'], ['inicial_acreedor', 'Inicial acreedor'],
  ['cargos', 'Cargos'], ['abonos', 'Abonos'],
  ['final_deudor', 'Final deudor'], ['final_acreedor', 'Final acreedor'],
];

export default function BalanzaCliente({ clave, onAbrirPoliza }: Props) {
  const [periodo, setPeriodo] = useState(mesDe());
  const [nivel, setNivel] = useState<number | null>(null);
  const [solo, setSolo] = useState<FiltroBalanza>('con_saldo_o_movimiento');
  const [balanza, setBalanza] = useState<Balanza | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cuenta, setCuenta] = useState<RenglonBalanza | null>(null);
  const [verSaldos, setVerSaldos] = useState(false);

  const [recarga, setRecarga] = useState(0);
  const llave = `${periodo.desde}|${periodo.hasta}|${nivel}|${solo}|${recarga}`;
  const [cargada, setCargada] = useState<string | null>(null);
  const cargando = cargada !== llave && !!periodo.desde && !!periodo.hasta;

  useEffect(() => {
    if (!periodo.desde || !periodo.hasta) return;
    let vivo = true;
    obtenerBalanza(clave, periodo.desde, periodo.hasta, nivel, solo)
      .then((b) => { if (vivo) { setBalanza(b); setError(null); setCargada(llave); } })
      .catch((e: unknown) => {
        if (vivo) { setError(mensaje(e, 'No se pudo calcular la balanza.')); setCargada(llave); }
      });
    return () => { vivo = false; };
  }, [clave, periodo, nivel, solo, llave]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
      <div className="card" style={{ display: 'flex', gap: 'var(--space-md)', flexWrap: 'wrap', alignItems: 'flex-end' }}>
        <label><span style={labelStyle}>Mes</span>
          <input className="input-field" type="month" value={periodo.desde.slice(0, 7)}
            onChange={(e) => e.target.value && setPeriodo(mesDe(`${e.target.value}-01`))} /></label>
        <label><span style={labelStyle}>Desde</span>
          <input className="input-field" type="date" value={periodo.desde}
            onChange={(e) => setPeriodo({ ...periodo, desde: e.target.value })} /></label>
        <label><span style={labelStyle}>Hasta</span>
          <input className="input-field" type="date" value={periodo.hasta}
            onChange={(e) => setPeriodo({ ...periodo, hasta: e.target.value })} /></label>
        <label><span style={labelStyle}>Nivel</span>
          <select className="input-field" value={nivel ?? ''} onChange={(e) => setNivel(e.target.value ? Number(e.target.value) : null)}>
            <option value="">Todos</option><option value="1">1 (mayor)</option><option value="2">2</option><option value="3">3</option>
          </select></label>
        <label><span style={labelStyle}>Cuentas</span>
          <select className="input-field" value={solo} onChange={(e) => setSolo(e.target.value as FiltroBalanza)}>
            <option value="con_saldo_o_movimiento">Con saldo o movimiento</option>
            <option value="con_movimiento">Sólo con movimiento</option>
            <option value="todas">Todas</option>
          </select></label>
        {cargando && <Loader size={16} className="spin" />}
        <span style={{ flex: 1 }} />
        <button type="button" className="btn-secondary" onClick={() => setVerSaldos(!verSaldos)}>
          {verSaldos ? 'Ocultar saldos iniciales' : 'Saldos iniciales'}
        </button>
      </div>

      {verSaldos && <SaldosIniciales clave={clave} onGuardado={() => setRecarga((n) => n + 1)} />}

      {error && <ErrorAlert message={error} />}

      {cuenta && (
        <AuxiliarCuenta clave={clave} cuenta={cuenta} desde={periodo.desde} hasta={periodo.hasta}
          onCerrar={() => setCuenta(null)} onAbrirPoliza={onAbrirPoliza} />
      )}

      {balanza && (
        <>
          <div role="status" style={{
            display: 'flex', gap: 8, alignItems: 'center', fontSize: '0.88rem',
            color: balanza.cuadra ? 'var(--success)' : 'var(--danger)',
          }}>
            {balanza.cuadra ? <CheckCircle2 size={16} /> : <XCircle size={16} />}
            {balanza.cuadra
              ? 'La balanza cuadra: cargos = abonos y los saldos suman cero.'
              : `La balanza NO cuadra · saldo inicial ${balanza.diferencias.saldo_inicial} · movimientos ${balanza.diferencias.movimientos} · saldo final ${balanza.diferencias.saldo_final}`}
          </div>
          {balanza.renglones.length === 0 ? (
            <div className="card" style={{ color: 'var(--text-secondary)' }}>
              Sin movimientos ni saldos en este periodo. Genera las pólizas del mes en el tab Pólizas.
            </div>
          ) : (
            <div className="card" style={{ padding: 0, overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border)' }}>
                    <th style={thStyle}>Cuenta</th><th style={thStyle}>Nombre</th>
                    {COLUMNAS.map(([k, t]) => <th key={k} style={{ ...thStyle, textAlign: 'right' }}>{t}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {balanza.renglones.map((r) => (
                    <tr key={r.cuenta_id} style={{ borderBottom: '1px solid var(--border)', fontWeight: r.nivel === 1 ? 600 : 400 }}>
                      <td style={{ ...tdStyle, paddingLeft: 14 + (r.nivel - 1) * 14, fontFamily: "'JetBrains Mono', monospace" }}>
                        <button type="button" onClick={() => setCuenta(r)} aria-label={`Auxiliar de ${r.numero}`}
                          style={{ background: 'none', border: 'none', color: 'var(--teal-light)', font: 'inherit', cursor: 'pointer', padding: 0 }}>
                          {r.numero}
                        </button>
                      </td>
                      <td style={tdStyle}>{r.nombre}</td>
                      {COLUMNAS.map(([k]) => <td key={k} style={tdMonoStyle}>{dinero(String(r[k]))}</td>)}
                    </tr>
                  ))}
                  <tr style={{ fontWeight: 700 }}>
                    <td style={tdStyle} colSpan={2}>Totales</td>
                    {COLUMNAS.map(([k]) => (
                      <td key={k} style={tdMonoStyle}>{dinero(balanza.totales[k as keyof Balanza['totales']], '0.00')}</td>
                    ))}
                  </tr>
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}
