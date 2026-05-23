import { Link } from 'react-router-dom';
import { ArrowRight, Shield, Cpu, Layers } from 'lucide-react';
import { SERVICES } from '../services/storeServices';

export default function LandingPage() {
  return (
    <div style={{ background: 'var(--bg-dark)', minHeight: '100vh', position: 'relative', overflow: 'hidden' }}>
      {/* Ambient glows */}
      <div style={{ position: 'fixed', width: 500, height: 500, borderRadius: '50%', background: 'var(--purple-muted)', filter: 'blur(120px)', top: -100, left: -100, pointerEvents: 'none' }} />
      <div style={{ position: 'fixed', width: 400, height: 400, borderRadius: '50%', background: 'var(--teal-muted)', filter: 'blur(120px)', bottom: -50, right: -50, pointerEvents: 'none' }} />

      <div style={{ position: 'relative', zIndex: 2, maxWidth: 1100, margin: '0 auto', padding: '0 24px' }}>
        {/* Nav */}
        <nav style={{ padding: '20px 0', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ fontSize: '1.2rem', fontWeight: 700 }}>
            <span className="gradient-text">Fiscalito</span>{' '}
            <span style={{ color: 'var(--text-muted)', fontWeight: 400 }}>Store</span>
          </div>
          <div style={{ display: 'flex', gap: 12 }}>
            <Link to="/login"><button className="btn-secondary">Iniciar sesion</button></Link>
            <Link to="/login"><button className="btn-primary">Registrarse</button></Link>
          </div>
        </nav>

        {/* Hero */}
        <section style={{ padding: '120px 0 80px', textAlign: 'center' }}>
          <h1 className="animate-in" style={{ fontSize: 'clamp(2.5rem, 5vw, 3.8rem)', fontWeight: 800, letterSpacing: -2, lineHeight: 1.1, marginBottom: 20 }}>
            Servicios inteligentes<br />para <span className="gradient-text">PYMEs mexicanas</span>
          </h1>
          <p className="animate-in" style={{ animationDelay: '0.15s', fontSize: '1.1rem', color: 'var(--text-secondary)', maxWidth: 580, margin: '0 auto 40px', lineHeight: 1.7 }}>
            Marketplace de microservicios que automatizan tus obligaciones fiscales, laborales y contables. Cada servicio calcula como contador y explica como maestro.
          </p>
          <div className="animate-in" style={{ animationDelay: '0.3s', display: 'flex', gap: 12, justifyContent: 'center' }}>
            <Link to="/login"><button className="btn-primary" style={{ fontSize: '1rem', padding: '14px 32px' }}>Comenzar gratis <ArrowRight size={18} style={{ marginLeft: 6, verticalAlign: 'middle' }} /></button></Link>
          </div>

          {/* Stats */}
          <div className="animate-in" style={{ animationDelay: '0.4s', display: 'flex', justifyContent: 'center', gap: 56, marginTop: 64 }}>
            {[
              { n: '4.9M', l: 'MiPYMEs en Mexico' },
              { n: '<2 min', l: 'Por declaracion' },
              { n: '95%+', l: 'Precision vs contador' },
            ].map((s, i) => (
              <div key={i} style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '2rem', fontWeight: 700, fontFamily: "'JetBrains Mono', monospace", color: 'var(--teal-light)' }}>{s.n}</div>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 1, marginTop: 4 }}>{s.l}</div>
              </div>
            ))}
          </div>
        </section>

        {/* Value props */}
        <section style={{ padding: '60px 0', display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 20 }}>
          {[
            { icon: <Cpu size={24} />, title: 'Motor deterministico', desc: 'Los calculos fiscales usan tablas ISR oficiales codificadas. No dependemos del LLM para los numeros.' },
            { icon: <Layers size={24} />, title: 'Modular y escalable', desc: 'Cada servicio es un microservicio independiente. Activa solo lo que necesitas, paga solo lo que usas.' },
            { icon: <Shield size={24} />, title: 'Privacidad por diseno', desc: 'El Fiscal Agent es stateless: no almacena tus datos. Todo se procesa en el request y se devuelve.' },
          ].map((v, i) => (
            <div key={i} className="card" style={{ textAlign: 'center', padding: 32 }}>
              <div style={{ color: 'var(--teal-light)', marginBottom: 16, display: 'flex', justifyContent: 'center' }}>{v.icon}</div>
              <h3 style={{ fontSize: '1.05rem', fontWeight: 600, marginBottom: 8 }}>{v.title}</h3>
              <p style={{ fontSize: '0.88rem', color: 'var(--text-secondary)', lineHeight: 1.6 }}>{v.desc}</p>
            </div>
          ))}
        </section>

        {/* Services preview */}
        <section style={{ padding: '40px 0 80px' }}>
          <h2 style={{ fontSize: '1.8rem', fontWeight: 700, textAlign: 'center', marginBottom: 40, letterSpacing: -0.5 }}>
            Nuestros servicios
          </h2>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 20 }}>
            {SERVICES.map((s) => (
              <div key={s.id} className="card" style={{
                opacity: s.status === 'coming_soon' ? 0.5 : 1,
                textAlign: 'center', padding: 32,
              }}>
                <div style={{ fontSize: '2rem', marginBottom: 12 }}>{s.icon}</div>
                <h3 style={{ fontWeight: 700, marginBottom: 6 }}>{s.name}</h3>
                <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>{s.tagline}</p>
                <span style={{
                  display: 'inline-block', marginTop: 12,
                  padding: '4px 12px', borderRadius: 'var(--radius-full)',
                  fontSize: '0.7rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: 1,
                  background: s.status === 'active' ? 'var(--border)' : 'var(--purple-bg)',
                  color: s.status === 'active' ? 'var(--teal-light)' : 'var(--purple-light)',
                }}>
                  {s.status === 'active' ? 'Disponible' : 'Proximamente'}
                </span>
              </div>
            ))}
          </div>
        </section>

        {/* Footer */}
        <footer style={{ padding: '32px 0', borderTop: '1px solid var(--border)', textAlign: 'center' }}>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
            Fiscalito Store &copy; 2026 — Servicios inteligentes para PYMEs mexicanas
          </p>
        </footer>
      </div>
    </div>
  );
}
