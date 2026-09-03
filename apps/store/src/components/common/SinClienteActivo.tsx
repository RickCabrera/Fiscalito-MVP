/**
 * "Elige un cliente primero". (R-05)
 *
 * Vive suelto porque **tres** pantallas lo necesitan —Nómina, Empleados y
 * Dispositivos— y las tres tienen la misma razón para no caer en un default:
 * si `/app/dispositivos` sin cliente activo aterrizara en `demo`, el selector
 * del header afirmaría un cliente y la pantalla enseñaría los aparatos de otro.
 * Es el bloqueante de E-02 otra vez, y `NominaDelClienteActivo` ya lo explica
 * para su caso.
 *
 * Se extrajo en vez de copiarse: tres copias del mismo estado vacío son tres
 * lugares donde arreglar el copy la próxima vez, y dos que alguien va a olvidar.
 */

import { Link } from 'react-router-dom';
import { Users } from 'lucide-react';
import { modoEmpresaUnica } from '../../services/modoEmpresa';

export default function SinClienteActivo({
  titulo,
  explicacion,
}: {
  titulo: string;
  /** Por qué ESTA pantalla necesita un cliente. No es genérico a propósito. */
  explicacion: string;
}) {
  return (
    <div className="page-container">
      <div className="page-header animate-in">
        <h1>{titulo}</h1>
        <p>{explicacion}</p>
      </div>

      {/* O-01: en modo empresa única no hay cliente que elegir ni cartera a la
          que volver — `/app/clientes` redirige. Si este estado vacío llegara a
          pintarse ahí, lo que falta es la Configuración de empresa, y eso es lo
          que tiene que decir en vez de mandar a una pantalla que no existe. */}
      <div className="card" style={{ padding: 'var(--space-2xl) var(--space-lg)', textAlign: 'center' }}>
        <Users size={24} color="var(--text-muted)" />
        {modoEmpresaUnica() ? (
          <>
            <div style={{ fontSize: '1.05rem', fontWeight: 600, margin: '12px 0 8px' }}>
              Configura la empresa primero
            </div>
            <p style={{ fontSize: '0.87rem', color: 'var(--text-secondary)', marginBottom: 'var(--space-md)' }}>
              Falta capturar los datos patronales: razón social y prima de riesgos de trabajo.
            </p>
            <Link to="/app/profile" style={{ color: 'var(--accent-active)', fontSize: '0.9rem' }}>
              Ir a Configuración de empresa
            </Link>
          </>
        ) : (
          <>
            <div style={{ fontSize: '1.05rem', fontWeight: 600, margin: '12px 0 8px' }}>
              Elige un cliente primero
            </div>
            <p style={{ fontSize: '0.87rem', color: 'var(--text-secondary)', marginBottom: 'var(--space-md)' }}>
              No hay ningún cliente activo. Elígelo en el selector de arriba o entra desde la cartera.
            </p>
            <Link to="/app/clientes" style={{ color: 'var(--accent-active)', fontSize: '0.9rem' }}>
              Ver la cartera
            </Link>
          </>
        )}
      </div>
    </div>
  );
}
