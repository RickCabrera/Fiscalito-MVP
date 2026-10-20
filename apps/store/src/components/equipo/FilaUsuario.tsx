/**
 * Un usuario del equipo (P5-01): rol, activo y —si es auxiliar— qué clientes ve.
 * Sin `editable` (quien mira no es el dueño) se pinta de sólo lectura.
 */

import { useState } from 'react';
import type { ClienteResumen } from '../../services/despachoApi';
import { NOMBRE_ROL, type Rol, type UsuarioEquipo } from '../../services/equipoApi';

const campo: React.CSSProperties = {
  background: 'var(--bg-input)', color: 'var(--text-primary)', border: '1px solid var(--border)',
  borderRadius: 'var(--radius-sm)', padding: '4px 8px', fontSize: '0.82rem',
};

interface Props {
  usuario: UsuarioEquipo;
  esYo: boolean;
  editable: boolean;
  clientes: ClienteResumen[];
  ocupado: boolean;
  onRol: (rol: Rol) => void;
  onActivo: (activo: boolean) => void;
  onAsignar: (clave: string, asignar: boolean) => void;
}

export default function FilaUsuario({ usuario: u, esYo, editable, clientes, ocupado, onRol,
  onActivo, onAsignar }: Props) {
  const [abierto, setAbierto] = useState(false);
  const nombre = u.nombre || u.email || u.uid;
  return (
    <li className="card" style={{ display: 'flex', flexDirection: 'column', gap: 8, opacity: u.activo ? 1 : 0.6 }}>
      <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
        <div style={{ flex: 1, minWidth: 180 }}>
          <div style={{ fontWeight: 600 }}>{nombre}{esYo && ' (tú)'}</div>
          {u.email && u.email !== nombre && (
            <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>{u.email}</div>
          )}
        </div>
        {editable ? (
          <select aria-label={`Rol de ${nombre}`} style={campo} value={u.rol} disabled={ocupado}
            onChange={(e) => onRol(e.target.value as Rol)}>
            {(Object.keys(NOMBRE_ROL) as Rol[]).map((r) => <option key={r} value={r}>{NOMBRE_ROL[r]}</option>)}
          </select>
        ) : (
          <span style={{ fontSize: '0.82rem' }}>{NOMBRE_ROL[u.rol]}</span>
        )}
        {!u.activo && <span style={{ fontSize: '0.78rem', color: 'var(--warning)' }}>Desactivado</span>}
        {editable && !esYo && (
          <button className="btn-secondary" disabled={ocupado} onClick={() => onActivo(!u.activo)}>
            {u.activo ? 'Desactivar' : 'Reactivar'}
          </button>
        )}
      </div>
      {u.rol === 'auxiliar' && (
        <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
          Ve {u.clientes.length === 0 ? 'ningún cliente' : `${u.clientes.length} ${u.clientes.length === 1 ? 'cliente' : 'clientes'}`}
          {editable && (
            <button className="btn-secondary" style={{ marginLeft: 8, padding: '2px 8px' }}
              onClick={() => setAbierto((x) => !x)} aria-expanded={abierto}>
              {abierto ? 'Cerrar' : 'Asignar clientes'}
            </button>
          )}
          {!abierto && u.clientes.length > 0 && <span>: {u.clientes.join(', ')}</span>}
        </div>
      )}
      {abierto && editable && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
          {clientes.map((c) => (
            <label key={c.id} style={{ display: 'flex', gap: 6, alignItems: 'center', fontSize: '0.82rem' }}>
              <input type="checkbox" disabled={ocupado} checked={u.clientes.includes(c.id)}
                onChange={(e) => onAsignar(c.id, e.target.checked)} />
              {c.nombre}
            </label>
          ))}
        </div>
      )}
    </li>
  );
}
