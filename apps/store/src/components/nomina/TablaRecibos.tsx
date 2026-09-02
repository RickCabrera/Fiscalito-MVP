/** Tabla de recibos del periodo (D-07). DEMO: se borra en F2. */

import { fmtMoney } from '../../utils/format';
import type { NominaPeriodo, ReciboNomina } from '../../services/nominaDemoApi';
import { envoltura, fila, tabla, td, tdNum, tdNumFuerte, th, thNum, tituloSeccion } from './estilosTabla';

const MONO_FAMILY = "'JetBrains Mono', monospace";

function isr(recibo: ReciboNomina): number {
  return recibo.deducciones
    .filter((d) => d.tipo === '002')
    .reduce((suma, d) => suma + Number(d.importe), 0);
}

export default function TablaRecibos({ nomina }: { nomina: NominaPeriodo }) {
  const total = (obtener: (r: ReciboNomina) => number) =>
    nomina.recibos.reduce((suma, r) => suma + obtener(r), 0);

  return (
    <section className="card" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
      <header style={{ display: 'flex', alignItems: 'baseline', gap: 'var(--space-sm)', flexWrap: 'wrap' }}>
        <h2 style={tituloSeccion}>Recibos</h2>
        <span style={{ color: 'var(--text-muted)', fontSize: '0.82rem' }}>
          {nomina.recibos.length} empleados
        </span>
        <span style={{ marginLeft: 'auto', fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
          Neto del periodo{' '}
          <strong
            style={{
              color: 'var(--text-primary)',
              fontFamily: MONO_FAMILY,
              fontVariantNumeric: 'tabular-nums',
            }}
          >
            {fmtMoney(total((r) => Number(r.neto)))}
          </strong>
        </span>
      </header>
      <div style={envoltura}>
        <table style={tabla(820)}>
          <thead>
            <tr>
              <th style={th}>Empleado</th>
              <th style={thNum}>SBC</th>
              <th style={thNum}>Días pagados</th>
              <th style={thNum}>Percepciones</th>
              <th style={thNum}>ISR</th>
              <th style={thNum}>Cuota obrera</th>
              <th style={thNum}>Neto</th>
            </tr>
          </thead>
          <tbody>
            {nomina.recibos.map((r, i) => (
              <tr key={r.empleado_no} style={fila(i)}>
                <td style={td}>
                  {r.nombre}{' '}
                  <span style={{ color: 'var(--text-muted)' }}>({r.empleado_no})</span>
                </td>
                <td style={tdNum}>{fmtMoney(Number(r.sbc))}</td>
                <td style={tdNum}>{r.dias_pagados}</td>
                <td style={tdNum}>{fmtMoney(Number(r.total_percepciones))}</td>
                <td style={tdNum}>{fmtMoney(isr(r))}</td>
                <td style={tdNum}>{fmtMoney(Number(r.cuota_obrera))}</td>
                <td style={tdNumFuerte}>{fmtMoney(Number(r.neto))}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr style={{ borderTop: '2px solid var(--border-active)' }}>
              <td style={{ ...td, fontWeight: 700 }}>Totales</td>
              <td />
              <td />
              <td style={tdNumFuerte}>
                {fmtMoney(total((r) => Number(r.total_percepciones)))}
              </td>
              <td style={tdNumFuerte}>{fmtMoney(total(isr))}</td>
              <td style={tdNumFuerte}>{fmtMoney(total((r) => Number(r.cuota_obrera)))}</td>
              <td style={tdNumFuerte}>{fmtMoney(total((r) => Number(r.neto)))}</td>
            </tr>
          </tfoot>
        </table>
      </div>
    </section>
  );
}
