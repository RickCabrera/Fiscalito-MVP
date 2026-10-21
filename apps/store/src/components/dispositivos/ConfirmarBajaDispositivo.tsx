/**
 * Confirmación de baja de un dispositivo. Estado, no `window.confirm`: es el patrón de
 * `EmpleadosTab`, y un misclic sobre un icono chico se llevaría el registro de quién
 * estaba enrolado.
 */

import AvisoDispositivos from './AvisoDispositivos';

export default function ConfirmarBajaDispositivo({
  nombre,
  onCancelar,
  onConfirmar,
}: {
  nombre: string;
  onCancelar: () => void;
  onConfirmar: () => void;
}) {
  return (
    <div style={{ marginTop: 'var(--space-md)' }}>
      <AvisoDispositivos>
        ¿Dar de baja <strong>{nombre}</strong>? Se pierde el registro de quién estaba
        enrolado en él. No borra a nadie de la plantilla ni del aparato físico.{' '}
        <button className="btn-secondary" onClick={onCancelar}>Cancelar</button>{' '}
        <button className="btn-primary" onClick={onConfirmar}>Sí, dar de baja</button>
      </AvisoDispositivos>
    </div>
  );
}
