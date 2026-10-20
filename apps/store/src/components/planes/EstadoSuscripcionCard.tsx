/**
 * Estado de la suscripción del despacho y lo que hoy está bloqueado, con su motivo (P5-08).
 *
 * Los motivos los escribe el backend (`bloqueos`): aquí no se deduce ningún límite, se pinta
 * lo que el backend hace cumplir. El aviso de solo lectura va arriba y en `role="alert"`
 * porque explica por qué nada se puede guardar en el resto de la app.
 */

import { AlertTriangle, Lock } from 'lucide-react';
import {
  NOMBRE_ESTADO, fechaCorta, type ResumenSuscripcion,
} from '../../services/suscripcionApi';

const COLOR_ESTADO: Record<string, string> = {
  prueba: 'var(--teal-light)',
  activa: 'var(--success)',
  morosa: 'var(--warning)',
  vencida: 'var(--danger)',
  cancelada: 'var(--text-secondary)',
};

export default function EstadoSuscripcionCard({
  resumen, puedeCancelar, cancelando, onCancelar,
}: {
  resumen: ResumenSuscripcion;
  puedeCancelar: boolean;
  cancelando: boolean;
  onCancelar: () => void;
}) {
  const s = resumen.suscripcion;
  const { uso, bloqueos } = resumen;

  return (
    <div className="card animate-in" style={{ display: 'grid', gap: 'var(--space-sm)' }}>
      {s.solo_lectura && (
        <p role="alert" style={{
          display: 'flex', gap: 8, alignItems: 'flex-start', margin: 0,
          color: 'var(--danger)', fontSize: '0.88rem', fontWeight: 600,
        }}>
          <Lock size={16} style={{ flexShrink: 0, marginTop: 2 }} /> {s.aviso}
        </p>
      )}

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-md)', alignItems: 'baseline' }}>
        <div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 1 }}>
            Tu plan
          </div>
          <div style={{ fontWeight: 700, fontSize: '1.15rem' }}>{s.plan_nombre}</div>
        </div>
        <span data-testid="estado-suscripcion" style={{
          fontSize: '0.75rem', fontWeight: 600, padding: '2px 10px',
          borderRadius: 'var(--radius-full)', border: `1px solid ${COLOR_ESTADO[s.estado]}`,
          color: COLOR_ESTADO[s.estado],
        }}>
          {NOMBRE_ESTADO[s.estado]}
        </span>
        <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
          {s.estado === 'prueba' ? 'Prueba hasta' : 'Periodo hasta'} {fechaCorta(s.fin_periodo)}
        </span>
        <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', fontFamily: "'JetBrains Mono', monospace" }}>
          {uso.clientes} clientes · {uso.usuarios} usuarios
          {uso.invitaciones_pendientes > 0 && ` (+${uso.invitaciones_pendientes} invitaciones)`}
        </span>
      </div>

      {!s.solo_lectura && s.aviso && (
        <p role="status" style={{ margin: 0, fontSize: '0.85rem', color: 'var(--warning)' }}>{s.aviso}</p>
      )}
      {s.plan_pendiente && (
        <p role="status" style={{ margin: 0, fontSize: '0.85rem', color: 'var(--warning)' }}>
          Tu cambio al plan {s.plan_pendiente} se aplica en cuanto se confirme el primer pago.
        </p>
      )}

      {bloqueos.filter((b) => b.tipo !== 'solo_lectura').length > 0 && (
        <div>
          <div style={{ fontSize: '0.8rem', fontWeight: 600, marginBottom: 4 }}>Bloqueado por tu plan</div>
          <ul aria-label="Bloqueos del plan" style={{ listStyle: 'none', padding: 0, margin: 0, display: 'grid', gap: 4 }}>
            {bloqueos.filter((b) => b.tipo !== 'solo_lectura').map((b) => (
              <li key={b.tipo} style={{ display: 'flex', gap: 8, fontSize: '0.83rem', color: 'var(--text-secondary)' }}>
                <AlertTriangle size={14} color="var(--warning)" style={{ flexShrink: 0, marginTop: 3 }} />
                {b.motivo}
              </li>
            ))}
          </ul>
        </div>
      )}

      {puedeCancelar && (
        <div>
          <button className="btn-secondary" onClick={onCancelar} disabled={cancelando}>
            {cancelando ? 'Cancelando…' : 'Cancelar suscripción'}
          </button>
        </div>
      )}
    </div>
  );
}
