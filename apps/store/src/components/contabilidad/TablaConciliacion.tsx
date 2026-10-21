/**
 * Una de las dos tablas de la conciliación (P2-06): movimientos del estado de
 * cuenta o de libros, con su marca de conciliado y casilla para la conciliación
 * manual. Pura: lo que pinta y lo que selecciona lo decide el padre.
 */

import { CheckCircle2, Circle } from 'lucide-react';
import { dinero } from './comun';
import { tdMonoStyle, tdStyle, thStyle } from '../../utils/styles';

export interface FilaConciliacion {
  clave: string; fecha: string; concepto: string; detalle: string;
  cargo: string; abono: string; conciliacion_id: number | null;
}

interface Props {
  titulo: string;
  filas: FilaConciliacion[];
  seleccion: Set<string>;
  onAlternar: (clave: string) => void;
  onDeshacer: (conciliacionId: number) => void;
  accion?: (fila: FilaConciliacion) => React.ReactNode;
  etiquetas: [string, string];
}

export default function TablaConciliacion({ titulo, filas, seleccion, onAlternar, onDeshacer, accion, etiquetas }: Props) {
  const pendientes = filas.filter((f) => f.conciliacion_id === null).length;
  return (
    <div className="card" style={{ padding: 0, overflowX: 'auto', flex: '1 1 420px', minWidth: 0 }}>
      <div style={{ padding: '10px 14px', fontWeight: 600, fontSize: '0.88rem', display: 'flex', gap: 8 }}>
        {titulo}
        <span style={{ color: 'var(--text-muted)', fontWeight: 400 }}>
          {filas.length} movimientos · {pendientes} pendientes
        </span>
      </div>
      <table aria-label={titulo} style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' }}>
        <thead>
          <tr style={{ borderBottom: '1px solid var(--border)' }}>
            <th style={thStyle} /><th style={thStyle}>Fecha</th><th style={thStyle}>Concepto</th>
            <th style={{ ...thStyle, textAlign: 'right' }}>{etiquetas[0]}</th>
            <th style={{ ...thStyle, textAlign: 'right' }}>{etiquetas[1]}</th>
            <th style={thStyle}>Estado</th>
          </tr>
        </thead>
        <tbody>
          {filas.length === 0 && (
            <tr><td colSpan={6} style={{ ...tdStyle, textAlign: 'center' }}>Sin movimientos en el periodo.</td></tr>
          )}
          {filas.map((f) => {
            const conciliado = f.conciliacion_id !== null;
            return (
              <tr key={f.clave} style={{
                borderBottom: '1px solid var(--border)',
                background: seleccion.has(f.clave) ? 'var(--teal-bg)' : undefined,
              }}>
                <td style={tdStyle}>
                  <input type="checkbox" aria-label={`Seleccionar ${f.concepto}`} disabled={conciliado}
                    checked={seleccion.has(f.clave)} onChange={() => onAlternar(f.clave)} />
                </td>
                <td style={{ ...tdStyle, whiteSpace: 'nowrap' }}>{f.fecha}</td>
                <td style={tdStyle}>
                  {f.concepto}
                  {f.detalle && <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>{f.detalle}</div>}
                </td>
                <td style={tdMonoStyle}>{dinero(f.cargo)}</td>
                <td style={tdMonoStyle}>{dinero(f.abono)}</td>
                <td style={{ ...tdStyle, whiteSpace: 'nowrap' }}>
                  {conciliado ? (
                    <span style={{ display: 'inline-flex', gap: 4, alignItems: 'center', color: 'var(--success)' }}>
                      <CheckCircle2 size={13} /> Conciliado
                      <button type="button" onClick={() => onDeshacer(f.conciliacion_id as number)}
                        style={{ background: 'none', border: 'none', color: 'var(--teal-light)', cursor: 'pointer', fontSize: '0.75rem' }}>
                        Deshacer
                      </button>
                    </span>
                  ) : (
                    <span style={{ display: 'inline-flex', gap: 4, alignItems: 'center', color: 'var(--warning)' }}>
                      <Circle size={13} /> Pendiente {accion?.(f)}
                    </span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
