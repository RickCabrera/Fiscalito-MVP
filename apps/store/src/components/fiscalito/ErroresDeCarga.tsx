/** Archivos que un uploader de CFDI no cargó: rechazados por no ser XML o que el parser no pudo leer. */

import { AlertCircle } from 'lucide-react';
import type { ArchivoRechazado } from '../../services/archivosXml';

/** `amplio` conserva la medida un poco mayor que la pre-declaración ya usaba en su zona de carga. */
export default function ErroresDeCarga({ errores, amplio = false }: { errores: ArchivoRechazado[]; amplio?: boolean }) {
  if (errores.length === 0) return null;
  return (
    <div style={{ padding: amplio ? '12px 16px' : '10px 14px', borderRadius: 'var(--radius-xs)', background: 'var(--danger-bg)', border: '1px solid var(--danger-border)' }}>
      {errores.map((err, i) => (
        <div key={i} style={{ fontSize: amplio ? '0.8rem' : '0.78rem', color: 'var(--danger)', display: 'flex', alignItems: 'center', gap: 6 }}>
          <AlertCircle size={amplio ? 14 : 12} /> {err.fileName}: {err.error}
        </div>
      ))}
    </div>
  );
}
