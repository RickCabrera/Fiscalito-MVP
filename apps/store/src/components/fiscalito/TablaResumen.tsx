/**
 * La tabla del resumen de impuestos (P3-02), como la de Contadigital: un renglón
 * por impuesto y columnas capturables (importe a pagar, subsidio, compensaciones).
 * Lo capturado se manda al backend al recalcular; aquí no se suma nada.
 */

import type { CapturaRenglon, ResumenImpuestos } from '../../services/impuestosApi';

interface Props {
  resumen: ResumenImpuestos;
  capturas: Record<string, CapturaRenglon>;
  onCapturar: (clave: string, campo: keyof CapturaRenglon, valor: string) => void;
}

const CELDA: React.CSSProperties = {
  padding: '6px 8px', borderBottom: '1px solid var(--border)', textAlign: 'right',
  fontFamily: 'JetBrains Mono, monospace', fontSize: '0.8rem', whiteSpace: 'nowrap',
};
const ENTRADA: React.CSSProperties = { width: 100, textAlign: 'right', padding: '4px 6px' };

export default function TablaResumen({ resumen, capturas, onCapturar }: Props) {
  const entrada = (clave: string, campo: keyof CapturaRenglon, etiqueta: string, sugerido: string) => (
    <input className="input-field" style={ENTRADA} type="number" step="0.01" min={0}
      aria-label={`${etiqueta} ${clave}`} placeholder={sugerido}
      value={capturas[clave]?.[campo] ?? ''}
      onChange={(e) => onCapturar(clave, campo, e.target.value)} />
  );

  return (
    <div className="card" style={{ overflowX: 'auto' }}>
      <p style={{ margin: '0 0 8px', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
        Periodo {String(resumen.mes).padStart(2, '0')}/{resumen.anio} · fecha límite {resumen.fecha_limite} ·
        fecha de pago {resumen.fecha_pago}
      </p>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ color: 'var(--text-secondary)', fontSize: '0.75rem' }}>
            <th style={{ ...CELDA, textAlign: 'left' }}>Concepto</th>
            <th style={CELDA}>Importe sistema</th>
            <th style={CELDA}>Importe a pagar</th>
            <th style={CELDA}>Actualización</th>
            <th style={CELDA}>Recargos</th>
            <th style={CELDA}>Subsidio</th>
            <th style={CELDA}>Compensaciones</th>
            <th style={CELDA}>Total</th>
          </tr>
        </thead>
        <tbody>
          {resumen.renglones.map((r) => (
            <tr key={r.clave} style={{ opacity: r.aplica ? 1 : 0.55 }}>
              <td style={{ ...CELDA, textAlign: 'left', fontFamily: 'inherit' }} title={r.nota}>
                <div>{r.concepto}</div>
                {r.nota && <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', whiteSpace: 'normal' }}>{r.nota}</div>}
              </td>
              <td style={CELDA}>{r.importe_sistema}</td>
              <td style={CELDA}>{entrada(r.clave, 'importe_a_pagar', 'Importe a pagar', r.importe_a_pagar)}</td>
              <td style={CELDA} title={r.factor ? `Factor ${r.factor}` : ''}>{r.actualizacion}</td>
              <td style={CELDA} title={`${r.meses_recargo} meses`}>{r.recargos}</td>
              <td style={CELDA}>
                {r.clave === 'ret_isr_salarios' ? entrada(r.clave, 'subsidio', 'Subsidio', r.subsidio) : r.subsidio}
              </td>
              <td style={CELDA}>{entrada(r.clave, 'compensaciones', 'Compensaciones', r.compensaciones)}</td>
              <td style={{ ...CELDA, fontWeight: 700 }}>{r.total}</td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr style={{ fontWeight: 700 }}>
            <td style={{ ...CELDA, textAlign: 'left', fontFamily: 'inherit' }}>Total</td>
            {['importe_sistema', 'importe_a_pagar', 'actualizacion', 'recargos', 'subsidio', 'compensaciones', 'total']
              .map((k) => <td key={k} style={CELDA}>{resumen.totales[k]}</td>)}
          </tr>
        </tfoot>
      </table>
      <p style={{ margin: '10px 0 0', fontSize: '0.9rem' }}>
        Total a pagar (ajustado a pesos, Art. 20 CFF):{' '}
        <strong data-testid="total-ajustado" style={{ color: 'var(--teal-light)' }}>{resumen.total_a_pagar_ajustado}</strong>
      </p>
      <p style={{ margin: '6px 0 0', fontSize: '0.72rem', color: 'var(--text-muted)' }}>
        Lo capturado se aplica al volver a calcular. Actualización y recargos: Arts. 17-A y 21 CFF.
      </p>
      {resumen.notas.length > 0 && (
        <ul style={{ margin: '8px 0 0', paddingLeft: 18, fontSize: '0.75rem', color: 'var(--warning)' }}>
          {resumen.notas.map((n) => <li key={n}>{n}</li>)}
        </ul>
      )}
    </div>
  );
}
