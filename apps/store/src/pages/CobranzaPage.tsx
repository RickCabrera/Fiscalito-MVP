/**
 * Cuentas por cobrar del despacho (P5-03) — `/app/cobranza`.
 *
 * Qué le debe cada cliente y desde cuándo: saldo, vencido y antigüedad (0-30, 31-60, 61-90,
 * +90 días desde la fecha del cargo). Al elegir un cliente (`?cliente=`, así entra el
 * dashboard) se abre su estado de cuenta. Todo lo calcula el backend; aquí sólo se pinta.
 * Sólo dueño y contador: al auxiliar el backend le responde 403 y se le dice.
 */

import { useCallback, useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Loader, RefreshCw, Wallet } from 'lucide-react';
import {
  generarIgualas, NOMBRE_TRAMO, pesos, resumenCobranza, type ResumenCobranza, type Tramo,
} from '../services/cobranzaApi';
import DetalleCliente from '../components/cobranza/DetalleCliente';
import ErrorAlert from '../components/common/ErrorAlert';

const TRAMOS = Object.keys(NOMBRE_TRAMO) as Tramo[];

export default function CobranzaPage() {
  const [params, setParams] = useSearchParams();
  const elegido = params.get('cliente') ?? '';
  const [resumen, setResumen] = useState<ResumenCobranza | null>(null);
  const [error, setError] = useState('');
  const [aviso, setAviso] = useState('');
  const [generando, setGenerando] = useState(false);

  const cargar = useCallback(() => {
    resumenCobranza().then((r) => { setError(''); setResumen(r); })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : 'No se pudo cargar la cobranza.'));
  }, []);
  useEffect(() => { cargar(); }, [cargar]);

  const generar = async () => {
    setGenerando(true);
    setError('');
    try {
      const r = await generarIgualas();
      setAviso(`${r.cargos} ${r.cargos === 1 ? 'iguala generada' : 'igualas generadas'} de ${r.periodo}.`);
      cargar();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudieron generar las igualas.');
    } finally {
      setGenerando(false);
    }
  };

  const elegir = (clave: string) => setParams(clave ? { cliente: clave } : {}, { replace: true });

  return (
    <div style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 16 }}>
      <h1 style={{ fontSize: '1.3rem', display: 'flex', alignItems: 'center', gap: 10 }}>
        <Wallet size={20} /> Cobranza del despacho
        <button className="btn-secondary" onClick={() => void generar()} disabled={generando}
          style={{ marginLeft: 'auto', display: 'inline-flex', gap: 6, alignItems: 'center' }}>
          {generando ? <Loader size={14} className="spin" /> : <RefreshCw size={14} />} Generar igualas del mes
        </button>
      </h1>
      {error && <ErrorAlert message={error} />}
      {aviso && <p role="status" style={{ color: 'var(--success)', fontSize: '0.85rem' }}>{aviso}</p>}
      {!resumen && !error && (
        <span style={{ display: 'flex', gap: 8, alignItems: 'center', color: 'var(--text-secondary)' }}>
          <Loader size={16} className="spin" /> Cargando…
        </span>
      )}
      {resumen && (
        <div className="card" style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', fontSize: '0.84rem', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ textAlign: 'left', color: 'var(--text-secondary)' }}>
                <th>Cliente</th><th>Iguala</th><th>Saldo</th><th>Vencido</th>
                {TRAMOS.map((t) => <th key={t}>{NOMBRE_TRAMO[t]}</th>)}<th>Debe desde</th>
              </tr>
            </thead>
            <tbody>
              {resumen.clientes.map((c) => (
                <tr key={c.cliente} style={{ borderTop: '1px solid var(--border)', cursor: 'pointer',
                  background: c.cliente === elegido ? 'var(--bg-card-hover)' : undefined }}
                  onClick={() => elegir(c.cliente)}>
                  <td><button className="btn-link" style={{ background: 'none', border: 'none', padding: 0,
                    color: 'var(--text-primary)', cursor: 'pointer' }}>{c.cliente_nombre || c.cliente}</button></td>
                  <td>{c.iguala_mensual ? pesos(c.iguala_mensual) : '—'}</td>
                  <td><b>{pesos(c.saldo)}</b></td>
                  <td style={{ color: Number(c.vencido) > 0 ? 'var(--danger)' : undefined }}>{pesos(c.vencido)}</td>
                  {TRAMOS.map((t) => <td key={t}>{Number(c.antiguedad[t]) ? pesos(c.antiguedad[t]) : ''}</td>)}
                  <td>{c.desde ?? ''}</td>
                </tr>
              ))}
              <tr style={{ borderTop: '2px solid var(--border)', fontWeight: 700 }}>
                <td>Total</td><td />
                <td>{pesos(resumen.totales.saldo)}</td><td>{pesos(resumen.totales.vencido)}</td>
                {TRAMOS.map((t) => <td key={t}>{pesos(resumen.totales.antiguedad[t])}</td>)}<td />
              </tr>
            </tbody>
          </table>
        </div>
      )}
      {elegido && (
        <div className="card">
          <DetalleCliente key={elegido} clave={elegido} onCambio={cargar} />
        </div>
      )}
    </div>
  );
}
