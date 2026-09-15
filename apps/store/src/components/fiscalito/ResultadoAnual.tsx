/**
 * Resultado de la declaración anual (T3).
 *
 * DOS NÚMEROS QUE NO SE SUMAN EN PANTALLA
 * ---------------------------------------
 * El desglose sale de `POST /api/v1/pre-declaracion-anual` y el efecto de las
 * deducciones personales de `POST /api/v1/deducciones-personales`: dos llamadas
 * al motor, dos respuestas. Esta pantalla las pinta **una junto a otra y no las
 * resta**. Restarlas sería inventar aquí una línea de cálculo que el motor no
 * devolvió, y el `CLAUDE.md` raíz reserva el cálculo fiscal al motor. Por eso el
 * banner de abajo dice de frente que el ISR del desglose todavía no las aplica.
 */

import type { PreDeclaracionResponse, DeduccionesPersonalesResponse } from '../../services/fiscalAgentApi';
import { exportarDeclaracionPDF } from '../../services/pdfExport';
import { formatMoney } from '../../utils/format';
import { AlertTriangle, Download, Info, Lightbulb, MessageSquare, RefreshCw } from 'lucide-react';

interface Props {
  resultado: PreDeclaracionResponse;
  deducciones: DeduccionesPersonalesResponse | null;
  contribuyente: { nombre: string; rfc: string };
  guardado: boolean;
  onNueva: () => void;
}

const FILA: React.CSSProperties = {
  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
  padding: '10px 14px', borderRadius: 'var(--radius-xs)',
};

const MONTO: React.CSSProperties = { fontFamily: "'JetBrains Mono', monospace", fontSize: '0.9rem' };

