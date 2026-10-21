/**
 * "Cumplimiento ante el SAT" en la ficha del cliente (P1-05, con el resumen 69-B de P1-04).
 *
 * Opinión de cumplimiento con su semáforo, constancia de situación fiscal y, abajo, las
 * contrapartes del cliente que aparecen en los listados del SAT.
 */

import DocumentoSat from './DocumentoSat';
import RiesgosCliente from './RiesgosCliente';

export default function CumplimientoCliente({ clave }: { clave: string }) {
  return (
    <section className="card animate-in" style={{ marginTop: 'var(--space-lg)', padding: 'var(--space-lg)', display: 'grid', gap: 'var(--space-lg)' }}>
      <h3 style={{ margin: 0, fontSize: '1rem' }}>Cumplimiento ante el SAT</h3>
      <DocumentoSat clave={clave} tipo="opinion" />
      <DocumentoSat clave={clave} tipo="constancia" />
      <RiesgosCliente clave={clave} />
    </section>
  );
}
