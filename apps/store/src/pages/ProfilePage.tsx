/**
 * Perfil del usuario. Para un despacho, E-05 lo reduce a lo que de verdad usa.
 *
 * EL SELECTOR DE TIPO SE OCULTA POR EL PERFIL **GUARDADO**, NO POR EL LOCAL
 * -------------------------------------------------------------------------
 * `tipo` es estado local y cambia con un clic. Si la condición colgara de él,
 * un CONTRIBUYENTE que clickeara "Despacho / Contador" por curiosidad vería
 * desaparecer el selector completo en ese mismo render, sin haber guardado nada
 * y sin forma de volver salvo recargando. Colgándola de `profile.contributorType`
 * el selector sólo desaparece para quien ya ES un despacho.
 *
 * A un despacho no se le piden RFC, régimen, actividad ni código postal: no
 * declara por sí mismo en esta app (§D21). `handleSave` **sigue mandando esos
 * campos** desde `form` aunque no se pinten, para no repetir la pérdida
 * silenciosa que cazó la mutación de E-01.
 */

import { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { useProfile } from '../context/ProfileContext';
import { getProfileByType } from '../services/contributorProfiles';
import type { ContributorType } from '../services/contributorProfiles';
import { esContador } from '../services/navigation';
import { modoEmpresaUnica } from '../services/modoEmpresa';
import { useCartera } from '../context/carteraStore';
import TarjetaEmpresa from '../components/empresa/TarjetaEmpresa';
import TipoDeCuenta from '../components/perfil/TipoDeCuenta';
import TarjetaPlan from '../components/perfil/TarjetaPlan';
import { Save, User } from 'lucide-react';

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
    nombreDespacho: profile.nombreDespacho,
  });

  const selectedProfile = tipo ? getProfileByType(tipo) : null;
  // Del perfil GUARDADO, no del estado local. Ver el encabezado del archivo.
  const esDespacho = esContador(profile.contributorType);
  const empresaUnica = modoEmpresaUnica();
  // O-01: la Configuración de empresa lee y escribe el MISMO documento que la
  // cartera (`users/{uid}/clientes/empresa`), así que sale de aquí y no de un
  // estado local: dos copias del mismo dato fiscal es lo que R-07 vino a cerrar.
  const cartera = useCartera();

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
        <h1>
          {esDespacho
            ? empresaUnica
              ? 'Perfil y empresa'
              : 'Perfil del despacho'
            : 'Perfil del contribuyente'}
        </h1>
        <p>
          {esDespacho
            ? empresaUnica
              ? 'Tus datos y los de la empresa cuya nómina llevas.'
              : 'Los datos de tu despacho. Los de cada cliente se llevan por separado.'
            : 'Estos datos se usan para calcular tus declaraciones correctamente.'}
        </p>
      </div>

      <TipoDeCuenta esOperadorDeNomina={esDespacho} tipo={tipo} setTipo={setTipo} />

      {/* T8: plan y uso. Sólo para quien OPERA la nómina —un contribuyente no
          tiene cartera y "0 / 25 clientes" no le describe nada—, y colgado del
          perfil GUARDADO como el resto de la pantalla: con el `tipo` local
          aparecería y desaparecería con un clic en el selector de arriba. */}
      {esDespacho && (
        <TarjetaPlan
          plan={profile.plan}
          clientes={cartera.clientes.length}
          conCartera={!empresaUnica}
        />
      )}

      {/* O-01: los datos patronales de la empresa única. Sólo para quien opera
          la nómina: un contribuyente no tiene empresa que configurar. */}
      {empresaUnica && esDespacho && (
        <div className="animate-in" style={{ marginBottom: 24 }}>
          <TarjetaEmpresa cartera={cartera} />
        </div>
      )}

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
            {/* Actividad y CP son del contribuyente: a un despacho no se le
                calcula ninguna declaración propia, así que no se le piden. */}
            {!esDespacho && (
              <>
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
              </>
            )}
          </div>
        </div>

        {/* Datos fiscales — o del despacho, que no son lo mismo */}
        <div className="card animate-in" style={{ animationDelay: '0.2s' }}>
          <h3 style={{ fontSize: '1.05rem', fontWeight: 600, marginBottom: 24 }}>
            {esDespacho ? (empresaUnica ? 'Datos fiscales' : 'Datos del despacho') : 'Datos fiscales'}
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {esDespacho ? (
              <>
                {/* O-01: en modo empresa única el nombre del patrón es la RAZÓN
                    SOCIAL y vive arriba, en Configuración de empresa, junto al
                    RFC y al registro patronal. Pintarlo también aquí crearía
                    dos nombres para el mismo patrón. */}
                {!empresaUnica && (
                  <div>
                    <label style={labelStyle}>Nombre del despacho</label>
                    <input className="input-field" placeholder="Despacho Contable Ejemplo"
                      value={form.nombreDespacho}
                      onChange={(e) => handleChange('nombreDespacho', e.target.value)} />
                  </div>
                )}
                <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', margin: 0 }}>
                  {empresaUnica
                    ? 'Los datos fiscales de la empresa se capturan arriba, en Configuración de empresa. La app no calcula las declaraciones de ISR e IVA de la empresa.'
                    : 'El RFC y el régimen que importan son los de cada cliente, no los del despacho: la app no calcula tus declaraciones propias.'}
                </p>
              </>
            ) : (
            <>
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
