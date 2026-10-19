/**
 * Una calculadora fiscal (P3-08): formulario, botón y resultado con desglose.
 * No calcula nada: manda los datos al motor y pinta lo que devuelve.
 */

import { useState } from 'react';
import { Calculator, Loader } from 'lucide-react';
import { calcular, type ResultadoCalculadora } from '../../services/impuestosApi';
import { cuerpoDe, type DefinicionCalculadora } from './definiciones';
import AvisoPorConfirmar from '../fiscalito/AvisoPorConfirmar';
import { fuentesPorConfirmar } from '../fiscalito/porConfirmar';

const ETIQUETA: React.CSSProperties = {
  display: 'flex', flexDirection: 'column', gap: 4, fontSize: '0.78rem',
  color: 'var(--text-secondary)',
};

function texto(v: unknown): string {
  if (v === null || v === undefined) return '—';
  if (typeof v === 'boolean') return v ? 'Sí' : 'No';
  return String(v);
}

export default function TarjetaCalculadora({ def }: { def: DefinicionCalculadora }) {
  const [valores, setValores] = useState<Record<string, string>>(
    () => Object.fromEntries(def.campos.map((c) => [c.id, c.defecto])),
  );
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [resultado, setResultado] = useState<ResultadoCalculadora | null>(null);

  const enviar = async (e: React.FormEvent) => {
    e.preventDefault();
    setCargando(true);
    setError(null);
    try {
      setResultado(await calcular(def.id, cuerpoDe(def, valores)));
    } catch (err) {
      setResultado(null);
      setError(err instanceof Error ? err.message : 'No se pudo calcular.');
    } finally {
      setCargando(false);
    }
  };

  const notas = Array.isArray(resultado?.notas) ? (resultado?.notas as string[]) : [];

  return (
    <section className="card" aria-label={def.titulo} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div>
        <h2 style={{ fontSize: '1rem', fontWeight: 700, margin: 0 }}>{def.titulo}</h2>
        <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', margin: '4px 0 0' }}>{def.descripcion}</p>
      </div>
      <form onSubmit={enviar} style={{ display: 'grid', gap: 8, gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))' }}>
        {def.campos.map((c) => (
          <label key={c.id} style={ETIQUETA}>
            {c.etiqueta}
            {c.tipo === 'opcion' ? (
              <select className="input-field" value={valores[c.id]}
                onChange={(e) => setValores({ ...valores, [c.id]: e.target.value })}>
                {c.opciones?.map((o) => <option key={o.valor} value={o.valor}>{o.etiqueta}</option>)}
              </select>
            ) : c.tipo === 'casilla' ? (
              <input type="checkbox" checked={valores[c.id] === 'true'}
                onChange={(e) => setValores({ ...valores, [c.id]: String(e.target.checked) })} />
            ) : (
              <input className="input-field"
                type={c.tipo === 'fecha' ? 'date' : c.tipo === 'texto' ? 'text' : 'number'}
                step={c.tipo === 'dinero' ? '0.01' : undefined} min={c.tipo === 'texto' || c.tipo === 'fecha' ? undefined : 0}
                value={valores[c.id]}
                onChange={(e) => setValores({ ...valores, [c.id]: e.target.value })} />
            )}
          </label>
        ))}
        <button className="btn-primary" type="submit" disabled={cargando}
          style={{ alignSelf: 'end', display: 'flex', alignItems: 'center', gap: 6, justifyContent: 'center' }}>
          {cargando ? <Loader size={14} className="spin" /> : <Calculator size={14} />} Calcular
        </button>
      </form>
      {error && <p role="alert" style={{ color: 'var(--danger)', fontSize: '0.82rem', margin: 0 }}>{error}</p>}
      {resultado && (
        <dl style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '4px 12px', margin: 0, fontSize: '0.85rem' }}>
          {def.salidas.map((s) => (
            <div key={s.id} style={{ display: 'contents' }}>
              <dt style={{ color: 'var(--text-secondary)' }}>{s.etiqueta}</dt>
              <dd style={{
                margin: 0, fontFamily: 'JetBrains Mono, monospace', textAlign: 'right',
                fontWeight: s.principal ? 700 : 400,
                color: s.principal ? 'var(--teal-light)' : 'var(--text-primary)',
              }} data-salida={s.id}>{texto(resultado[s.id])}</dd>
            </div>
          ))}
        </dl>
      )}
      <AvisoPorConfirmar fuentes={fuentesPorConfirmar(resultado)} />
      {notas.length > 0 && (
        <ul style={{ margin: 0, paddingLeft: 18, fontSize: '0.75rem', color: 'var(--warning)' }}>
          {notas.map((n) => <li key={n}>{n}</li>)}
        </ul>
      )}
      {resultado && typeof resultado.fundamento === 'string' && (
        <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)', margin: 0 }}>{resultado.fundamento}</p>
      )}
    </section>
  );
}
