import { useParams, Link, useNavigate } from 'react-router-dom';
import { getServiceById } from '../services/storeServices';
import { ArrowLeft, ExternalLink, Check, Code, Zap } from 'lucide-react';

export default function ServiceDetailPage() {
  const { serviceId } = useParams();
  const navigate = useNavigate();
  const service = getServiceById(serviceId || '');

  if (!service) {
    return (
      <div className="page-container">
        <p>Servicio no encontrado.</p>
        <Link to="/app"><button className="btn-secondary">Volver al inicio</button></Link>
      </div>
    );
  }

  return (
    <div className="page-container">
      {/* Back */}
      <Link to="/app" style={{ display: 'inline-flex', alignItems: 'center', gap: 6, color: 'var(--text-primary)', fontSize: '0.85rem', marginBottom: 24 }}>
        <ArrowLeft size={16} /> Dashboard
      </Link>

      {/* Hero */}
      <div className="animate-in" style={{ display: 'flex', alignItems: 'flex-start', gap: 24, marginBottom: 40 }}>
        <div style={{
          width: 72, height: 72, borderRadius: 'var(--radius)',
          background: 'var(--accent-gradient)', display: 'flex',
          alignItems: 'center', justifyContent: 'center', fontSize: '2rem', flexShrink: 0,
        }}>
          {service.icon}
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
            <h1 style={{ fontSize: '2rem', fontWeight: 800, letterSpacing: -1 }}>{service.name}</h1>
            <span style={{
              padding: '4px 14px', borderRadius: 'var(--radius-full)',
              fontSize: '0.7rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: 1,
              background: service.status === 'active' ? 'var(--border)' : 'var(--purple-bg)',
              color: service.status === 'active' ? 'var(--teal-light)' : 'var(--purple-light)',
              border: `1px solid ${service.status === 'active' ? 'var(--border-hover)' : 'var(--purple-muted)'}`,
            }}>
              {service.status === 'active' ? 'Activo' : 'Proximamente'}
            </span>
          </div>
          <p style={{ color: 'var(--text-secondary)', fontSize: '1.05rem', lineHeight: 1.6, maxWidth: 600 }}>
            {service.description}
          </p>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>
        {/* Features */}
        <div className="card animate-in" style={{ animationDelay: '0.1s' }}>
          <h3 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: 20 }}>Funcionalidades</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {service.features.map((f, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
                <div style={{
                  width: 22, height: 22, borderRadius: '50%', flexShrink: 0,
                  background: 'var(--border)', display: 'flex',
                  alignItems: 'center', justifyContent: 'center', marginTop: 1,
                }}>
                  <Check size={12} color="var(--teal-light)" />
                </div>
                <span style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>{f}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Technical info */}
        <div className="card animate-in" style={{ animationDelay: '0.2s' }}>
          <h3 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: 20 }}>Informacion tecnica</h3>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 4 }}>
                Categoria
              </div>
              <div style={{ fontSize: '0.95rem', textTransform: 'capitalize' }}>{service.category}</div>
            </div>

            {service.apiEndpoint && (
              <div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 4 }}>
                  API Endpoint
                </div>
                <code style={{
                  fontFamily: "'JetBrains Mono', monospace", fontSize: '0.85rem',
                  padding: '6px 12px', background: 'var(--bg-input)', borderRadius: 'var(--radius-xs)',
                  color: 'var(--teal-light)', display: 'inline-block',
                }}>
                  {service.apiEndpoint}
                </code>
              </div>
            )}

            <div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 4 }}>
                Stack
              </div>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                {['FastAPI', 'Python', 'OpenAI / Anthropic', 'Cloud Run'].map((t) => (
                  <span key={t} style={{
                    padding: '4px 10px', borderRadius: 'var(--radius-full)',
                    background: 'var(--purple-bg)', color: 'var(--purple-light)',
                    fontSize: '0.75rem', fontWeight: 500,
                  }}>
                    {t}
                  </span>
                ))}
              </div>
            </div>
          </div>

          {/* Action buttons */}
          <div style={{ display: 'flex', gap: 12, marginTop: 28 }}>
            {service.id === 'fiscalito' && (
              <button className="btn-primary" onClick={() => navigate('/app/store/fiscalito/use')}
                style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
                <Zap size={16} /> Usar Fiscalito
              </button>
            )}
            {service.status === 'active' && service.apiEndpoint && (
              <a href={`${service.apiEndpoint}/docs`} target="_blank" rel="noopener noreferrer">
                <button className="btn-secondary" style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
                  <Code size={16} /> Abrir API docs
                </button>
              </a>
            )}
            {service.externalUrl && (
              <a href={service.externalUrl} target="_blank" rel="noopener noreferrer">
                <button className="btn-secondary" style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
                  <ExternalLink size={16} /> Abrir app
                </button>
              </a>
            )}
          </div>
        </div>
      </div>

      {/* API Demo section for Fiscalito */}
      {service.id === 'fiscalito' && (
        <div className="card animate-in" style={{ animationDelay: '0.3s', marginTop: 24, overflow: 'hidden', padding: 0 }}>
          <div style={{
            padding: '16px 24px', borderBottom: '1px solid var(--border)',
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          }}>
            <h3 style={{ fontSize: '0.95rem', fontWeight: 600 }}>POST /api/v1/pre-declaracion</h3>
            <div style={{ display: 'flex', gap: 6 }}>
              <span style={{ width: 10, height: 10, borderRadius: '50%', background: '#ff5f56' }} />
              <span style={{ width: 10, height: 10, borderRadius: '50%', background: '#ffbd2e' }} />
              <span style={{ width: 10, height: 10, borderRadius: '50%', background: '#27c93f' }} />
            </div>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr' }}>
            <div style={{
              padding: 20, borderRight: '1px solid var(--border)',
              fontFamily: "'JetBrains Mono', monospace", fontSize: '0.72rem', lineHeight: 1.8,
              background: 'var(--purple-bg-subtle)', whiteSpace: 'pre',
            }}>
              <div style={{ fontFamily: 'Outfit', fontSize: '0.7rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: 1.5, color: 'var(--text-muted)', marginBottom: 10 }}>Request</div>
{`{
  "contribuyente": {
    "rfc": "CAUA030101ABC",
    "regimen": "626"
  },
  "facturas": [{
    "subtotal": 15000.00,
    "iva_trasladado": 2400.00,
    "isr_retenido": 1500.00
  }],
  "periodo_month": 1,
  "incluir_explicacion": true
}`}
            </div>
            <div style={{
              padding: 20,
              fontFamily: "'JetBrains Mono', monospace", fontSize: '0.72rem', lineHeight: 1.8,
              background: 'var(--teal-bg-subtle)', whiteSpace: 'pre',
            }}>
              <div style={{ fontFamily: 'Outfit', fontSize: '0.7rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: 1.5, color: 'var(--text-muted)', marginBottom: 10 }}>Response</div>
{`{
  "tipo_declaracion": "mensual",
  "desglose": {
    "ingresos": 15000.00,
    "tasa_isr": "1.00%",
    "isr_causado": 150.00,
    "isr_retenido": 1500.00,
    "isr_a_pagar": 0.00,
    "saldo_favor": 1350.00
  },
  "explicacion": "Tus clientes
  retuvieron mas de lo que debes.
  Saldo a favor: $1,350"
}`}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
