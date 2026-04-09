/** Wizard de onboarding post-registro — orquesta los 4 pasos de configuracion del perfil */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useProfile } from '../context/ProfileContext';
import { getProfileByType } from '../services/contributorProfiles';
import type { ContributorType } from '../services/contributorProfiles';
import { ArrowLeft, ArrowRight, Check } from 'lucide-react';

import WizardProgress from '../components/onboarding/WizardProgress';
import StepTipo from '../components/onboarding/StepTipo';
import StepDatosFiscales from '../components/onboarding/StepDatosFiscales';
import StepDatosPersonales from '../components/onboarding/StepDatosPersonales';
import StepConfirmar from '../components/onboarding/StepConfirmar';

export default function OnboardingWizard() {
  const navigate = useNavigate();
  const { setProfile } = useProfile();
  const [step, setStep] = useState(0);
  const [saving, setSaving] = useState(false);

  // Form state
  const [tipo, setTipo] = useState<ContributorType | null>(null);
  const [rfc, setRfc] = useState('');
  const [regimen, setRegimen] = useState('');
  const [nombreNegocio, setNombreNegocio] = useState('');
  const [numEmpleados, setNumEmpleados] = useState('');
  const [nombre, setNombre] = useState('');
  const [telefono, setTelefono] = useState('');
  const [actividad, setActividad] = useState('');
  const [cp, setCp] = useState('');

  const selectedProfile = tipo ? getProfileByType(tipo) : null;

  const canNext = (): boolean => {
    if (step === 0) return tipo !== null;
    if (step === 1) {
      const rfcValid = rfc.length === 12 || rfc.length === 13;
      const regimenValid = regimen !== '';
      const pymeValid = tipo !== 'pyme' || (nombreNegocio.trim() !== '' && numEmpleados !== '');
      return rfcValid && regimenValid && pymeValid;
    }
    if (step === 2) return nombre.trim() !== '';
    return true;
  };

  const handleFinish = async () => {
    setSaving(true);
    try {
      await setProfile({
        contributorType: tipo,
        rfc, regimen, nombre, telefono, actividad, cp,
        nombreNegocio, numEmpleados,
        onboardingComplete: true,
      });
      navigate('/app');
    } catch {
      setSaving(false);
    }
  };

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
          <span className="gradient-text">Fiscalito</span>{' '}
          <span style={{ color: 'var(--text-muted)', fontWeight: 400 }}>Store</span>
        </div>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
          Configuremos tu perfil de contribuyente
        </p>
      </div>

      <WizardProgress currentStep={step} />

      {/* Step content */}
      <div style={{ flex: 1, width: '100%', maxWidth: 720, padding: '40px 24px' }}>
        <div className="animate-in" key={step}>
          {step === 0 && <StepTipo tipo={tipo} setTipo={setTipo} />}
          {step === 1 && selectedProfile && (
            <StepDatosFiscales
              allowedRegimens={selectedProfile.allowedRegimens}
              rfc={rfc} setRfc={setRfc}
              regimen={regimen} setRegimen={setRegimen}
              nombreNegocio={nombreNegocio} setNombreNegocio={setNombreNegocio}
              numEmpleados={numEmpleados} setNumEmpleados={setNumEmpleados}
              isPyme={tipo === 'pyme'}
            />
          )}
          {step === 2 && (
            <StepDatosPersonales
              nombre={nombre} setNombre={setNombre}
              telefono={telefono} setTelefono={setTelefono}
              actividad={actividad} setActividad={setActividad}
              cp={cp} setCp={setCp}
            />
          )}
          {step === 3 && selectedProfile && (
            <StepConfirmar
              tipoLabel={selectedProfile.label}
              tipoIcon={selectedProfile.icon}
              allowedRegimens={selectedProfile.allowedRegimens}
              rfc={rfc} regimen={regimen} nombre={nombre}
              telefono={telefono} actividad={actividad} cp={cp}
              nombreNegocio={nombreNegocio} numEmpleados={numEmpleados}
            />
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

        {step < 3 ? (
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
            <Check size={16} /> {saving ? 'Guardando...' : 'Comenzar a usar Fiscalito Store'}
          </button>
        )}
      </div>
    </div>
  );
}
