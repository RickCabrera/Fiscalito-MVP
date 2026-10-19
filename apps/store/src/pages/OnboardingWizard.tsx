/**
 * Wizard de onboarding post-registro.
 *
 * K (2026-10-19): el sistema es SOLO para despachos y contadores. No hay paso
 * de "tipo": toda cuenta queda como `contador`. Se piden tres datos —contador,
 * despacho y teléfono—; los fiscales son de cada cliente (§D21).
 *
 * Una cuenta vieja de contribuyente también cae aquí (ver `isOnboardingComplete`
 * en `ProfileContext`): al terminar el wizard queda convertida en despacho. Sus
 * campos de contribuyente (RFC, régimen…) se vacían para que nada los lea como
 * si fueran del despacho.
 */

import { useState } from 'react';
import { useNavigate, Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useProfile } from '../context/ProfileContext';
import { rutaInicial } from '../services/navigation';
import { ArrowLeft, ArrowRight, Check, Loader } from 'lucide-react';

import WizardProgress from '../components/onboarding/WizardProgress';
import StepDatosDespacho from '../components/onboarding/StepDatosDespacho';
import StepConfirmar from '../components/onboarding/StepConfirmar';
import { MARCA, MARCA_LOGO } from '../services/marca';

/** Un paso del wizard. El id es lo que manda; el índice sólo ordena. */
type PasoId = 'despacho' | 'confirmar';

const PASOS: PasoId[] = ['despacho', 'confirmar'];
const ETIQUETAS: Record<PasoId, string> = {
  despacho: 'Datos del despacho',
  confirmar: 'Confirmar',
};

export default function OnboardingWizard() {
  const navigate = useNavigate();
  const { user, loading: authLoading } = useAuth();
  const { profile, setProfile, loading: profileLoading, isOnboardingComplete } = useProfile();
  const [step, setStep] = useState(0);
  const [saving, setSaving] = useState(false);

  const eraContribuyente =
    profile.onboardingComplete && profile.contributorType !== 'contador';

  const [nombreDespacho, setNombreDespacho] = useState(profile.nombreDespacho ?? '');
  const [nombre, setNombre] = useState(profile.nombre ?? '');
  const [telefono, setTelefono] = useState(profile.telefono ?? '');

  const pasoActual = PASOS[step];
  const esUltimo = step >= PASOS.length - 1;

  const canNext = (): boolean =>
    pasoActual !== 'despacho' || (nombre.trim() !== '' && nombreDespacho.trim() !== '');

  const handleFinish = async () => {
    setSaving(true);
    try {
      // Los campos de contribuyente viajan VACÍOS, no ausentes: `setProfile`
      // hace merge, y una cuenta convertida conservaría su RFC propio.
      await setProfile({
        contributorType: 'contador',
        nombre, telefono, nombreDespacho,
        rfc: '', regimen: '', actividad: '', cp: '', nombreNegocio: '', numEmpleados: '',
        onboardingComplete: true,
      });
      navigate(rutaInicial());
    } catch {
      setSaving(false);
    }
  };

  if (authLoading || profileLoading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100vh' }}>
        <Loader size={28} className="spin" color="var(--teal-light)" />
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  if (isOnboardingComplete()) {
    return <Navigate to="/app" replace />;
  }

  return (
    <div style={{
      minHeight: '100vh',
      background: 'var(--bg-dark)',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
    }}>
      {/* Header */}
      <div style={{ padding: '32px 24px 0', width: '100%', maxWidth: 720, textAlign: 'center' }}>
        <div style={{ fontSize: '1.3rem', fontWeight: 700, marginBottom: 8 }}>
          <span className="gradient-text">{MARCA_LOGO}</span>
        </div>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
          Configuremos el perfil de tu despacho
        </p>
      </div>

      {eraContribuyente && (
        <p role="status" style={{
          maxWidth: 672, margin: '16px 24px 0', padding: '12px 16px',
          background: 'var(--warning-bg)', border: '1px solid var(--warning-border)',
          borderRadius: 'var(--radius-sm)', fontSize: '0.88rem', color: 'var(--text-primary)',
        }}>
          Esta plataforma ahora es solo para despachos y contadores. Completa estos
          datos para convertir tu cuenta en una cuenta de despacho.
        </p>
      )}

      <WizardProgress pasos={PASOS.map((p) => ETIQUETAS[p])} currentStep={step} />

      {/* Step content */}
      <div style={{ flex: 1, width: '100%', maxWidth: 720, padding: '40px 24px' }}>
        <div className="animate-in" key={pasoActual}>
          {pasoActual === 'despacho' && (
            <StepDatosDespacho
              nombre={nombre} setNombre={setNombre}
              nombreDespacho={nombreDespacho} setNombreDespacho={setNombreDespacho}
              telefono={telefono} setTelefono={setTelefono}
            />
          )}
          {pasoActual === 'confirmar' && (
            <StepConfirmar nombre={nombre} nombreDespacho={nombreDespacho} telefono={telefono} />
          )}
        </div>
      </div>

      {/* Navigation buttons */}
      <div style={{
        width: '100%', maxWidth: 720, padding: '0 24px 40px',
        display: 'flex', justifyContent: 'space-between',
      }}>
        <button
          onClick={() => setStep((s) => s - 1)}
          style={{
            display: 'flex', alignItems: 'center', gap: 8,
            padding: '12px 24px', background: 'transparent',
            border: '1px solid var(--border)', borderRadius: 'var(--radius-full)',
            color: 'var(--text-secondary)', fontSize: '0.9rem', fontWeight: 500,
            cursor: 'pointer', visibility: step === 0 ? 'hidden' : 'visible',
            transition: 'all 0.2s',
          }}
        >
          <ArrowLeft size={16} /> Atras
        </button>

        {!esUltimo ? (
          <button
            className="btn-primary"
            disabled={!canNext()}
            onClick={() => setStep((s) => s + 1)}
            style={{
              display: 'flex', alignItems: 'center', gap: 8,
              opacity: canNext() ? 1 : 0.4,
              cursor: canNext() ? 'pointer' : 'not-allowed',
            }}
          >
            Siguiente <ArrowRight size={16} />
          </button>
        ) : (
          <button
            className="btn-primary"
            onClick={handleFinish}
            disabled={saving}
            style={{ display: 'flex', alignItems: 'center', gap: 8, opacity: saving ? 0.7 : 1 }}
          >
            <Check size={16} /> {saving ? 'Guardando...' : `Comenzar a usar ${MARCA}`}
          </button>
        )}
      </div>
    </div>
  );
}
