import { SERVICES } from '../services/storeServices';
import { useProfile } from '../context/ProfileContext';
import { Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';

export default function MarketplacePage() {
  const { profile } = useProfile();
  const tipo = profile.contributorType;

  // Sort: applicable services first, non-applicable after
  const sorted = [...SERVICES].sort((a, b) => {
    if (!tipo) return 0;
    const aApplies = a.appliesTo.includes(tipo);
    const bApplies = b.appliesTo.includes(tipo);
    if (aApplies && !bApplies) return -1;
    if (!aApplies && bApplies) return 1;
    return 0;
  });

  return (
    <div className="page-container">
      <div className="page-header animate-in">
        <h1>Marketplace</h1>
        <p>Activa solo los servicios que necesitas. Cada uno funciona de forma independiente.</p>
      </div>

      {/* Category filters */}
      <div className="animate-in" style={{ animationDelay: '0.1s', display: 'flex', gap: 8, marginBottom: 32 }}>
        {['Todos', 'Fiscal', 'Laboral', 'Contable'].map((cat, i) => (
          <button key={cat} style={{
            padding: '8px 20px',
            borderRadius: 'var(--radius-full)',
            border: '1px solid var(--border)',
            background: i === 0 ? 'var(--teal-bg)' : 'transparent',
            color: i === 0 ? 'var(--teal-light)' : 'var(--text-muted)',
            fontSize: '0.85rem',
            fontWeight: 500,
            cursor: 'pointer',
            transition: 'all 0.2s',
          }}>
            {cat}
          </button>
        ))}
      </div>

      {/* Service cards grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: 20 }}>
        {sorted.map((service, idx) => {
          const applies = !tipo || service.appliesTo.includes(tipo);
          const dimmed = !applies || service.status === 'coming_soon';

          return (
            <div
              key={service.id}
              className="card animate-in"
              style={{
                animationDelay: `${0.15 + idx * 0.1}s`,
                opacity: dimmed ? 0.55 : 1,
                position: 'relative',
                overflow: 'hidden',
                cursor: 'pointer',
                transition: 'all 0.3s',
              }}
              onMouseOver={(e) => {
                if (!dimmed) {
                  e.currentTarget.style.borderColor = 'var(--border-active)';
                  e.currentTarget.style.transform = 'translateY(-4px)';
                  e.currentTarget.style.boxShadow = 'var(--shadow-md)';
                }
              }}
              onMouseOut={(e) => {
                e.currentTarget.style.borderColor = 'var(--border)';
                e.currentTarget.style.transform = 'translateY(0)';
                e.currentTarget.style.boxShadow = 'none';
              }}
            >
              {/* Top accent line */}
              <div style={{
                position: 'absolute', top: 0, left: 0, right: 0, height: 3,
                background: service.status === 'active' && applies ? 'var(--accent-gradient)' : 'var(--border)',
              }} />

              {/* Badges */}
              <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
                <span style={{
                  display: 'inline-block',
                  padding: '4px 12px',
                  borderRadius: 'var(--radius-full)',
                  fontSize: '0.7rem',
                  fontWeight: 600,
                  textTransform: 'uppercase',
                  letterSpacing: 1,
                  background: service.status === 'active' ? 'var(--border)' : 'var(--purple-bg)',
                  color: service.status === 'active' ? 'var(--teal-light)' : 'var(--purple-light)',
                  border: `1px solid ${service.status === 'active' ? 'var(--border-hover)' : 'var(--purple-muted)'}`,
                }}>
                  {service.status === 'active' ? 'Disponible' : 'Proximamente'}
                </span>

                {tipo && !applies && (
                  <span style={{
                    display: 'inline-block',
                    padding: '4px 12px',
                    borderRadius: 'var(--radius-full)',
                    fontSize: '0.7rem',
                    fontWeight: 600,
                    textTransform: 'uppercase',
                    letterSpacing: 1,
                    background: 'var(--danger-bg)',
                    color: 'var(--danger)',
                    border: '1px solid var(--danger-border)',
                  }}>
                    No aplica a tu perfil
                  </span>
                )}
              </div>

              {/* Icon */}
              <div style={{
                width: 52, height: 52, borderRadius: 12,
                background: 'var(--accent-gradient)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: '1.5rem', marginBottom: 20,
              }}>
                {service.icon}
              </div>

              {/* Content */}
              <h3 style={{ fontSize: '1.3rem', fontWeight: 700, marginBottom: 8, letterSpacing: -0.5 }}>
                {service.name}
              </h3>
              <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', lineHeight: 1.6, marginBottom: 20 }}>
                {service.description}
              </p>

              {/* Features */}
              <ul style={{ listStyle: 'none', marginBottom: 24 }}>
                {service.features.slice(0, 4).map((f, i) => (
                  <li key={i} style={{
                    padding: '5px 0', fontSize: '0.83rem', color: 'var(--text-secondary)',
                    display: 'flex', alignItems: 'center', gap: 8,
                  }}>
                    <span style={{
                      width: 6, height: 6, borderRadius: '50%',
                      background: 'var(--teal-light)', flexShrink: 0,
                    }} />
                    {f}
                  </li>
                ))}
                {service.features.length > 4 && (
                  <li style={{ padding: '5px 0', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                    +{service.features.length - 4} mas...
                  </li>
                )}
              </ul>

              {/* CTA */}
              {service.status === 'active' && applies ? (
                <Link to={`/app/store/${service.id}`}>
                  <button className="btn-primary" style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
                    Ver servicio <ArrowRight size={16} />
                  </button>
                </Link>
              ) : (
                <button style={{
                  padding: '10px 24px',
                  background: 'rgba(255,255,255,0.04)',
                  border: 'none',
                  borderRadius: 'var(--radius-full)',
                  color: 'var(--text-muted)',
                  fontSize: '0.85rem',
                  fontWeight: 500,
                  cursor: 'not-allowed',
                }}>
                  {!applies ? 'No disponible' : 'Notificarme'}
                </button>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
