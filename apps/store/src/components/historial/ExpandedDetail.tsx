/** Expanded detail view — renders different layouts based on declaration category */

import { Timestamp } from 'firebase/firestore';
import { Download } from 'lucide-react';
import { type DeclaracionRecord } from '../../services/declaracionesHistory';
import { exportarDeclaracionPDF } from '../../services/pdfExport';

interface ExpandedDetailProps {
  record: DeclaracionRecord;
  profile: { nombre: string; rfc: string };
  fmtMoney: (n: number) => string;
}

const thStyle: React.CSSProperties = { padding: '8px 10px', textAlign: 'left', color: 'var(--text-muted)', fontWeight: 500, fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: 0.5 };
const tdStyle: React.CSSProperties = { padding: '8px 10px', color: 'var(--text-secondary)' };
const monoR: React.CSSProperties = { ...tdStyle, fontFamily: "'JetBrains Mono', monospace", textAlign: 'right' };

function PdfBtn({ onClick }: { onClick: () => void }) {
  return (
    <div style={{ marginTop: 16 }}>
      <button className="btn-primary" onClick={(e) => { e.stopPropagation(); onClick(); }}
        style={{ display: 'inline-flex', alignItems: 'center', gap: 8, fontSize: '0.85rem', padding: '8px 20px' }}>
        <Download size={14} /> Descargar PDF
      </button>
    </div>
  );
}

