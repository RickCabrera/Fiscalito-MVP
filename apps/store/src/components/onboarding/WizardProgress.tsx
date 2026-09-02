/**
 * Barra de progreso del wizard con indicadores de paso.
 *
 * E-05: los pasos LLEGAN como prop. Un despacho recorre tres y un contribuyente
 * cuatro, así que una lista fija aquí pintaría un paso que nadie va a ver.
 */

interface WizardProgressProps {
  pasos: string[];
  currentStep: number;
}

export default function WizardProgress({ pasos, currentStep }: WizardProgressProps) {
  const STEPS = pasos;
  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: 8,
      padding: '32px 24px 0',
      width: '100%',
      maxWidth: 720,
    }}>
      {STEPS.map((label, i) => (
        <div key={label} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}>
          <div style={{
            width: '100%',
            height: 4,
            borderRadius: 2,
            background: i <= currentStep ? 'var(--accent-gradient)' : 'var(--border)',
            transition: 'background 0.3s',
          }} />
          <span style={{
            fontSize: '0.72rem',
            fontWeight: i === currentStep ? 600 : 400,
            color: i <= currentStep ? 'var(--teal-light)' : 'var(--text-muted)',
            transition: 'color 0.3s',
          }}>
            {label}
          </span>
        </div>
      ))}
    </div>
  );
}
