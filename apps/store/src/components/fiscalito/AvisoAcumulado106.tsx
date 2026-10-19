/**
 * Estado del acumulado del Art. 106 LISR en la pre-declaración (612/606, mes > 1).
 * Salió de `PreDeclaracionTab` (P1-06) para dejar ese archivo bajo 300 líneas; el
 * texto y las condiciones son los mismos.
 */

import { AlertCircle, CheckCircle, Loader } from 'lucide-react';

const MESES = [
  'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
  'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre',
];

export interface Acumulado106 {
  ingresos_acumulados: number;
  deducciones_acumuladas: number;
  isr_pagado_anterior: number;
  meses_encontrados: number[];
  meses_faltantes: number[];
}

const caja = (fondo: string, borde: string): React.CSSProperties => ({
  padding: '12px 16px', borderRadius: 'var(--radius-md)', background: fondo,
  border: `1px solid ${borde}`, display: 'flex', alignItems: 'flex-start', gap: 10,
});
const texto: React.CSSProperties = { fontSize: '0.82rem', color: 'var(--text-secondary)', lineHeight: 1.5 };
const meses = (ms: number[]) => ms.map((m) => MESES[m - 1]).join(', ');

export default function AvisoAcumulado106({ cargando, acumulado }: { cargando: boolean; acumulado: Acumulado106 | null }) {
  if (cargando) {
    return (
      <div style={{ ...caja('var(--teal-bg-subtle)', 'var(--border-hover)'), alignItems: 'center', ...texto }}>
        <Loader size={14} className="spin" /> Cargando datos de meses anteriores…
      </div>
    );
  }
  if (!acumulado || acumulado.meses_encontrados.length === 0) {
    return (
      <div style={caja('var(--warning-bg)', 'var(--warning-border)')}>
        <AlertCircle size={16} color="var(--warning)" style={{ flexShrink: 0, marginTop: 2 }} />
        <div style={texto}>
          No se encontraron declaraciones anteriores de este ejercicio.
          Se calculará solo con datos de este mes (tabla simple).
        </div>
      </div>
    );
  }
  if (acumulado.meses_faltantes.length > 0) {
    return (
      <div style={caja('var(--warning-bg)', 'var(--warning-border)')}>
        <AlertCircle size={16} color="var(--warning)" style={{ flexShrink: 0, marginTop: 2 }} />
        <div style={texto}>
          Faltan pre-declaraciones de{' '}
          <strong style={{ color: 'var(--text-primary)' }}>{meses(acumulado.meses_faltantes)}</strong>.
          El cálculo será parcial. Calcula esos meses primero para mayor precisión.
        </div>
      </div>
    );
  }
  return (
    <div style={caja('var(--success-bg)', 'var(--success-border)')}>
      <CheckCircle size={16} color="var(--success)" style={{ flexShrink: 0, marginTop: 2 }} />
      <div style={texto}>
        <strong style={{ color: 'var(--text-primary)' }}>Art. 106</strong> — Datos de{' '}
        {meses(acumulado.meses_encontrados)} cargados automáticamente desde tu historial.
      </div>
    </div>
  );
}