export default function ExpandedDetail({ record: d, profile, fmtMoney }: ExpandedDetailProps) {
  const cat = d.categoria;

  if (cat === 'diot' && d.proveedores) {
    return (
      <div style={{ marginTop: 16 }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border)' }}>
              {['RFC', 'Nombre', 'Total ops.', 'IVA pagado', '#'].map((h) => <th key={h} style={thStyle}>{h}</th>)}
            </tr>
          </thead>
          <tbody>
            {d.proveedores.map((p, i) => (
              <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                <td style={{ ...tdStyle, fontFamily: "'JetBrains Mono', monospace", fontSize: '0.76rem' }}>{p.rfc}</td>
                <td style={tdStyle}>{p.nombre}</td>
                <td style={monoR}>{fmtMoney(p.total_operaciones)}</td>
                <td style={monoR}>{fmtMoney(p.iva_pagado)}</td>
                <td style={{ ...tdStyle, textAlign: 'center' }}>{p.cantidad_facturas}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <PdfBtn onClick={() => {/* DIOT PDF would need full DIOTResponse — skip for stored records */}} />
      </div>
    );
  }

  if (cat === 'retenciones' && d.terceros) {
    return (
      <div style={{ marginTop: 16 }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border)' }}>
              {['RFC', 'Nombre', 'Total', 'ISR ret.', 'IVA ret.', '#'].map((h) => <th key={h} style={thStyle}>{h}</th>)}
            </tr>
          </thead>
          <tbody>
            {d.terceros.map((t, i) => (
              <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                <td style={{ ...tdStyle, fontFamily: "'JetBrains Mono', monospace", fontSize: '0.76rem' }}>{t.rfc}</td>
                <td style={tdStyle}>{t.nombre}</td>
                <td style={monoR}>{fmtMoney(t.total_pagado)}</td>
                <td style={monoR}>{fmtMoney(t.isr_retenido)}</td>
                <td style={monoR}>{fmtMoney(t.iva_retenido)}</td>
                <td style={{ ...tdStyle, textAlign: 'center' }}>{t.cantidad_facturas}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  if (cat === 'multiperiodo' && d.resultados && d.acumulado) {
    return (
      <div style={{ marginTop: 16 }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10, marginBottom: 14 }}>
          {[
            { l: 'Total ISR', v: fmtMoney(d.acumulado.total_isr) },
            { l: 'Total IVA', v: fmtMoney(d.acumulado.total_iva) },
            { l: 'Promedio', v: fmtMoney(d.acumulado.promedio) },
            { l: 'Tendencia', v: d.acumulado.tendencia },
          ].map((s) => (
            <div key={s.l} style={{ padding: '8px 10px', borderRadius: 'var(--radius-xs)', background: 'rgba(110,159,160,0.06)', textAlign: 'center' }}>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: 4 }}>{s.l}</div>
              <div style={{ fontSize: '0.85rem', fontWeight: 600, fontFamily: "'JetBrains Mono', monospace" }}>{s.v}</div>
            </div>
          ))}
        </div>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border)' }}>
              {['Periodo', 'ISR', 'IVA', 'Total'].map((h) => <th key={h} style={thStyle}>{h}</th>)}
            </tr>
          </thead>
          <tbody>
            {d.resultados.map((r, i) => (
              <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                <td style={{ ...tdStyle, fontWeight: 500 }}>{r.periodo}</td>
                <td style={monoR}>{fmtMoney(r.isr)}</td>
                <td style={monoR}>{fmtMoney(r.iva)}</td>
                <td style={{ ...monoR, fontWeight: 700, color: r.total <= 0 ? 'var(--success)' : 'var(--text-primary)' }}>{fmtMoney(r.total)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  if (cat === 'estado_cuenta' && d.estado_cuenta) {
    const ec = d.estado_cuenta;
    return (
      <div style={{ marginTop: 16 }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 14 }}>
          {[
            { l: 'Ingresos acumulados', v: fmtMoney(ec.ingresos_acumulados), c: 'var(--teal-light)' },
            { l: 'Egresos acumulados', v: fmtMoney(ec.egresos_acumulados), c: 'var(--purple-light)' },
            { l: 'ISR estimado', v: fmtMoney(ec.isr_estimado), c: 'var(--text-primary)' },
            { l: 'ISR retenido', v: fmtMoney(ec.isr_retenido), c: 'var(--teal-light)' },
            { l: 'ISR faltante', v: ec.isr_faltante <= 0 ? `${fmtMoney(Math.abs(ec.isr_faltante))} a favor` : fmtMoney(ec.isr_faltante), c: ec.isr_faltante <= 0 ? 'var(--success)' : 'var(--warning)' },
            { l: 'IVA neto', v: fmtMoney(ec.iva_neto), c: 'var(--text-primary)' },
          ].map((s) => (
            <div key={s.l} style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 12px', borderRadius: 'var(--radius-xs)', background: 'rgba(110,159,160,0.04)' }}>
              <span style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>{s.l}</span>
              <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '0.85rem', fontWeight: 600, color: s.c }}>{s.v}</span>
            </div>
          ))}
        </div>
        {d.advertencias && d.advertencias.length > 0 && (
          <div style={{ marginTop: 8 }}>
            {d.advertencias.map((a, i) => (
              <div key={i} style={{ fontSize: '0.8rem', color: 'var(--warning)', paddingLeft: 8, borderLeft: '2px solid var(--warning)', marginBottom: 6 }}>{a}</div>
            ))}
          </div>
        )}
      </div>
    );
  }

  // Default: predeclaracion / deducciones — show desglose
  if (d.desglose) {
    const fecha = d.fecha_calculo instanceof Timestamp ? d.fecha_calculo.toDate() : new Date(d.fecha_calculo);
    return (
      <div style={{ marginTop: 16 }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
          {[
            { label: 'Ingresos facturados', value: d.desglose.total_ingresos_facturados },
            { label: 'Ingresos gravados', value: d.desglose.total_ingresos_gravados },
            { label: 'Deducciones', value: d.desglose.total_deducciones_autorizadas },
            { label: 'Egresos', value: d.desglose.total_egresos },
            { label: 'Base ISR', value: d.desglose.base_isr },
            { label: 'Tasa ISR', value: null, display: `${(d.desglose.tasa_isr * 100).toFixed(2)}%` },
            { label: 'ISR causado', value: d.desglose.isr_causado },
            { label: 'ISR retenido', value: d.desglose.isr_retenido },
            { label: 'ISR a pagar', value: d.desglose.isr_a_pagar, hl: true },
            { label: 'IVA cobrado', value: d.desglose.iva_trasladado_cobrado },
            { label: 'IVA pagado', value: d.desglose.iva_trasladado_pagado },
            { label: 'IVA a pagar', value: d.desglose.iva_a_pagar, hl: true },
          ].map((item) => (
            <div key={item.label} style={{
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              padding: '8px 12px', borderRadius: 'var(--radius-xs)',
              background: item.hl ? 'rgba(110,159,160,0.06)' : 'transparent',
            }}>
              <span style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>{item.label}</span>
              <span style={{
                fontFamily: "'JetBrains Mono', monospace", fontSize: '0.85rem',
                fontWeight: item.hl ? 700 : 400,
                color: item.hl ? 'var(--teal-light)' : 'var(--text-primary)',
              }}>
                {item.display ?? fmtMoney(item.value ?? 0)}
              </span>
            </div>
          ))}
        </div>
        {d.explicacion && (
          <div style={{ marginTop: 14, padding: '14px 16px', borderRadius: 'var(--radius-xs)', background: 'rgba(73,33,83,0.08)', border: '1px solid rgba(73,33,83,0.2)' }}>
            <div style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--purple-light)', marginBottom: 6 }}>Explicación</div>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>{d.explicacion}</p>
          </div>
        )}
        {d.advertencias && d.advertencias.length > 0 && (
          <div style={{ marginTop: 10 }}>
            {d.advertencias.map((a, i) => (
              <div key={i} style={{ fontSize: '0.82rem', color: 'var(--warning)', paddingLeft: 8, borderLeft: '2px solid var(--warning)', marginBottom: 6 }}>{a}</div>
            ))}
          </div>
        )}
        <div style={{ marginTop: 16 }}>
          <button className="btn-primary" onClick={(e) => {
            e.stopPropagation();
            exportarDeclaracionPDF({
              periodo: d.periodo, tipo: d.tipo, regimen: d.regimen, desglose: d.desglose!,
              explicacion: d.explicacion ?? null, advertencias: d.advertencias ?? [],
              recomendaciones: d.recomendaciones ?? [],
              contribuyente: { nombre: profile.nombre, rfc: profile.rfc }, fechaCalculo: fecha,
            });
          }} style={{ display: 'inline-flex', alignItems: 'center', gap: 8, fontSize: '0.85rem', padding: '8px 20px' }}>
            <Download size={14} /> Descargar PDF
          </button>
        </div>
      </div>
    );
  }

  return <div style={{ marginTop: 16, fontSize: '0.85rem', color: 'var(--text-muted)' }}>Sin detalles disponibles.</div>;
}
