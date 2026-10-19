/**
 * Lo que ve una persona moral donde iría la pre-declaración (T6, P3-01).
 *
 * La pre-declaración es la de `calculadora.py` (personas físicas) y el API
 * rechaza el 601 con un 400. El motor de morales vive en sus propios tabs:
 * Pagos provisionales PM y Declaración anual.
 */

import { Building2 } from 'lucide-react';

export default function AvisoMotorPM() {
  return (
    <div className="card" style={{ textAlign: 'center', padding: 'var(--space-lg)' }}>
      <Building2 size={28} color="var(--text-muted)" />
      <p style={{ margin: '12px 0 0', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
        Esta pre-declaración es la de personas físicas. El ISR de una persona moral se
        calcula en <strong>Pagos provisionales PM</strong> y en <strong>Declaración anual</strong>.
      </p>
    </div>
  );
}
