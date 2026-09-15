/**
 * Tab Pólizas de Contabilito (T7).
 *
 * Una fila por CFDI fiscal, expandible a sus movimientos. La fila enseña el
 * total de cargos y el de abonos **por separado** en vez de un solo importe:
 * ver los dos iguales es la comprobación de la partida doble, y esconder uno
 * de los dos la vuelve un acto de fe.
 */

import { useState } from 'react';
import { ChevronDown, ChevronRight, FileStack, AlertTriangle } from 'lucide-react';
import type { Poliza } from '../../services/contabilidad/polizas';
import { fmtMoney } from '../../utils/format';
import { thStyle, tdStyle, tdMonoStyle } from '../../utils/styles';

interface Props {
  polizas: Poliza[];
  recibosNomina: number;
  sinEfecto: number;
}

const ETIQUETA_TIPO: Record<Poliza['tipo'], string> = {
  ingreso: 'Ingreso',
  egreso: 'Egreso',
  diario: 'Diario',
};

export default function PolizasTab({ polizas, recibosNomina, sinEfecto }: Props) {
  const [abierta, setAbierta] = useState<string | null>(null);

  if (polizas.length === 0) {
    return (
      <div className="card" style={{ textAlign: 'center', padding: 'var(--space-lg)' }}>
        <FileStack size={28} color="var(--text-muted)" />
        <p style={{ margin: '12px 0 0', fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
          Carga los CFDI del periodo arriba y aquí sale una póliza por comprobante.
        </p>
      </div>
    );
  }

  const descuadradas = polizas.filter((p) => Math.abs(p.diferenciaConTotal) >= 0.01);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {recibosNomina > 0 && (
        <div style={{
          padding: '8px 12px', borderRadius: 'var(--radius-xs)',
          background: 'var(--teal-bg-subtle)', border: '1px solid var(--border)',
          fontSize: '0.78rem', color: 'var(--text-secondary)',
        }}>
          {recibosNomina} recibo{recibosNomina > 1 ? 's' : ''} de nómina sin póliza — este
          cascarón no contabiliza nómina: sus retenciones y cuotas obrero-patronales van a
          cuentas que el catálogo todavía no maneja.
        </div>
      )}

      {sinEfecto > 0 && (
        <div style={{
          padding: '8px 12px', borderRadius: 'var(--radius-xs)',
          background: 'var(--bg-card)', border: '1px solid var(--border)',
          fontSize: '0.78rem', color: 'var(--text-muted)',
        }}>
          {sinEfecto} comprobante{sinEfecto > 1 ? 's' : ''} sin movimientos: un traslado (T) no
          transfiere propiedad, y un comprobante en ceros no mueve cuentas.
        </div>
      )}

      {descuadradas.length > 0 && (
        <div style={{
          display: 'flex', alignItems: 'flex-start', gap: 8,
          padding: '10px 12px', borderRadius: 'var(--radius-xs)',
          background: 'var(--warning-bg)', border: '1px solid var(--warning-border)',
          fontSize: '0.78rem', color: 'var(--text-secondary)',
        }}>
          <AlertTriangle size={14} style={{ color: 'var(--warning)', flexShrink: 0, marginTop: 2 }} />
          <span>
            En {descuadradas.length} póliza{descuadradas.length > 1 ? 's' : ''} el total del CFDI
            no coincide con lo que se contabilizó. La póliza cuadra; lo que falta es un impuesto
            que el lector de XML no interpreta (IEPS y locales). Está marcado en la fila.
          </span>
        </div>
      )}

      <div className="card" style={{ padding: 0, overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border)' }}>
              <th style={{ ...thStyle, width: 36 }}></th>
              <th style={thStyle}>Fecha</th>
              <th style={thStyle}>Tipo</th>
              <th style={thStyle}>Concepto</th>
              <th style={thStyle}>Contraparte</th>
              <th style={{ ...thStyle, textAlign: 'right' }}>Cargos</th>
              <th style={{ ...thStyle, textAlign: 'right' }}>Abonos</th>
            </tr>
          </thead>
          <tbody>
            {polizas.map((p) => {
              const expandida = abierta === p.uuid;
              const difiere = Math.abs(p.diferenciaConTotal) >= 0.01;
              return [
                <tr
                  key={p.uuid}
                  onClick={() => setAbierta(expandida ? null : p.uuid)}
                  style={{ borderBottom: '1px solid var(--border)', cursor: 'pointer' }}
                >
                  <td style={{ ...tdStyle, color: 'var(--text-muted)' }}>
                    {expandida ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                  </td>
                  <td style={tdStyle}>{(p.fecha || '').slice(0, 10)}</td>
                  <td style={tdStyle}>
                    {ETIQUETA_TIPO[p.tipo]}
                    <span style={{ color: 'var(--text-muted)', fontSize: '0.72rem' }}>
                      {' '}({p.tipoComprobante} · {p.direccion})
                    </span>
                  </td>
                  <td style={{ ...tdStyle, color: 'var(--text-primary)' }}>
                    {p.concepto}
                    {difiere && (
                      <span title={`Total del CFDI ${fmtMoney(p.totalCargos + p.diferenciaConTotal)} vs contabilizado`}
                        style={{ color: 'var(--warning)', marginLeft: 6 }}>
                        ⚠
                      </span>
                    )}
                  </td>
                  <td style={{ ...tdStyle, fontFamily: "'JetBrains Mono', monospace", fontSize: '0.78rem' }}>
                    {p.contraparte}
                  </td>
                  <td style={tdMonoStyle}>{fmtMoney(p.totalCargos)}</td>
                  <td style={tdMonoStyle}>{fmtMoney(p.totalAbonos)}</td>
                </tr>,
                expandida && (
                  <tr key={`${p.uuid}-mov`} style={{ borderBottom: '1px solid var(--border)', background: 'var(--bg-surface)' }}>
                    <td colSpan={7} style={{ padding: '10px 14px 14px 46px' }}>
                      <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginBottom: 6 }}>
                        UUID {p.uuid}
                      </div>
                      {p.movimientos.length === 0 ? (
                        <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                          Sin movimientos contables.
                        </div>
                      ) : (
                        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' }}>
                          <tbody>
                            {p.movimientos.map((m, i) => (
                              <tr key={`${m.cuenta}-${i}`}>
                                <td style={{ ...tdStyle, fontFamily: "'JetBrains Mono', monospace", color: 'var(--teal-light)', width: 70 }}>
                                  {m.cuenta}
                                </td>
                                <td style={tdStyle}>{m.nombre}</td>
                                <td style={{ ...tdMonoStyle, width: 140 }}>
                                  {m.cargo > 0 ? fmtMoney(m.cargo) : ''}
                                </td>
                                <td style={{ ...tdMonoStyle, width: 140 }}>
                                  {m.abono > 0 ? fmtMoney(m.abono) : ''}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      )}
                    </td>
                  </tr>
                ),
              ];
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
