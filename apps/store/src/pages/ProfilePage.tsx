/**
 * Perfil del despacho.
 *
 * K (2026-10-19): el sistema es solo para despachos, así que no hay selector de
 * tipo de cuenta ni datos fiscales propios. A un despacho no se le piden RFC,
 * régimen, actividad ni código postal: el sujeto del cálculo es cada cliente
 * (`docs/decisiones-nomina.md` §D21).
 */

import { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useProfile } from '../context/ProfileContext';
import { useCartera } from '../context/carteraStore';
import TarjetaPlan from '../components/perfil/TarjetaPlan';
import { Link } from 'react-router-dom';
import { ScrollText, UsersRound, Save, User } from 'lucide-react';

export default function ProfilePage() {
  const { user } = useAuth();
  const { profile, setProfile } = useProfile();
  const cartera = useCartera();
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);

  const [form, setForm] = useState({
    nombre: profile.nombre || user?.displayName || '',
    telefono: profile.telefono,
    nombreDespacho: profile.nombreDespacho,
  });

  const handleChange = (field: keyof typeof form, value: string) => {
    setForm((f) => ({ ...f, [field]: value }));
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await setProfile({
        nombre: form.nombre,
        telefono: form.telefono,
        nombreDespacho: form.nombreDespacho,
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch {
      // error is set in context
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="page-container">
      <div className="page-header animate-in">
        <h1>Perfil del despacho</h1>
        <p>Los datos de tu despacho. Los de cada cliente se llevan por separado.</p>
      </div>

      <TarjetaPlan plan={profile.plan} clientes={cartera.clientes.length} />

      {/* P0-07: la bitácora se entra desde aquí, no desde el sidebar (como Planes). */}
      <Link
        to="/app/auditoria"
        className="card animate-in"
        style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 24, color: 'var(--text-primary)' }}
      >
        <ScrollText size={18} color="var(--accent-active)" />
        <span style={{ fontWeight: 600 }}>Bitácora de auditoría</span>
        <span style={{ fontSize: '0.83rem', color: 'var(--text-secondary)' }}>
          Quién hizo cada cambio en el despacho, a qué cliente y cuándo.
        </span>
      </Link>

      {/* P5-01: el equipo del despacho (usuarios, invitaciones, roles y asignaciones). */}
      <Link
        to="/app/equipo"
        className="card animate-in"
        style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 24, color: 'var(--text-primary)' }}
      >
        <UsersRound size={18} color="var(--accent-active)" />
        <span style={{ fontWeight: 600 }}>Equipo del despacho</span>
        <span style={{ fontSize: '0.83rem', color: 'var(--text-secondary)' }}>
          Invita usuarios, asigna roles y decide qué clientes ve cada auxiliar.
        </span>
      </Link>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 24 }}>
        <div className="card animate-in" style={{ animationDelay: '0.1s' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 24 }}>
            <div style={{
              width: 44, height: 44, borderRadius: '50%',
              background: 'var(--accent-gradient)', display: 'flex',
              alignItems: 'center', justifyContent: 'center',
            }}>
              <User size={20} color="white" />
            </div>
            <div>
              <h3 style={{ fontSize: '1.05rem', fontWeight: 600 }}>Datos del contador</h3>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{user?.email}</p>
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div>
              <label style={labelStyle}>Nombre completo</label>
              <input className="input-field" placeholder="Tu nombre" value={form.nombre}
                onChange={(e) => handleChange('nombre', e.target.value)} />
            </div>
            <div>
              <label style={labelStyle}>Telefono</label>
              <input className="input-field" placeholder="10 digitos" value={form.telefono}
                onChange={(e) => handleChange('telefono', e.target.value)} />
            </div>
          </div>
        </div>

        <div className="card animate-in" style={{ animationDelay: '0.2s' }}>
          <h3 style={{ fontSize: '1.05rem', fontWeight: 600, marginBottom: 24 }}>Datos del despacho</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div>
              <label style={labelStyle}>Nombre del despacho</label>
              <input className="input-field" placeholder="Despacho Contable Ejemplo"
                value={form.nombreDespacho}
                onChange={(e) => handleChange('nombreDespacho', e.target.value)} />
            </div>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', margin: 0 }}>
              El RFC y el régimen que importan son los de cada cliente, no los del despacho:
              se capturan en Clientes.
            </p>
          </div>
        </div>
      </div>

      <div className="animate-in" style={{ animationDelay: '0.3s', marginTop: 24, display: 'flex', gap: 12, alignItems: 'center' }}>
        <button className="btn-primary" onClick={handleSave} disabled={saving}
          style={{ display: 'inline-flex', alignItems: 'center', gap: 8, opacity: saving ? 0.7 : 1 }}>
          <Save size={16} /> {saving ? 'Guardando...' : 'Guardar cambios'}
        </button>
        {saved && (
          <span style={{ color: 'var(--success)', fontSize: '0.85rem', fontWeight: 500 }}>
            Guardado correctamente
          </span>
        )}
      </div>
    </div>
  );
}

const labelStyle: React.CSSProperties = {
  display: 'block',
  fontSize: '0.83rem',
  color: 'var(--text-secondary)',
  marginBottom: 6,
};
