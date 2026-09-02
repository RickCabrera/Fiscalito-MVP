/**
 * Selector de cliente activo, en la barra superior (E-02).
 *
 * SÓLO SE MUESTRA EN RUTAS CON ALCANCE DE CLIENTE. Calendario y Perfil son del
 * DESPACHO, no de un cliente: §D21 dice explícito que el calendario de una
 * cuenta de despacho muestra sus obligaciones propias y nada patronal. Un
 * selector de cliente visible ahí le mentiría al contador sobre lo que está
 * viendo.
 *
 * DEMO — se borra en F2.
 */

import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { Building2, Loader } from 'lucide-react';
import { useClienteActivo } from '../context/clienteActivoStore';
import { rutaTieneAlcanceDeCliente } from '../services/navigation';

export default function SelectorCliente() {
  const { clientes, clienteId, loading, setClienteId } = useClienteActivo();
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const { id: idDeLaRuta } = useParams();

  if (!rutaTieneAlcanceDeCliente(pathname)) return null;

  const cambiar = (nuevo: string) => {
    setClienteId(nuevo);
    // Si se está viendo la ficha de un cliente, el selector tiene que mover la
    // ficha también: si no, el header diría una cosa y la pantalla otra.
    if (idDeLaRuta) navigate(`/app/clientes/${nuevo}`);
  };

  return (
    <div
      style={{
        display: 'flex', alignItems: 'center', gap: 10,
        padding: '10px 24px',
        borderBottom: '1px solid var(--border)',
        background: 'var(--bg-surface)',
      }}
    >
      <Building2 size={16} color="var(--text-secondary)" />
      <label htmlFor="selector-cliente" style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
        Cliente activo
      </label>
      {loading ? (
        <Loader size={14} className="spin" color="var(--text-muted)" />
      ) : (
        <select
          id="selector-cliente"
          className="input-field"
          value={clienteId ?? ''}
          onChange={(e) => cambiar(e.target.value)}
          disabled={clientes.length === 0}
          style={{ width: 'auto', minWidth: 220, padding: '6px 10px', cursor: 'pointer' }}
        >
          {clientes.length === 0 && <option value="">Sin clientes</option>}
          {clientes.map((c) => (
            <option key={c.id} value={c.id}>
              {c.nombre} · {c.num_empleados} empleados
            </option>
          ))}
        </select>
      )}
    </div>
  );
}
