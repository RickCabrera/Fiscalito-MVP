/** Tabla de recibos del periodo (D-07). DEMO: se borra en F2. */

import { fmtMoney } from '../../utils/format';
import type { NominaPeriodo, ReciboNomina } from '../../services/nominaDemoApi';

function isr(recibo: ReciboNomina): number {
  return recibo.deducciones
    .filter((d) => d.tipo === '002')
    .reduce((suma, d) => suma + Number(d.importe), 0);
}

export default function TablaRecibos({ nomina }: { nomina: NominaPeriodo }) {
  const total = (obtener: (r: ReciboNomina) => number) =>
    nomina.recibos.reduce((suma, r) => suma + obtener(r), 0);

  return (
    <section
      style={{
        background: 'var(--bg-surface)',
        border: '1px solid var(--border)',
        borderRadius: 12,
        padding: 20,
      }}
    >
      <h2 style={{ fontSize: '1rem', marginTop: 0 }}>Recibos</h2>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem' }}>
        <thead>
          <tr style={{ textAlign: 'left', color: 'var(--text-muted)' }}>
            <th style={{ padding: '4px 0' }}>Empleado</th>
            <th>SBC</th>
            <th>Días pagados</th>
            <th style={{ textAlign: 'right' }}>Percepciones</th>
            <th style={{ textAlign: 'right' }}>ISR</th>
            <th style={{ textAlign: 'right' }}>Cuota obrera</th>
            <th style={{ textAlign: 'right' }}>Neto</th>
          </tr>
        </thead>
        <tbody>
          {nomina.recibos.map((r) => (
            <tr key={r.empleado_no}>
              <td style={{ padding: '4px 0' }}>
                {r.nombre} <span style={{ color: 'var(--text-muted)' }}>({r.empleado_no})</span>
              </td>
              <td>{fmtMoney(Number(r.sbc))}</td>
              <td>{r.dias_pagados}</td>
              <td style={{ textAlign: 'right' }}>{fmtMoney(Number(r.total_percepciones))}</td>
              <td style={{ textAlign: 'right' }}>{fmtMoney(isr(r))}</td>
              <td style={{ textAlign: 'right' }}>{fmtMoney(Number(r.cuota_obrera))}</td>
              <td style={{ textAlign: 'right', fontWeight: 600 }}>{fmtMoney(Number(r.neto))}</td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr style={{ borderTop: '1px solid var(--border)', fontWeight: 700 }}>
            <td style={{ padding: '6px 0' }}>Totales</td>
            <td />
            <td />
            <td style={{ textAlign: 'right' }}>
              {fmtMoney(total((r) => Number(r.total_percepciones)))}
            </td>
            <td style={{ textAlign: 'right' }}>{fmtMoney(total(isr))}</td>
            <td style={{ textAlign: 'right' }}>
              {fmtMoney(total((r) => Number(r.cuota_obrera)))}
            </td>
            <td style={{ textAlign: 'right' }}>{fmtMoney(total((r) => Number(r.neto)))}</td>
          </tr>
        </tfoot>
      </table>
    </section>
  );
}
