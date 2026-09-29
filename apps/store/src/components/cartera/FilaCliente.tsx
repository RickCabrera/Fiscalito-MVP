/**
 * Un renglón de la cartera: la tarjeta que abre la ficha y, al lado, "Editar" (C-01).
 *
 * La tarjeta salió de `ClientesPage` sin cambios cuando C-01 le agregó el botón
 * de editar y la página pasó del tope de 300 líneas. "Editar" va AL LADO y no
 * dentro, porque la tarjeta ya es un <button> y un botón dentro de otro no es
 * HTML válido.
 */

import { Building2, ChevronRight, Pencil, Users } from 'lucide-react';
import type { ClienteCartera } from '../../services/carteraApi';
import { etiquetaOrigen, primaComoPorcentaje } from '../../services/despachoApi';

function TarjetaCliente({
  cliente, activo, onAbrir,
}: { cliente: ClienteCartera; activo: boolean; onAbrir: () => void }) {
  return (
    <button
      onClick={onAbrir}
      className="card"
      style={{
        display: 'flex', alignItems: 'center', gap: 'var(--space-md)', width: '100%',
        padding: 'var(--space-md) var(--space-lg)', textAlign: 'left', cursor: 'pointer',
        border: `1.5px solid ${activo ? 'var(--accent-active)' : 'var(--border)'}`,
        background: activo ? 'var(--accent-active-bg)' : 'var(--bg-card)',
        color: 'var(--text-primary)',
      }}
    >
      <div
        style={{
          width: 44, height: 44, borderRadius: 'var(--radius-sm)', flexShrink: 0,
          background: 'var(--accent-gradient)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}
      >
        <Building2 size={20} color="var(--text-on-accent)" />
      </div>

      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-xs)', flexWrap: 'wrap' }}>
          <span style={{ fontWeight: 600, fontSize: '1rem' }}>{cliente.nombre}</span>
          {activo && (
            <span
              style={{
                fontSize: '0.7rem', fontWeight: 600, letterSpacing: 0.3,
                padding: '2px 8px', borderRadius: 'var(--radius-full)',
                background: 'var(--accent-active)', color: 'var(--text-on-accent)',
              }}
            >
              ACTIVO
            </span>
          )}
        </div>
        <div style={{ fontSize: '0.83rem', color: 'var(--text-secondary)', marginTop: 2 }}>
          {cliente.giro} · {etiquetaOrigen(cliente.origen)}
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-lg)', flexShrink: 0 }}>
        <div style={{ textAlign: 'right' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, justifyContent: 'flex-end' }}>
            <Users size={14} color="var(--text-muted)" />
            <span style={{ fontWeight: 600, fontFamily: "'JetBrains Mono', monospace" }}>
              {cliente.empleados.length}
            </span>
          </div>
          <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>empleados</div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontWeight: 600, fontFamily: "'JetBrains Mono', monospace", fontSize: '0.9rem' }}>
            {primaComoPorcentaje(cliente.prima_riesgo)}
          </div>
          <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>prima de RT</div>
        </div>
        <ChevronRight size={18} color="var(--text-muted)" />
      </div>
    </button>
  );
}

export default function FilaCliente({
  cliente, activo, editable, onAbrir, onEditar,
}: {
  cliente: ClienteCartera;
  activo: boolean;
  editable: boolean;
  onAbrir: () => void;
  onEditar: () => void;
}) {
  return (
    <div style={{ display: 'flex', gap: 'var(--space-xs)', alignItems: 'stretch' }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <TarjetaCliente cliente={cliente} activo={activo} onAbrir={onAbrir} />
      </div>
      {editable && (
        <button
          className="btn-secondary"
          aria-label={`Editar ${cliente.nombre}`}
          title="Editar datos del cliente"
          onClick={onEditar}
          style={{ display: 'inline-flex', alignItems: 'center' }}
        >
          <Pencil size={16} />
        </button>
      )}
    </div>
  );
}
