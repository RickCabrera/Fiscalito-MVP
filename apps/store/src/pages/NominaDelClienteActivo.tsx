/**
 * `/app/nomina` — lleva a la nómina del cliente activo (E-03).
 *
 * Existe para que el enlace "Nómina" del sidebar no tenga que conocer el id del
 * cliente: `getSidebarLinks` es función pura del tipo de perfil y darle acceso
 * al contexto la volvería otra cosa.
 *
 * **No cae en `demo` cuando no hay cliente.** Un default silencioso ahí sería el
 * bloqueante de E-02 otra vez: el header diría un cliente y la pantalla
 * calcularía otro. Sin cartera, esto manda a elegir.
 *
 * DEMO — se borra en F2.
 */

import { Link, Navigate } from 'react-router-dom';
import { Loader, Users } from 'lucide-react';
import { useClienteActivo } from '../context/clienteActivoStore';
import ErrorAlert from '../components/common/ErrorAlert';

export default function NominaDelClienteActivo() {
  const { clienteId, loading, error } = useClienteActivo();

  if (clienteId) {
    return <Navigate to={`/app/clientes/${clienteId}/nomina`} replace />;
  }

  return (
    <div className="page-container">
      <div className="page-header animate-in">
        <h1>Nómina</h1>
        <p>La nómina se calcula por cliente.</p>
      </div>

      {loading && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: 'var(--text-secondary)' }}>
          <Loader size={18} className="spin" color="var(--accent-active)" />
          Buscando el cliente activo...
        </div>
      )}

      {error && <ErrorAlert message={error} />}

      {!loading && !error && (
        <div className="card" style={{ padding: '48px 24px', textAlign: 'center' }}>
          <Users size={24} color="var(--text-muted)" />
          <div style={{ fontSize: '1.05rem', fontWeight: 600, margin: '12px 0 8px' }}>
            Elige un cliente primero
          </div>
          <p style={{ fontSize: '0.87rem', color: 'var(--text-secondary)', marginBottom: 16 }}>
            No hay ningún cliente activo, así que no hay nómina que calcular.
          </p>
          <Link to="/app/clientes" style={{ color: 'var(--accent-active)', fontSize: '0.9rem' }}>
            Ver la cartera
          </Link>
        </div>
      )}
    </div>
  );
}
