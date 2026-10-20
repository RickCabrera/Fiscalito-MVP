/** Historial de cobros de la suscripción, tal como los reportó el proveedor (P5-08). */

import { fechaCorta, type PagoSuscripcion } from '../../services/suscripcionApi';

export default function HistorialPagos({ pagos }: { pagos: PagoSuscripcion[] }) {
  if (pagos.length === 0) {
    return (
      <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>Aún no hay pagos registrados.</p>
    );
  }
  return (
    <table aria-label="Historial de pagos" style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
      <thead>
        <tr style={{ color: 'var(--text-muted)', textAlign: 'left' }}>
          <th style={{ padding: 6 }}>Fecha</th>
          <th style={{ padding: 6 }}>Plan</th>
          <th style={{ padding: 6 }}>Estado</th>
          <th style={{ padding: 6, textAlign: 'right' }}>Monto</th>
        </tr>
      </thead>
      <tbody>
        {pagos.map((p) => (
          <tr key={p.id} style={{ borderTop: '1px solid var(--border)' }}>
            <td style={{ padding: 6 }}>{fechaCorta(p.fecha)}</td>
            <td style={{ padding: 6 }}>{p.plan}</td>
            <td style={{ padding: 6, color: p.estado === 'pagado' ? 'var(--success)' : 'var(--danger)' }}>
              {p.estado === 'pagado' ? 'Pagado' : 'Fallido'}
            </td>
            <td style={{ padding: 6, textAlign: 'right', fontFamily: "'JetBrains Mono', monospace" }}>
              {p.monto !== null ? `$${p.monto} ${p.moneda}` : '—'}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
