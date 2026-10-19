/**
 * Pinta el resultado de un finiquito, aguinaldo, PTU o ajuste anual tal como lo devolvió
 * el motor: por trabajador o por concepto, con gravado/exento y fundamento. No suma nada.
 */

import type { CalculoExtraordinario } from '../../services/nominaApi';
import { fmtMoney } from '../../utils/format';
import { envoltura, tabla, td, tdNum, th, thNum } from './estilosTabla';

type Fila = Record<string, unknown>;

const dinero = (v: unknown) => (v === undefined || v === null || v === '' ? '—' : fmtMoney(Number(v)));

function Conceptos({ conceptos }: { conceptos: Fila[] }) {
  return (
    <div style={envoltura}>
      <table style={tabla(720)}>
        <thead>
          <tr>
            <th style={th}>Concepto</th>
            <th style={thNum}>Importe</th>
            <th style={thNum}>Exento</th>
            <th style={thNum}>Gravado</th>
            <th style={th}>Fundamento</th>
          </tr>
        </thead>
        <tbody>
          {conceptos.map((c, i) => (
            <tr key={i}>
              <td style={td}>{String(c.concepto)}</td>
              <td style={tdNum}>{dinero(c.importe)}</td>
              <td style={tdNum}>{dinero(c.exento)}</td>
              <td style={tdNum}>{dinero(c.gravado)}</td>
              <td style={{ ...td, fontSize: '0.78rem', color: 'var(--text-muted)' }}>{String(c.fundamento ?? '')}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function PorTrabajador({ filas, ajuste }: { filas: Fila[]; ajuste: boolean }) {
  return (
    <div style={envoltura}>
      <table style={tabla(720)}>
        <thead>
          <tr>
            <th style={th}>Empleado</th>
            {ajuste ? (
              <>
                <th style={thNum}>Impuesto anual</th>
                <th style={thNum}>Retenido</th>
                <th style={thNum}>A cargo</th>
                <th style={thNum}>A favor</th>
                <th style={th}>Motivo</th>
              </>
            ) : (
              <>
                <th style={thNum}>Importe</th>
                <th style={thNum}>ISR</th>
                <th style={thNum}>Neto</th>
              </>
            )}
          </tr>
        </thead>
        <tbody>
          {filas.map((f, i) => (
            <tr key={i}>
              <td style={td}>{String(f.nombre ?? f.empleado_no)}</td>
              {ajuste ? (
                <>
                  <td style={tdNum}>{dinero(f.impuesto_anual)}</td>
                  <td style={tdNum}>{dinero(f.isr_retenido)}</td>
                  <td style={tdNum}>{dinero(f.saldo_a_cargo)}</td>
                  <td style={tdNum}>{dinero(f.saldo_a_favor)}</td>
                  <td style={{ ...td, fontSize: '0.78rem' }}>{String(f.motivo ?? '')}</td>
                </>
              ) : (
                <>
                  <td style={tdNum}>{dinero(f.total_percepciones)}</td>
                  <td style={tdNum}>{dinero(f.isr)}</td>
                  <td style={tdNum}>{dinero(f.neto)}</td>
                </>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function ResultadoExtraordinario({ calculo }: { calculo: CalculoExtraordinario }) {
  const r = calculo.resultado;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
      {calculo.tipo === 'finiquito' ? (
        <>
          <Conceptos conceptos={(r.conceptos as Fila[]) ?? []} />
          <p style={{ margin: 0 }}>
            Total {dinero(r.total)} · ISR ordinario {dinero(r.isr_ordinario)} · ISR por separación{' '}
            {dinero(r.isr_separacion)} · <strong>Neto {dinero(r.neto)}</strong>
          </p>
        </>
      ) : (
        <PorTrabajador
          filas={((r.recibos ?? r.trabajadores) as Fila[]) ?? []}
          ajuste={calculo.tipo === 'ajuste_anual'}
        />
      )}
      {calculo.tipo === 'ptu' && (
        <p style={{ margin: 0 }}>
          Repartible {dinero(r.utilidad_repartible)} · repartido {dinero(r.repartido)} · remanente {dinero(r.remanente)}
        </p>
      )}
      {calculo.advertencias.map((a) => (
        <p key={a} style={{ margin: 0, fontSize: '0.8rem', color: 'var(--warning)' }}>
          {a}
        </p>
      ))}
      {calculo.periodo_id && (
        <p style={{ margin: 0, fontSize: '0.78rem', color: 'var(--text-muted)' }}>
          Guardado en el historial del cliente (#{calculo.periodo_id}).
        </p>
      )}
    </div>
  );
}
