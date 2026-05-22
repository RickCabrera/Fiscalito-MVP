import { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { useProfile } from '../context/ProfileContext';
import { CONTRIBUTOR_TYPES, getProfileByType } from '../services/contributorProfiles';
import type { ContributorType } from '../services/contributorProfiles';
import { Save, User, Check } from 'lucide-react';

const NUM_EMPLEADOS_OPTIONS = ['Solo yo', '2-5', '6-20', '21+'];

export default function ProfilePage() {
  const { user } = useAuth();
  const { profile, setProfile } = useProfile();
  const [saved, setSaved] = useState(false);

  const [tipo, setTipo] = useState<ContributorType | null>(profile.contributorType);
  const [form, setForm] = useState({
    nombre: profile.nombre || user?.displayName || '',
    rfc: profile.rfc,
    regimen: profile.regimen,
    actividad: profile.actividad,
    cp: profile.cp,
    telefono: profile.telefono,
    nombreNegocio: profile.nombreNegocio,
    numEmpleados: profile.numEmpleados,
  });

  const selectedProfile = tipo ? getProfileByType(tipo) : null;

  // Reset regimen when tipo changes if current regimen is not in allowed list
  useEffect(() => {
    if (selectedProfile && form.regimen) {
      const allowed = selectedProfile.allowedRegimens.map((r) => r.code);
      if (!allowed.includes(form.regimen)) {
        setForm((f) => ({ ...f, regimen: '' }));
      }
    }
  }, [tipo]);

  const handleChange = (field: string, value: string) => {
    setForm((f) => ({ ...f, [field]: value }));
  };

  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    setSaving(true);
    try {
      await setProfile({
        contributorType: tipo,
        nombre: form.nombre,
        rfc: form.rfc,
        regimen: form.regimen,
        actividad: form.actividad,
        cp: form.cp,
        telefono: form.telefono,
        nombreNegocio: form.nombreNegocio,
        numEmpleados: form.numEmpleados,
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
        <h1>Perfil del contribuyente</h1>
        <p>Estos datos se usan para calcular tus declaraciones correctamente.</p>
      </div>

      {/* Tipo de contribuyente */}
      <div className="card animate-in" style={{ marginBottom: 24 }}>
        <h3 style={{ fontSize: '1.05rem', fontWeight: 600, marginBottom: 16 }}>Tipo de contribuyente</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 10 }}>
          {CONTRIBUTOR_TYPES.map((ct) => {
            const selected = tipo === ct.id;
            return (
              <button
                key={ct.id}
                onClick={() => setTipo(ct.id)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  padding: '12px 14px',
                  background: selected ? 'var(--nav-active-bg)' : 'var(--bg-input)',
                  border: `1.5px solid ${selected ? 'var(--teal-light)' : 'var(--border)'}`,
                  borderRadius: 'var(--radius-sm)',
                  color: 'var(--text-primary)',
                  textAlign: 'left',
                  cursor: 'pointer',
                  transition: 'all 0.2s',
                  position: 'relative',
                }}
              >
                <span style={{ fontSize: '1.2rem' }}>{ct.icon}</span>
                <span style={{ fontSize: '0.85rem', fontWeight: selected ? 600 : 400 }}>{ct.label}</span>
                {selected && (
                  <Check size={14} style={{ marginLeft: 'auto', color: 'var(--teal-light)' }} />
                )}
              </button>
            );
          })}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>
        {/* Personal info */}
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
              <h3 style={{ fontSize: '1.05rem', fontWeight: 600 }}>Datos personales</h3>
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
            <div>
              <label style={labelStyle}>Actividad economica</label>
              <input className="input-field" placeholder="Ej: Diseno grafico, Consultoria..." value={form.actividad}
                onChange={(e) => handleChange('actividad', e.target.value)} />
            </div>
            <div>
              <label style={labelStyle}>Codigo postal (domicilio fiscal)</label>
              <input className="input-field" placeholder="00000" value={form.cp}
                onChange={(e) => handleChange('cp', e.target.value)} maxLength={5}
                style={{ fontFamily: "'JetBrains Mono', monospace", letterSpacing: 2 }} />
            </div>
          </div>
        </div>

        {/* Fiscal info */}
        <div className="card animate-in" style={{ animationDelay: '0.2s' }}>
          <h3 style={{ fontSize: '1.05rem', fontWeight: 600, marginBottom: 24 }}>Datos fiscales</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div>
              <label style={labelStyle}>RFC</label>
              <input className="input-field" placeholder="XAXX010101000" value={form.rfc}
                onChange={(e) => handleChange('rfc', e.target.value.toUpperCase())}
                maxLength={13} style={{ fontFamily: "'JetBrains Mono', monospace", letterSpacing: 1 }} />
            </div>
            <div>
              <label style={labelStyle}>Regimen fiscal</label>
              <select className="input-field" value={form.regimen}
                onChange={(e) => handleChange('regimen', e.target.value)}
                style={{ cursor: 'pointer' }}>
                <option value="">Seleccionar regimen...</option>
                {selectedProfile ? (
                  selectedProfile.allowedRegimens.map((r) => (
                    <option key={r.code} value={r.code}>{r.code} — {r.name}</option>
                  ))
                ) : (
                  <>
                    <option value="626">626 — RESICO</option>
                    <option value="612">612 — Actividad Empresarial y Profesional</option>
                    <option value="605">605 — Sueldos y Salarios</option>
                    <option value="606">606 — Arrendamiento</option>
                    <option value="625">625 — Plataformas Tecnologicas</option>
                    <option value="621">621 — Incorporacion Fiscal (RIF)</option>
                  </>
                )}
              </select>
              {!tipo && (
                <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: 4, display: 'block' }}>
                  Selecciona un tipo de contribuyente para filtrar regimenes
                </span>
              )}
            </div>

            {/* PYME extra fields */}
            {tipo === 'pyme' && (
              <>
                <div>
                  <label style={labelStyle}>Nombre del negocio</label>
                  <input className="input-field" placeholder="Mi Empresa S.A. de C.V."
                    value={form.nombreNegocio}
                    onChange={(e) => handleChange('nombreNegocio', e.target.value)} />
                </div>
                <div>
                  <label style={labelStyle}>Numero de empleados</label>
                  <select className="input-field" value={form.numEmpleados}
                    onChange={(e) => handleChange('numEmpleados', e.target.value)}
                    style={{ cursor: 'pointer' }}>
                    <option value="">Seleccionar...</option>
                    {NUM_EMPLEADOS_OPTIONS.map((opt) => (
                      <option key={opt} value={opt}>{opt}</option>
                    ))}
                  </select>
                </div>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Save button */}
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
