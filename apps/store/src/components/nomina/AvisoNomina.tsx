/**
 * Aviso destacado dentro del flujo de nómina (extraído de `NominaClientePage`
 * en E-06). DEMO: se borra en F2 con la épica.
 *
 * Usa `.card` como base y sólo cambia el color del borde según la severidad,
 * para que un aviso se lea como una card marcada y no como otro tipo de caja
 * — la decisión es de E-04 y no se re-litiga aquí.
 */

import { AlertTriangle } from 'lucide-react';

export type Severidad = 'error' | 'advertencia';

const COLOR: Record<Severidad, string> = {
  error: 'var(--danger)',
  advertencia: 'var(--warning)',
};

export default function AvisoNomina({
  severidad,
  children,
  conIcono = true,
  rol = 'alert',
  etiqueta,
  pie,
}: {
  severidad: Severidad;
  children: React.ReactNode;
  /** El aviso de error de operación no lleva icono: lo dice su encabezado. */
  conIcono?: boolean;
  rol?: 'alert' | 'alertdialog';
  etiqueta?: string;
  /** Acciones bajo el texto — hoy sólo el diálogo de confirmación las usa. */
  pie?: React.ReactNode;
}) {
  const color = COLOR[severidad];
  return (
    <div
      className="card"
      role={rol}
      aria-label={etiqueta}
      style={{
        borderColor: color,
        color: 'var(--text-primary)',
        margin: 0,
        display: 'flex',
        flexDirection: 'column',
        gap: 'var(--space-sm)',
      }}
    >
      <div style={{ display: 'flex', gap: 'var(--space-sm)', alignItems: 'flex-start' }}>
        {conIcono && (
          <AlertTriangle size={18} color={color} style={{ flexShrink: 0, marginTop: 2 }} />
        )}
        <span>{children}</span>
      </div>
      {pie}
    </div>
  );
}
