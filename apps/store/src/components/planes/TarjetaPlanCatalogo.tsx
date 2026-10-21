/**
 * Un plan del catálogo del backend con su precio, límites, módulos y la acción (P5-08).
 *
 * "Lo que bloquearía" se avisa ANTES de elegir: bajar a un plan más chico no borra nada,
 * sólo impide altas, y el usuario decide con ese dato enfrente.
 */

import { Check } from 'lucide-react';
import { textoPrecio, type PlanCatalogo } from '../../services/suscripcionApi';

export type AccionPlan = 'suscribirse' | 'cambiar' | null;

export default function TarjetaPlanCatalogo({
  plan, actual, accion, ocupado, onElegir,
}: {
  plan: PlanCatalogo;
  actual: boolean;
  /** null = no se puede hacer nada con este plan (no es dueño, o ya es el plan con cobro). */
  accion: AccionPlan;
  ocupado: boolean;
  onElegir: () => void;
}) {
  const etiqueta = accion === 'suscribirse' ? 'Suscribirme' : 'Cambiar a este plan';

  return (
    <div
      className="card"
      aria-label={`Plan ${plan.nombre}`}
      style={{
        display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)',
        border: `1.5px solid ${actual ? 'var(--accent-active)' : 'var(--border)'}`,
        background: actual ? 'var(--accent-active-bg)' : 'var(--bg-card)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-xs)', flexWrap: 'wrap' }}>
        <h3 style={{ fontSize: '1.15rem', fontWeight: 700 }}>{plan.nombre}</h3>
        {actual && (
          <span style={{
            fontSize: '0.7rem', fontWeight: 600, letterSpacing: 0.3, padding: '2px 8px',
            borderRadius: 'var(--radius-full)', background: 'var(--accent-active)',
            color: 'var(--text-on-accent)',
          }}>
            TU PLAN
          </span>
        )}
      </div>

      <div style={{ fontSize: '1.2rem', fontWeight: 700, fontFamily: "'JetBrains Mono', monospace" }}>
        {textoPrecio(plan)}
      </div>

      <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'grid', gap: 6 }}>
        {[`Hasta ${plan.max_clientes} clientes`,
          plan.max_usuarios === 1 ? '1 usuario' : `Hasta ${plan.max_usuarios} usuarios`,
          ...plan.modulos.map((m) => m.nombre)].map((linea) => (
          <li key={linea} style={{ display: 'flex', gap: 8, alignItems: 'flex-start', fontSize: '0.85rem' }}>
            <Check size={14} color="var(--teal-light)" style={{ flexShrink: 0, marginTop: 3 }} />
            <span style={{ color: 'var(--text-secondary)' }}>{linea}</span>
          </li>
        ))}
      </ul>

      {!actual && plan.bloquearia.map((b) => (
        <p key={b.tipo} role="status" style={{ fontSize: '0.78rem', color: 'var(--warning)', margin: 0 }}>
          {b.motivo}
        </p>
      ))}

      {accion && (
        <button className="btn-primary" onClick={onElegir} disabled={ocupado} style={{ marginTop: 'auto' }}>
          {ocupado ? 'Guardando…' : etiqueta}
        </button>
      )}
      {!accion && actual && (
        <button className="btn-secondary" disabled style={{ marginTop: 'auto' }}>Plan actual</button>
      )}
    </div>
  );
}
