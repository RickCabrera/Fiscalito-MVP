/**
 * Tab Catálogo de Contabilito (P2-01): el catálogo de cuentas del CLIENTE, en
 * árbol, con su código agrupador del SAT (Anexo 24) y la naturaleza de cada
 * cuenta. Se siembra el catálogo base, se agregan subcuentas, se renombra y se
 * borra (el backend rechaza borrar una cuenta con movimientos o subcuentas, y
 * el motivo se enseña tal cual).
 */

import { useEffect, useMemo, useState } from 'react';
import { BookOpen, Loader, Plus, Sprout, Trash2 } from 'lucide-react';
import {
  borrarCuenta, editarCuenta, listarCuentas, obtenerAgrupador, sembrarCatalogo,
  type CodigoAgrupador, type Cuenta,
} from '../../services/contabilidadApi';
import ErrorAlert from '../common/ErrorAlert';
import FormCuenta from './FormCuenta';
import { ETIQUETA_TIPO_CUENTA, enArbol, mensaje } from './comun';
import { tdStyle, thStyle } from '../../utils/styles';

interface Props {
  clave: string;
}

export default function CatalogoCuentas({ clave }: Props) {
  const [cuentas, setCuentas] = useState<Cuenta[] | null>(null);
  const [agrupador, setAgrupador] = useState<CodigoAgrupador[]>([]);
  const [fuente, setFuente] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const [nuevaBajo, setNuevaBajo] = useState<Cuenta | null | undefined>(undefined);
  const [editando, setEditando] = useState<{ id: number; nombre: string } | null>(null);

  const [recarga, setRecarga] = useState(0);
  const cargar = () => setRecarga((n) => n + 1);

  useEffect(() => {
    let vivo = true;
    listarCuentas(clave)
      .then((r) => { if (vivo) { setCuentas(r.cuentas); setError(null); } })
      .catch((e: unknown) => { if (vivo) setError(mensaje(e, 'No se pudo cargar el catálogo.')); });
    return () => { vivo = false; };
  }, [clave, recarga]);

  useEffect(() => {
    obtenerAgrupador()
      .then((r) => { setAgrupador(r.codigos); setFuente(r.fuente); })
      .catch(() => undefined);
  }, []);

  const nombres = useMemo(() => new Map(agrupador.map((c) => [c.codigo, c.nombre])), [agrupador]);
  const arbol = useMemo(() => enArbol(cuentas ?? []), [cuentas]);

  async function accion(fn: () => Promise<unknown>, falla: string) {
    setOcupado(true);
    setError(null);
    try {
      await fn();
      cargar();
    } catch (e) {
      setError(mensaje(e, falla));
    } finally {
      setOcupado(false);
    }
  }

  if (cuentas === null && !error) {
    return <div className="card"><Loader size={16} className="spin" /> Cargando catálogo…</div>;
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
      {error && <ErrorAlert message={error} />}
      <div className="card" style={{ display: 'flex', gap: 'var(--space-md)', flexWrap: 'wrap', alignItems: 'center' }}>
        <BookOpen size={18} />
        <div style={{ flex: 1, minWidth: 240 }}>
          <strong>{cuentas?.length ?? 0} cuentas</strong>
          <p style={{ margin: 0, fontSize: '0.78rem', color: 'var(--text-muted)' }}>
            Código agrupador: {fuente || 'Anexo 24 de la RMF'}
          </p>
        </div>
        <button type="button" className="btn-secondary" disabled={ocupado}
          onClick={() => void accion(() => sembrarCatalogo(clave), 'No se pudo sembrar el catálogo.')}>
          <Sprout size={14} /> {cuentas?.length ? 'Completar catálogo base' : 'Sembrar catálogo base'}
        </button>
        <button type="button" className="btn-primary" disabled={ocupado} onClick={() => setNuevaBajo(null)}>
          <Plus size={14} /> Cuenta de mayor
        </button>
      </div>

      {nuevaBajo !== undefined && (
        <FormCuenta
          clave={clave}
          padre={nuevaBajo}
          agrupador={agrupador}
          onListo={() => { setNuevaBajo(undefined); cargar(); }}
          onCancelar={() => setNuevaBajo(undefined)}
        />
      )}

      {cuentas?.length === 0 ? (
        <div className="card" style={{ color: 'var(--text-secondary)' }}>
          Este cliente no tiene catálogo. Siembra el catálogo base: trae las cuentas que usan
          las pólizas automáticas (bancos, clientes, IVA cobrado y pendiente, retenciones…),
          cada una ligada a su código agrupador.
        </div>
      ) : (
        <div className="card" style={{ padding: 0, overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.84rem' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                <th style={thStyle}>Cuenta</th>
                <th style={thStyle}>Nombre</th>
                <th style={thStyle}>Agrupador SAT</th>
                <th style={thStyle}>Tipo</th>
                <th style={thStyle}>Naturaleza</th>
                <th style={thStyle}>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {arbol.map((c) => (
                <tr key={c.id} style={{ borderBottom: '1px solid var(--border)' }}>
                  <td style={{ ...tdStyle, fontFamily: "'JetBrains Mono', monospace", paddingLeft: 14 + (c.nivel - 1) * 18 }}>
                    {c.numero}
                  </td>
                  <td style={{ ...tdStyle, color: c.afectable ? 'var(--text-secondary)' : 'var(--text-primary)', fontWeight: c.afectable ? 400 : 600 }}>
                    {editando?.id === c.id ? (
                      <form onSubmit={(e) => {
                        e.preventDefault();
                        const nombre = editando.nombre;
                        setEditando(null);
                        void accion(() => editarCuenta(clave, c.id, { nombre }), 'No se pudo renombrar.');
                      }}>
                        <input className="input-field" aria-label={`Nombre de ${c.numero}`} value={editando.nombre}
                          autoFocus onChange={(e) => setEditando({ id: c.id, nombre: e.target.value })}
                          onBlur={() => setEditando(null)} />
                      </form>
                    ) : (
                      <button type="button" onClick={() => setEditando({ id: c.id, nombre: c.nombre })}
                        title="Renombrar" style={{ background: 'none', border: 'none', color: 'inherit', font: 'inherit', cursor: 'text', padding: 0, textAlign: 'left' }}>
                        {c.nombre}
                      </button>
                    )}
                  </td>
                  <td style={tdStyle} title={nombres.get(c.codigo_agrupador) ?? ''}>
                    <span style={{ fontFamily: "'JetBrains Mono', monospace" }}>{c.codigo_agrupador}</span>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginLeft: 6 }}>
                      {nombres.get(c.codigo_agrupador) ?? ''}
                    </span>
                  </td>
                  <td style={tdStyle}>{ETIQUETA_TIPO_CUENTA[c.tipo] ?? c.tipo}</td>
                  <td style={tdStyle}>{c.naturaleza === 'deudora' ? 'Deudora' : 'Acreedora'}</td>
                  <td style={{ ...tdStyle, whiteSpace: 'nowrap' }}>
                    <button type="button" className="btn-secondary" style={{ padding: '3px 8px' }}
                      aria-label={`Agregar subcuenta a ${c.numero}`} disabled={ocupado}
                      onClick={() => setNuevaBajo(c)}><Plus size={13} /></button>{' '}
                    <button type="button" className="btn-secondary" style={{ padding: '3px 8px' }}
                      aria-label={`Borrar ${c.numero}`} disabled={ocupado}
                      onClick={() => {
                        if (window.confirm(`¿Borrar la cuenta ${c.numero} ${c.nombre}?`)) {
                          void accion(() => borrarCuenta(clave, c.id), 'No se pudo borrar la cuenta.');
                        }
                      }}><Trash2 size={13} /></button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
