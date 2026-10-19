/**
 * Obligaciones y tareas de un día del calendario (P3-10).
 *
 * Cada obligación dice cliente, estado (pendiente / presentada / vencida) y su fundamento en el
 * `title`; las fiscales y patronales se pueden marcar presentadas a mano. Las credenciales no:
 * se "resuelven" subiendo la renovada.
 */

import { CheckCircle2, Circle } from 'lucide-react';
import type { ObligacionCartera, TareaAgenda } from '../../services/agendaApi';

const COLOR_ESTADO: Record<ObligacionCartera['estado'], string> = {
  pendiente: 'var(--warning)', presentada: 'var(--success)', vencida: 'var(--danger)',
};

const ETIQUETA_TIPO: Record<ObligacionCartera['tipo'], string> = {
  fiscal: 'Fiscal', patronal: 'Patronal', credencial: 'e.firma/CSD',
};

interface Props {
  obligaciones: ObligacionCartera[];
  tareas: TareaAgenda[];
  compacto?: boolean;
  onMarcar?: (o: ObligacionCartera) => void;
  onTarea?: (t: TareaAgenda) => void;
}

export default function ItemsDelDia({ obligaciones, tareas, compacto = false, onMarcar, onTarea }: Props) {
  return (
    <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 4 }}>
      {obligaciones.map((o) => (
        <li key={`${o.cliente}-${o.clave}`} title={`${o.fundamento}${o.nota ? ` · ${o.nota}` : ''}`}
          style={{
            fontSize: compacto ? '0.68rem' : '0.75rem', padding: '3px 6px',
            borderLeft: `3px solid ${COLOR_ESTADO[o.estado]}`, background: 'var(--bg-card-hover)',
            borderRadius: 'var(--radius-sm)', opacity: o.estado === 'presentada' ? 0.7 : 1,
          }}>
          <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
            <span style={{ fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {o.cliente_nombre || o.cliente}
            </span>
            {onMarcar && o.tipo !== 'credencial' && (
              <button onClick={() => onMarcar(o)} aria-label={`${o.estado === 'presentada' ? 'Desmarcar' : 'Marcar presentada'}: ${o.nombre} de ${o.cliente_nombre}`}
                style={{ marginLeft: 'auto', background: 'none', border: 'none', cursor: 'pointer', color: COLOR_ESTADO[o.estado], padding: 0 }}>
                {o.estado === 'presentada' ? <CheckCircle2 size={13} /> : <Circle size={13} />}
              </button>
            )}
          </div>
          <div style={{ color: 'var(--text-secondary)' }}>
            {o.nombre}{o.condicional ? ' (verifica si aplica)' : ''}
          </div>
          {!compacto && (
            <div style={{ color: COLOR_ESTADO[o.estado], fontSize: '0.66rem', textTransform: 'uppercase' }}>
              {ETIQUETA_TIPO[o.tipo]} · {o.estado}
            </div>
          )}
        </li>
      ))}
      {tareas.map((t) => (
        <li key={`t-${t.id}`} style={{
          fontSize: compacto ? '0.68rem' : '0.75rem', padding: '3px 6px',
          border: '1px dashed var(--border)', borderRadius: 'var(--radius-sm)',
          textDecoration: t.estado === 'hecha' ? 'line-through' : 'none',
        }}>
          <button onClick={() => onTarea?.(t)} aria-label={`Tarea ${t.titulo}: ${t.estado}`}
            style={{ background: 'none', border: 'none', padding: 0, color: 'var(--text-primary)', cursor: onTarea ? 'pointer' : 'default', textAlign: 'left', font: 'inherit' }}>
            Tarea: {t.titulo}{t.cliente_nombre ? ` · ${t.cliente_nombre}` : ''}
          </button>
        </li>
      ))}
    </ul>
  );
}
