/**
 * Tabla mes a mes de importes que ya vienen calculados del motor (P3-01, P3-06).
 * No suma ni redondea: pinta el texto que manda el backend, igual que el Excel.
 */

import { CELDA, nombreMes, type ColumnaMes } from './tablaMesesUtil';

interface Props {
  etiqueta: string;
  columnas: ColumnaMes[];
  filas: Record<string, unknown>[];
}

export default function TablaMeses({ etiqueta, columnas, filas }: Props) {
  return (
    <div className="card" style={{ overflowX: 'auto' }}>
      <table aria-label={etiqueta} style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ color: 'var(--text-secondary)', fontSize: '0.75rem' }}>
            <th style={{ ...CELDA, textAlign: 'left' }}>Mes</th>
            {columnas.map((c) => <th key={c.campo} style={CELDA}>{c.titulo}</th>)}
          </tr>
        </thead>
        <tbody>
          {filas.map((f) => (
            <tr key={String(f.mes)}>
              <td style={{ ...CELDA, textAlign: 'left', fontFamily: 'inherit' }}>
                {nombreMes(Number(f.mes))}
              </td>
              {columnas.map((c) => (
                <td key={c.campo} style={CELDA}>
                  {String(f[c.campo] ?? '')}
                  {c.campo === 'pago_efectuado' && f.pago_capturado === true && (
                    <span title="Capturado" style={{ color: 'var(--text-muted)' }}> *</span>
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
