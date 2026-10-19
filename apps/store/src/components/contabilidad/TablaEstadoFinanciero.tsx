/**
 * Pinta un estado financiero (P2-05) tal como lo arma el backend: encabezados de
 * rubro, renglones de cuenta con sangría por nivel, subtotales y totales. No
 * suma nada: cada importe viene calculado. En el balance general enseña el
 * cuadre activo = pasivo + capital que decidió el backend.
 */

import { CheckCircle2, XCircle } from 'lucide-react';
import type { EstadoFinanciero } from '../../services/contabilidadApi';
import { dinero } from './comun';
import { tdMonoStyle, tdStyle, thStyle } from '../../utils/styles';

export default function TablaEstadoFinanciero({ reporte }: { reporte: EstadoFinanciero }) {
  const balance = reporte.reporte === 'balance_general';
  return (
    <section className="card" aria-label={reporte.titulo} style={{ padding: 0, overflowX: 'auto' }}>
      <div style={{ padding: 'var(--space-md)', display: 'flex', flexWrap: 'wrap', gap: 'var(--space-md)', alignItems: 'baseline' }}>
        <strong style={{ fontSize: '1rem' }}>{reporte.titulo}</strong>
        <span style={{ color: 'var(--text-secondary)', fontSize: '0.82rem' }}>
          {balance ? `Al ${reporte.hasta}` : `Del ${reporte.desde} al ${reporte.hasta}`}
          {reporte.comparativo && ` · comparativo ${reporte.comparativo.desde} a ${reporte.comparativo.hasta}`}
          {` · ${reporte.moneda}`}{reporte.tipo_cambio && ` (TC ${reporte.tipo_cambio})`}
        </span>
        {balance && (
          <span role="status" style={{
            display: 'inline-flex', gap: 6, alignItems: 'center', fontSize: '0.85rem',
            color: reporte.cuadra ? 'var(--success)' : 'var(--danger)',
          }}>
            {reporte.cuadra ? <CheckCircle2 size={15} /> : <XCircle size={15} />}
            {reporte.cuadra ? 'Activo = pasivo + capital' : `No cuadra: diferencia ${reporte.diferencia}`}
          </span>
        )}
      </div>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.84rem' }}>
        <thead>
          <tr style={{ borderBottom: '1px solid var(--border)' }}>
            <th style={thStyle}>Concepto</th>
            {reporte.columnas.map((c) => <th key={c.clave} style={{ ...thStyle, textAlign: 'right' }}>{c.etiqueta}</th>)}
          </tr>
        </thead>
        <tbody>
          {reporte.lineas.map((l, i) => {
            if (l.tipo === 'encabezado') {
              return (
                <tr key={`${l.clave}-${i}`}>
                  <td colSpan={reporte.columnas.length + 1} style={{ ...tdStyle, color: 'var(--teal-light)', fontWeight: 700, paddingTop: 18 }}>
                    {l.etiqueta}
                  </td>
                </tr>
              );
            }
            const fuerte = l.tipo !== 'cuenta';
            return (
              <tr key={`${l.clave}-${i}`} style={{
                borderTop: fuerte ? '1px solid var(--border)' : undefined,
                fontWeight: l.tipo === 'total' ? 800 : fuerte ? 600 : 400,
              }}>
                <td style={{ ...tdStyle, paddingLeft: 14 + Math.max(0, l.nivel - 1) * 14, color: fuerte ? 'var(--text-primary)' : undefined }}>
                  {l.numero && <span style={{ fontFamily: "'JetBrains Mono', monospace", marginRight: 8 }}>{l.numero}</span>}
                  {l.etiqueta}
                </td>
                {reporte.columnas.map((c) => (
                  <td key={c.clave} style={{ ...tdMonoStyle, color: fuerte ? 'var(--text-primary)' : undefined }}>
                    {dinero(l.valores?.[c.clave], fuerte ? '0.00' : '—')}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </section>
  );
}
