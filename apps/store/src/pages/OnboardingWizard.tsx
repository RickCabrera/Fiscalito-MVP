/**
 * Wizard de onboarding post-registro (E-05: los pasos dependen del tipo).
 *
 * UN DESPACHO RECORRE TRES PASOS, UN CONTRIBUYENTE CUATRO
 * ------------------------------------------------------
 * Y **todo** se decide contra la lista de ids, no contra el índice: el render,
 * `canNext`, el botón "Atrás" y —sobre todo— cuál es el último paso. Con el
 * `step < 3` que estaba cableado, un wizard de tres pasos dejaba al contador en
 * "Confirmar" viendo "Siguiente", y `handleFinish` no se ejecutaba nunca: no se
 * creaba la cuenta.
 *
 * A un despacho no se le piden RFC, régimen, actividad ni código postal: no
 * declara por sí mismo en esta app, el sujeto del cálculo es su cliente. La
 * consecuencia está declarada en `docs/decisiones-nomina.md` §D21.
 */

import { useState } from 'react';
import { useNavigate, Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useProfile } from '../context/ProfileContext';
import { getProfileByType } from '../services/contributorProfiles';
import { rutaInicial, esContador } from '../services/navigation';
import { modoEmpresaUnica } from '../services/modoEmpresa';
import type { ContributorType } from '../services/contributorProfiles';
import { ArrowLeft, ArrowRight, Check, Loader } from 'lucide-react';

import WizardProgress from '../components/onboarding/WizardProgress';
import StepTipo from '../components/onboarding/StepTipo';
import StepDatosFiscales from '../components/onboarding/StepDatosFiscales';
import StepDatosDespacho from '../components/onboarding/StepDatosDespacho';
import StepDatosPersonales from '../components/onboarding/StepDatosPersonales';
import StepConfirmar from '../components/onboarding/StepConfirmar';

/** Un paso del wizard. El id es lo que manda; el índice sólo ordena. */
type PasoId = 'tipo' | 'fiscales' | 'despacho' | 'personales' | 'confirmar';

const ETIQUETA: Record<PasoId, string> = {
  tipo: 'Tipo',
  fiscales: 'Datos fiscales',
  despacho: 'Datos del despacho',
  personales: 'Datos personales',
  confirmar: 'Confirmar',
};

const PASOS_CONTADOR: PasoId[] = ['tipo', 'despacho', 'confirmar'];
const PASOS_CONTRIBUYENTE: PasoId[] = ['tipo', 'fiscales', 'personales', 'confirmar'];

function pasosDelTipo(tipo: ContributorType | null): PasoId[] {
  return esContador(tipo) ? PASOS_CONTADOR : PASOS_CONTRIBUYENTE;
}

