/**
 * Desglose por concepto de cada recibo (P4): percepciones con gravado y exento,
 * deducciones, otros pagos, la tarifa con la que se calculó y si fue parcial.
 *
 * Todo sale del motor tal cual. El único cálculo del front es sumar para pintar un pie,
 * igual que `TablaRecibos`.
 */

import { useState } from 'react';
import type { Partida, ReciboNomina } from '../../services/nominaDemoApi';
import { fmtMoney } from '../../utils/format';
import { envoltura, tabla, td, tdNum, th, thNum, tituloSeccion } from './estilosTabla';

/** Los campos de P4 que el motor agrega al recibo. Opcionales: un histórico viejo no los trae. */
export type ReciboDesglosado = ReciboNomina & {
  tipo_regimen?: string;
  dias_en_periodo?: number | null;
  parcial?: boolean;
  tarifa?: string;
  isr_causado?: string | null;
  subsidio_causado?: string;
  sbc_variable_integrable?: string;
};

function Partidas({ titulo, partidas, conGravado }: { titulo: string; partidas: Partida[]; conGravado?: boolean }) {
  if (partidas.length === 0) return null;
  return (
    <div style={envoltura}>
      <table style={tabla(520)}>
        <thead>
          <tr>
            <th style={th}>{titulo}</th>
            <th style={thNum}>Importe</th>
            {conGravado && <th style={thNum}>Gravado</th>}
            {conGravado && <th style={thNum}>Exento</th>}
          </tr>
        </thead>
        <tbody>
          {partidas.map((p, i) => (
            <tr key={`${p.tipo}-${p.clave}-${i}`}>
              <td style={td}>
                {p.concepto} <span style={{ color: 'var(--text-muted)' }}>({p.tipo})</span>
              </td>
              <td style={tdNum}>{fmtMoney(Number(p.importe))}</td>
              {conGravado && <td style={tdNum}>{fmtMoney(Number(p.gravado ?? 0))}</td>}
              {conGravado && <td style={tdNum}>{fmtMoney(Number(p.exento ?? 0))}</td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function DesgloseRecibos({ recibos }: { recibos: ReciboDesglosado[] }) {
  const [abierto, setAbierto] = useState<string | null>(null);
  if (recibos.length === 0) return null;
  return (
    <section className="card" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
      <h2 style={tituloSeccion}>Desglose por concepto</h2>
      {recibos.map((r) => {
        const visible = abierto === r.empleado_no;
        return (
          <div key={r.empleado_no} style={{ borderTop: '1px solid var(--border)', paddingTop: 'var(--space-xs)' }}>
            <button
              className="btn-secondary"
              aria-expanded={visible}
              onClick={() => setAbierto(visible ? null : r.empleado_no)}
            >
              {r.nombre} ({r.empleado_no}) · neto {fmtMoney(Number(r.neto))}
              {r.parcial ? ' · periodo parcial' : ''}
              {r.tipo_regimen && r.tipo_regimen !== '02' ? ' · asimilado' : ''}
            </button>
            {visible && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-xs)', marginTop: 'var(--space-xs)' }}>
                <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                  Días pagados {r.dias_pagados}
                  {r.dias_en_periodo ? ` de ${r.dias_en_periodo} con relación laboral` : ''}
                  {r.tarifa ? ` · tarifa ${r.tarifa}` : ''}
                  {r.isr_causado ? ` · ISR causado ${fmtMoney(Number(r.isr_causado))}` : ''}
                  {r.subsidio_causado && Number(r.subsidio_causado) > 0
                    ? ` · subsidio causado ${fmtMoney(Number(r.subsidio_causado))}`
                    : ''}
                  {r.sbc_variable_integrable && Number(r.sbc_variable_integrable) > 0
                    ? ` · integra al SBC del bimestre siguiente ${fmtMoney(Number(r.sbc_variable_integrable))}`
                    : ''}
                </p>
                <Partidas titulo="Percepciones" partidas={r.percepciones} conGravado />
                <Partidas titulo="Deducciones" partidas={r.deducciones} />
                <Partidas titulo="Otros pagos" partidas={r.otros_pagos} />
              </div>
            )}
          </div>
        );
      })}
    </section>
  );
}
