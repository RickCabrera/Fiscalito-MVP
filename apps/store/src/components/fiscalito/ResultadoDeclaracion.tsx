/** Muestra el resultado de una pre-declaración calculada */

import type { PreDeclaracionResponse } from '../../services/fiscalAgentApi';
import { exportarDeclaracionPDF } from '../../services/pdfExport';
import { useProfile } from '../../context/ProfileContext';
import { formatMoney } from '../../utils/format';
import { AlertTriangle, Lightbulb, RefreshCw, MessageSquare, Download } from 'lucide-react';

interface Props {
  resultado: PreDeclaracionResponse;
  onNuevaDeclaracion: () => void;
}

function formatTasa(tasa: number): string {
  return `${(tasa * 100).toFixed(2)}%`;
}

export default function ResultadoDeclaracion({ resultado, onNuevaDeclaracion }: Props) {
  const { profile } = useProfile();
  const d = resultado.desglose;
  const totalAPagar = d.total_a_pagar;
  const esAFavor = totalAPagar < 0;

  const handleDescargarPDF = () => {
    exportarDeclaracionPDF({
      periodo: resultado.periodo,
      tipo: resultado.tipo_declaracion,
      regimen: resultado.regimen,
      desglose: resultado.desglose,
      explicacion: resultado.explicacion ?? null,
      advertencias: resultado.advertencias ?? [],
      recomendaciones: resultado.recomendaciones ?? [],
      contribuyente: { nombre: profile.nombre, rfc: profile.rfc },
      fechaCalculo: new Date(),
    });
  };

  const items: { label: string; value: string; highlight?: boolean }[] = [
    { label: 'Ingresos facturados', value: formatMoney(d.total_ingresos_facturados) },
    { label: 'Ingresos gravados', value: formatMoney(d.total_ingresos_gravados) },
    ...(d.total_deducciones_autorizadas ? [{ label: 'Deducciones autorizadas', value: formatMoney(d.total_deducciones_autorizadas) }] : []),
    ...(d.total_egresos ? [{ label: 'Egresos', value: formatMoney(d.total_egresos) }] : []),
    ...(d.gastos_personales_excluidos ? [{ label: `Gastos personales excluidos (${d.cantidad_gastos_personales ?? 0} facturas)`, value: formatMoney(d.gastos_personales_excluidos) }] : []),
    { label: 'Base ISR', value: formatMoney(d.base_isr) },
    { label: 'Tasa ISR', value: formatTasa(d.tasa_isr) },
    { label: 'ISR causado', value: formatMoney(d.isr_causado) },
    ...(d.isr_retenido ? [{ label: 'ISR retenido', value: formatMoney(d.isr_retenido) }] : []),
    ...(d.pagos_provisionales_anteriores ? [{ label: 'ISR de meses anteriores acreditado', value: `-${formatMoney(d.pagos_provisionales_anteriores)}` }] : []),
    { label: 'ISR a pagar', value: formatMoney(d.isr_a_pagar), highlight: true },
    ...(d.iva_trasladado_cobrado != null ? [{ label: 'IVA cobrado', value: formatMoney(d.iva_trasladado_cobrado) }] : []),
    ...(d.iva_trasladado_pagado != null ? [{ label: 'IVA pagado (acreditable)', value: formatMoney(d.iva_trasladado_pagado) }] : []),
    ...(d.iva_retenido ? [{ label: 'IVA retenido', value: formatMoney(d.iva_retenido) }] : []),
    { label: 'IVA a pagar', value: formatMoney(d.iva_a_pagar), highlight: true },
  ];

  return (
    <div className="animate-in" style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Total principal */}
      <div className="card" style={{
        textAlign: 'center',
        background: esAFavor
          ? 'linear-gradient(135deg, var(--success-bg), var(--teal-bg))'
          : 'linear-gradient(135deg, var(--purple-bg), var(--purple-bg-subtle))',
        border: `1px solid ${esAFavor ? 'var(--success-border)' : 'var(--border-hover)'}`,
      }}>
        <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 8 }}>
          {resultado.tipo_declaracion} — {resultado.periodo}
        </div>
        <div style={{
          fontSize: '2.4rem', fontWeight: 800, fontFamily: "'JetBrains Mono', monospace",
          color: esAFavor ? 'var(--success)' : 'var(--text-primary)',
        }}>
          {esAFavor
            ? `${formatMoney(Math.abs(totalAPagar))} a favor`
            : formatMoney(totalAPagar)}
        </div>
        <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: 4 }}>
          {esAFavor ? 'Saldo a favor estimado' : 'Total estimado a pagar (ISR + IVA)'}
        </div>
      </div>

      {/* Desglose grid */}
      <div className="card">
        <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: 16 }}>Desglose</h3>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          {items.map((item) => (
            <div key={item.label} style={{
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              padding: '10px 14px', borderRadius: 'var(--radius-xs)',
              background: item.highlight ? 'var(--teal-bg-subtle)' : 'transparent',
              border: item.highlight ? '1px solid var(--border)' : 'none',
            }}>
              <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>{item.label}</span>
              <span style={{
                fontFamily: "'JetBrains Mono', monospace", fontSize: '0.9rem',
                fontWeight: item.highlight ? 700 : 400,
                color: item.highlight ? 'var(--teal-light)' : 'var(--text-primary)',
              }}>
                {item.value}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Deduccion ciega nota */}
      {d.deduccion_ciega_aplicada && d.comparacion_deduccion && (
        <div className="card" style={{ background: 'var(--teal-bg-subtle)', border: '1px solid var(--border)' }}>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
            {d.comparacion_deduccion}
          </p>
        </div>
      )}

      {/* Explicación LLM */}
      {resultado.explicacion && (
        <div className="card" style={{
          background: 'var(--purple-bg-subtle)', border: '1px solid var(--purple-muted)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
            <MessageSquare size={16} color="var(--purple-light)" />
            <h3 style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--purple-light)' }}>Explicación</h3>
          </div>
          <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', lineHeight: 1.7, whiteSpace: 'pre-wrap' }}>
            {resultado.explicacion}
          </p>
        </div>
      )}

      {/* Advertencias */}
      {resultado.advertencias && resultado.advertencias.length > 0 && (
        <div className="card" style={{ background: 'var(--teal-bg-subtle)', border: '1px solid var(--warning-border)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
            <AlertTriangle size={16} color="var(--warning)" />
            <h3 style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--warning)' }}>Advertencias</h3>
          </div>
          <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 8 }}>
            {resultado.advertencias.map((a, i) => (
              <li key={i} style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', paddingLeft: 8, borderLeft: '2px solid var(--warning)' }}>
                {a}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Recomendaciones */}
      {resultado.recomendaciones && resultado.recomendaciones.length > 0 && (
        <div className="card" style={{ background: 'var(--teal-bg-subtle)', border: '1px solid var(--teal-bg)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
            <Lightbulb size={16} color="var(--teal-light)" />
            <h3 style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--teal-light)' }}>Recomendaciones</h3>
          </div>
          <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 8 }}>
            {resultado.recomendaciones.map((r, i) => (
              <li key={i} style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', paddingLeft: 8, borderLeft: '2px solid var(--teal-light)' }}>
                {r}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Acciones */}
      <div style={{ display: 'flex', justifyContent: 'center', gap: 12, marginTop: 8 }}>
        <button className="btn-primary" onClick={handleDescargarPDF} style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
          <Download size={16} /> Descargar PDF
        </button>
        <button className="btn-secondary" onClick={onNuevaDeclaracion} style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
          <RefreshCw size={16} /> Nueva declaración
        </button>
      </div>
    </div>
  );
}