export default function OnboardingWizard() {
  const navigate = useNavigate();
  const { user, loading: authLoading } = useAuth();
  const { setProfile, loading: profileLoading, isOnboardingComplete } = useProfile();
  const [step, setStep] = useState(0);
  const [saving, setSaving] = useState(false);

  // Form state
  const [tipo, setTipo] = useState<ContributorType | null>(null);
  const [rfc, setRfc] = useState('');
  const [regimen, setRegimen] = useState('');
  const [nombreNegocio, setNombreNegocio] = useState('');
  const [numEmpleados, setNumEmpleados] = useState('');
  const [nombreDespacho, setNombreDespacho] = useState('');
  const [nombre, setNombre] = useState('');
  const [telefono, setTelefono] = useState('');
  const [actividad, setActividad] = useState('');
  const [cp, setCp] = useState('');

  const selectedProfile = tipo ? getProfileByType(tipo) : null;
  const esDespacho = esContador(tipo);
  const pasos = pasosDelTipo(tipo);
  // El índice puede quedar fuera de rango si el tipo cambia de 4 pasos a 3: se
  // acota, en vez de dejar `pasos[step]` en `undefined`.
  const pasoActual = pasos[Math.min(step, pasos.length - 1)];
  const esUltimo = step >= pasos.length - 1;

  /** Qué falta para avanzar. Decidido por ID de paso, nunca por índice. */
  const canNext = (): boolean => {
    switch (pasoActual) {
      case 'tipo':
        return tipo !== null;
      case 'fiscales': {
        const rfcValid = rfc.length === 12 || rfc.length === 13;
        const pymeValid = tipo !== 'pyme' || (nombreNegocio.trim() !== '' && numEmpleados !== '');
        return rfcValid && regimen !== '' && pymeValid;
      }
      case 'despacho':
        // O-01: en modo empresa única el paso no pinta "nombre del despacho"
        // —la razón social es dato fiscal y se captura en Configuración de
        // empresa—, así que exigirlo aquí dejaría "Siguiente" apagado para
        // siempre sobre un campo que no existe en la pantalla. Es el mismo
        // defecto de E-05 (`step < 3` cableado) por la puerta de al lado: la
        // condición tiene que seguir a lo que de verdad se renderiza.
        return (
          nombre.trim() !== '' && (modoEmpresaUnica() || nombreDespacho.trim() !== '')
        );
      case 'personales':
        return nombre.trim() !== '';
      default:
        return true;
    }
  };

  const handleFinish = async () => {
    setSaving(true);
    try {
      // Los campos que el despacho no llenó viajan vacíos, no ausentes: el
      // perfil tiene una forma fija y `setProfile` hace merge sobre lo previo.
      await setProfile({
        contributorType: tipo,
        rfc, regimen, nombre, telefono, actividad, cp,
        nombreNegocio, numEmpleados, nombreDespacho,
        onboardingComplete: true,
      });
      // Un despacho entra a sus clientes, no al dashboard de contribuyente.
      navigate(rutaInicial(tipo));
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
          <span className="gradient-text">Fiscalito</span>{' '}
          <span style={{ color: 'var(--text-muted)', fontWeight: 400 }}>Store</span>
        </div>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
          {esDespacho ? 'Configuremos el perfil de tu despacho' : 'Configuremos tu perfil de contribuyente'}
        </p>
      </div>

      <WizardProgress pasos={pasos.map((p) => ETIQUETA[p])} currentStep={step} />

      {/* Step content */}
      <div style={{ flex: 1, width: '100%', maxWidth: 720, padding: '40px 24px' }}>
        <div className="animate-in" key={pasoActual}>
          {pasoActual === 'tipo' && <StepTipo tipo={tipo} setTipo={setTipo} />}
          {pasoActual === 'fiscales' && selectedProfile && (
            <StepDatosFiscales
              allowedRegimens={selectedProfile.allowedRegimens}
              rfc={rfc} setRfc={setRfc}
              regimen={regimen} setRegimen={setRegimen}
              nombreNegocio={nombreNegocio} setNombreNegocio={setNombreNegocio}
              numEmpleados={numEmpleados} setNumEmpleados={setNumEmpleados}
              isPyme={tipo === 'pyme'}
            />
          )}
          {pasoActual === 'despacho' && (
            <StepDatosDespacho
              nombre={nombre} setNombre={setNombre}
              nombreDespacho={nombreDespacho} setNombreDespacho={setNombreDespacho}
              telefono={telefono} setTelefono={setTelefono}
            />
          )}
          {pasoActual === 'personales' && (
            <StepDatosPersonales
              nombre={nombre} setNombre={setNombre}
              telefono={telefono} setTelefono={setTelefono}
              actividad={actividad} setActividad={setActividad}
              cp={cp} setCp={setCp}
            />
          )}
          {pasoActual === 'confirmar' && selectedProfile && (
            <StepConfirmar
              tipoLabel={selectedProfile.label}
              tipoIcon={selectedProfile.icon}
              allowedRegimens={selectedProfile.allowedRegimens}
              esContador={esDespacho}
              rfc={rfc} regimen={regimen} nombre={nombre}
              telefono={telefono} actividad={actividad} cp={cp}
              nombreNegocio={nombreNegocio} numEmpleados={numEmpleados}
              nombreDespacho={nombreDespacho}
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
            <Check size={16} /> {saving ? 'Guardando...' : 'Comenzar a usar Fiscalito Store'}
          </button>
        )}
      </div>
    </div>
  );
}
