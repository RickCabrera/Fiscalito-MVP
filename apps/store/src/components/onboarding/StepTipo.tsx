/** Step 1: Selector de tipo de contribuyente con cards visuales */

import { Check } from 'lucide-react';
import { CONTRIBUTOR_TYPES } from '../../services/contributorProfiles';
import type { ContributorType } from '../../services/contributorProfiles';

interface StepTipoProps {
  tipo: ContributorType | null;
  setTipo: (t: ContributorType) => void;
}

export default function StepTipo({ tipo, setTipo }: StepTipoProps) {
  return (
    <div>
      <h2 style={{ fontSize: '1.4rem', fontWeight: 700, marginBottom: 8 }}>
        ¿Que tipo de contribuyente eres?
      </h2>
      <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: 32 }}>
        Esto nos permite mostrarte solo los servicios y obligaciones que aplican a tu situacion.
      </p>

      <div style={{ display: 'grid', gap: 12 }}>
        {CONTRIBUTOR_TYPES.map((ct) => {
          const selected = tipo === ct.id;
          return (
            <button
              key={ct.id}
              onClick={() => setTipo(ct.id)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 16,
                padding: '20px 24px',
                background: selected ? 'rgba(110, 159, 160, 0.08)' : 'var(--bg-card)',
                border: `1.5px solid ${selected ? 'var(--teal-light)' : 'var(--border)'}`,
                borderRadius: 'var(--radius)',
                color: 'var(--text-primary)',
                textAlign: 'left',
                cursor: 'pointer',
                transition: 'all 0.2s',
              }}
            >
              <div style={{
                width: 52, height: 52, borderRadius: 'var(--radius-sm)',
                background: selected ? 'var(--accent-gradient)' : 'var(--bg-input)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: '1.5rem', flexShrink: 0,
                transition: 'background 0.2s',
              }}>
                {ct.icon}
              </div>
              <div>
                <div style={{ fontWeight: 600, fontSize: '1.05rem', marginBottom: 2 }}>
                  {ct.label}
                </div>
                <div style={{ fontSize: '0.83rem', color: 'var(--text-secondary)' }}>
                  {ct.description}
                </div>
              </div>
              {selected && (
                <div style={{
                  marginLeft: 'auto',
                  width: 24, height: 24, borderRadius: '50%',
                  background: 'var(--teal-light)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  flexShrink: 0,
                }}>
                  <Check size={14} color="var(--bg-dark)" />
                </div>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