export default function ResultadoAnual({ resultado, deducciones, contribuyente, guardado, onNueva }: Props) {
  const d = resultado.desglose;
  const esAFavor = d.total_a_pagar < 0;

  const handlePDF = () => {
    exportarDeclaracionPDF({
      periodo: resultado.periodo,
      tipo: resultado.tipo_declaracion,
      regimen: resultado.regimen,
      desglose: d,
      explicacion: resultado.explicacion ?? null,
      advertencias: resultado.advertencias ?? [],
      recomendaciones: resultado.recomendaciones ?? [],
      contribuyente,
      fechaCalculo: new Date(),
      deducciones: deducciones
        ? {
            desglose: deducciones.desglose,
            total_antes_tope: deducciones.total_antes_tope,
            tope_global: deducciones.tope_global,
            tope_tipo: deducciones.tope_tipo,
            total_deducible: deducciones.total_deducible,
            excedente_no_aprovechado: deducciones.excedente_no_aprovechado,
            saldo_a_favor_estimado: deducciones.saldo_a_favor_estimado,
          }
        : null,
      titulo: 'Declaración anual',
      prefijoArchivo: 'DeclaracionAnual',
    });
  };

  const items: { label: string; value: string; highlight?: boolean }[] = [
    { label: 'Ingresos facturados', value: formatMoney(d.total_ingresos_facturados) },
    { label: 'Ingresos gravados', value: formatMoney(d.total_ingresos_gravados) },
    ...(d.total_deducciones_autorizadas ? [{ label: 'Deducciones autorizadas', value: formatMoney(d.total_deducciones_autorizadas) }] : []),
    ...(d.total_egresos ? [{ label: 'Egresos', value: formatMoney(d.total_egresos) }] : []),
    { label: 'Base ISR del ejercicio', value: formatMoney(d.base_isr) },
    { label: 'Tasa ISR', value: `${(d.tasa_isr * 100).toFixed(2)}%` },
    { label: 'ISR causado', value: formatMoney(d.isr_causado) },
    ...(d.isr_retenido ? [{ label: 'ISR retenido', value: formatMoney(d.isr_retenido) }] : []),
    { label: 'ISR a pagar', value: formatMoney(d.isr_a_pagar), highlight: true },
    ...(d.iva_trasladado_cobrado != null ? [{ label: 'IVA cobrado', value: formatMoney(d.iva_trasladado_cobrado) }] : []),
    ...(d.iva_trasladado_pagado != null ? [{ label: 'IVA pagado (acreditable)', value: formatMoney(d.iva_trasladado_pagado) }] : []),
    { label: 'IVA a pagar', value: formatMoney(d.iva_a_pagar), highlight: true },
  ];

  return (
    <div className="animate-in" style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div className="card" style={{
        textAlign: 'center',
        background: esAFavor
          ? 'linear-gradient(135deg, var(--success-bg), var(--teal-bg))'
          : 'linear-gradient(135deg, var(--purple-bg), var(--purple-bg-subtle))',
        border: `1px solid ${esAFavor ? 'var(--success-border)' : 'var(--border-hover)'}`,
      }}>
        <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 8 }}>
          {resultado.periodo} — {resultado.regimen}
        </div>
        <div style={{
          fontSize: '2.4rem', fontWeight: 800, fontFamily: "'JetBrains Mono', monospace",
          color: esAFavor ? 'var(--success)' : 'var(--text-primary)',
        }}>
          {esAFavor
            ? `${formatMoney(Math.abs(d.total_a_pagar))} a favor`
            : formatMoney(d.total_a_pagar)}
        </div>
        <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: 4 }}>
          {esAFavor ? 'Saldo a favor estimado del ejercicio' : 'Total estimado del ejercicio (ISR + IVA)'}
          {deducciones ? ', antes de deducciones personales' : ''}
        </div>
      </div>

      {guardado && (
        <div style={{ fontSize: '0.8rem', color: 'var(--success)' }}>
          Guardada en tu historial como declaración anual.
        </div>
      )}

      <div className="card">
        <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: 16 }}>Desglose del ejercicio</h3>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          {items.map((item) => (
            <div key={item.label} style={{
              ...FILA,
              background: item.highlight ? 'var(--teal-bg-subtle)' : 'transparent',
              border: item.highlight ? '1px solid var(--border)' : 'none',
            }}>
              <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>{item.label}</span>
              <span style={{
                ...MONTO,
                fontWeight: item.highlight ? 700 : 400,
                color: item.highlight ? 'var(--teal-light)' : 'var(--text-primary)',
              }}>{item.value}</span>
            </div>
          ))}
        </div>
      </div>

      {deducciones && (
        <div className="card">
          <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: 6 }}>Deducciones personales</h3>
          <div style={{
            display: 'flex', alignItems: 'flex-start', gap: 8, marginBottom: 14,
            padding: '10px 14px', borderRadius: 'var(--radius-xs)',
            background: 'var(--warning-bg)', border: '1px solid var(--warning-border)',
          }}>
            <Info size={14} color="var(--warning)" style={{ flexShrink: 0, marginTop: 2 }} />
            <span style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
              El ISR del desglose de arriba <strong>todavía no descuenta</strong> estas deducciones.
              El efecto se calcula aparte, sobre la base del ejercicio, y es el renglón
              &ldquo;Efecto estimado en ISR&rdquo;.
            </span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {deducciones.desglose.map((dd) => (
              <div key={dd.concepto} style={{ ...FILA, padding: '8px 14px' }}>
                <span style={{ fontSize: '0.83rem', color: 'var(--text-secondary)' }}>
                  {dd.concepto}
                  {dd.tope_aplicable != null && dd.monto_aceptado < dd.monto_solicitado && (
                    <span style={{ color: 'var(--warning)', fontSize: '0.75rem' }}> · topado</span>
                  )}
                </span>
                <span style={{ ...MONTO, fontSize: '0.83rem' }}>{formatMoney(dd.monto_aceptado)}</span>
              </div>
            ))}
            <div style={{ ...FILA, background: 'var(--teal-bg-subtle)', border: '1px solid var(--border)' }}>
              <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                Total deducible (tope {deducciones.tope_tipo}: {formatMoney(deducciones.tope_global)})
              </span>
              <span style={{ ...MONTO, fontWeight: 700, color: 'var(--teal-light)' }}>
                {formatMoney(deducciones.total_deducible)}
              </span>
            </div>
            {deducciones.excedente_no_aprovechado > 0 && (
              <div style={{ ...FILA, padding: '8px 14px' }}>
                <span style={{ fontSize: '0.83rem', color: 'var(--text-muted)' }}>Excedente no aprovechado</span>
                <span style={{ ...MONTO, fontSize: '0.83rem', color: 'var(--text-muted)' }}>
                  {formatMoney(deducciones.excedente_no_aprovechado)}
                </span>
              </div>
            )}
            <div style={{ ...FILA, background: 'var(--success-bg)', border: '1px solid var(--success-border)' }}>
              <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Efecto estimado en ISR</span>
              <span style={{ ...MONTO, fontWeight: 700, color: 'var(--success)' }}>
                {formatMoney(deducciones.saldo_a_favor_estimado)} a favor
              </span>
            </div>
          </div>
        </div>
      )}

      {resultado.explicacion && (
        <div className="card" style={{ background: 'var(--purple-bg-subtle)', border: '1px solid var(--purple-muted)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
            <MessageSquare size={16} color="var(--purple-light)" />
            <h3 style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--purple-light)' }}>Explicación</h3>
          </div>
          <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', lineHeight: 1.7, whiteSpace: 'pre-wrap' }}>
            {resultado.explicacion}
          </p>
        </div>
      )}

      {(resultado.advertencias ?? []).length > 0 && (
        <div className="card" style={{ background: 'var(--teal-bg-subtle)', border: '1px solid var(--warning-border)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
            <AlertTriangle size={16} color="var(--warning)" />
            <h3 style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--warning)' }}>Advertencias</h3>
          </div>
          <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 8 }}>
            {resultado.advertencias?.map((a, i) => (
              <li key={i} style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', paddingLeft: 8, borderLeft: '2px solid var(--warning)' }}>{a}</li>
            ))}
          </ul>
        </div>
      )}

      {(resultado.recomendaciones ?? []).length > 0 && (
        <div className="card" style={{ background: 'var(--teal-bg-subtle)', border: '1px solid var(--teal-bg)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
            <Lightbulb size={16} color="var(--teal-light)" />
            <h3 style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--teal-light)' }}>Recomendaciones</h3>
          </div>
          <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 8 }}>
            {resultado.recomendaciones?.map((r, i) => (
              <li key={i} style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', paddingLeft: 8, borderLeft: '2px solid var(--teal-light)' }}>{r}</li>
            ))}
          </ul>
        </div>
      )}

      <div style={{ display: 'flex', justifyContent: 'center', gap: 12, marginTop: 8 }}>
        <button className="btn-primary" onClick={handlePDF} style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
          <Download size={16} /> Descargar PDF
        </button>
        <button className="btn-secondary" onClick={onNueva} style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
          <RefreshCw size={16} /> Nueva declaración anual
        </button>
      </div>
    </div>
  );
}
