/**
 * El resultado del MOTOR para el SBC del empleado (`POST /nomina/sbc`). Todo lo
 * de esta caja viene del backend. Salió de `ModalEmpleado.tsx` en P6-05.
 */
import { AlertTriangle, Loader } from 'lucide-react';
import type { SBCResponse } from '../../services/carteraApi';

export default function ResultadoSbc({ calculando, errorSbc, sbc }: {
  calculando: boolean;
  errorSbc: string | null;
  sbc: SBCResponse | null;
}) {
  return (
    <div
      style={{
        background: 'var(--bg-input)', borderRadius: 'var(--radius-sm)',
        padding: 'var(--space-sm) var(--space-md)', fontSize: '0.86rem',
      }}
    >
      {calculando && (
        <span style={{ color: 'var(--text-secondary)', display: 'flex', gap: 6, alignItems: 'center' }}>
          <Loader size={14} /> Integrando…
        </span>
      )}
      {!calculando && errorSbc && (
        <span role="alert" style={{ color: 'var(--danger)' }}>{errorSbc}</span>
      )}
      {!calculando && !errorSbc && !sbc && (
        <span style={{ color: 'var(--text-muted)' }}>
          Captura el salario diario para ver el SBC.
        </span>
      )}
      {!calculando && sbc && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-md)' }}>
          <span>
            Factor <strong style={{ fontFamily: "'JetBrains Mono', monospace" }}>{sbc.factor}</strong>
            <span style={{ color: 'var(--text-muted)' }}> ({sbc.dias_vacaciones_aplicados} días de vacaciones)</span>
          </span>
          <span>
            SBC <strong style={{ fontFamily: "'JetBrains Mono', monospace" }}>${sbc.sbc}</strong>
          </span>
          {sbc.piso_aplicado && (
            <span style={{ color: 'var(--warning)', display: 'flex', gap: 4, alignItems: 'center' }}>
              <AlertTriangle size={14} />
              Se aplicó el piso de 1 salario mínimo (${sbc.piso}). El patrón absorbe la
              cuota obrera (Art. 36 LSS).
            </span>
          )}
          {sbc.tope_aplicado && (
            <span style={{ color: 'var(--warning)', display: 'flex', gap: 4, alignItems: 'center' }}>
              <AlertTriangle size={14} /> Se aplicó el tope de 25 UMA (${sbc.tope}).
            </span>
          )}
        </div>
      )}
    </div>
  );
}
