/**
 * Aviso ámbar de la pantalla de dispositivos, con el mismo aspecto que los de
 * `EmpleadosTab`. Separado de `DispositivosPage` para que la página quepa en 300 líneas
 * y `TarjetaDispositivo` lo reciba por prop sin duplicarlo.
 */

import type { ReactNode } from 'react';

export default function AvisoDispositivos({ children }: { children: ReactNode }) {
  return (
    <p
      role="alert"
      style={{
        margin: 0, background: 'var(--warning-bg)', border: '1px solid var(--warning-border)',
        borderRadius: 'var(--radius-sm)', padding: 'var(--space-sm) var(--space-md)',
        fontSize: '0.88rem', color: 'var(--text-primary)',
      }}
    >
      {children}
    </p>
  );
}
