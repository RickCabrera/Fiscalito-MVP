/** Reusable success notification banner */

interface Props {
  message?: string;
}

export default function SuccessNotice({ message = 'Guardado en historial' }: Props) {
  return (
    <div style={{
      padding: '8px 16px',
      borderRadius: 'var(--radius-xs)',
      background: 'var(--success-bg)',
      border: '1px solid var(--success-border)',
      color: 'var(--success)',
      fontSize: '0.82rem',
      display: 'flex',
      alignItems: 'center',
      gap: 6,
    }}>
      &#10003; {message}
    </div>
  );
}
