/** Reusable error alert banner */

import { AlertCircle } from 'lucide-react';

interface Props {
  message: string;
}

export default function ErrorAlert({ message }: Props) {
  return (
    <div style={{
      padding: '12px 16px',
      borderRadius: 'var(--radius-xs)',
      background: 'var(--danger-bg)',
      border: '1px solid var(--danger-border)',
      color: 'var(--danger)',
      fontSize: '0.85rem',
      display: 'flex',
      alignItems: 'center',
      gap: 8,
    }}>
      <AlertCircle size={16} /> {message}
    </div>
  );
}
