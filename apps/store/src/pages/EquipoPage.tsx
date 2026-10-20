/**
 * Equipo del despacho (P5-01) — `/app/equipo`, se entra desde Perfil.
 *
 * Usuarios con su rol, invitaciones pendientes y los clientes que ve cada auxiliar. Sólo el
 * dueño gestiona: el backend lo hace cumplir (403) y `puede_gestionar` decide qué se pinta.
 * El límite de usuarios del plan también lo hace cumplir el backend (`app/planes.py`).
 */

import { useCallback, useEffect, useState } from 'react';
import { Loader, MailPlus, UsersRound, X } from 'lucide-react';
import { useClienteActivo } from '../context/clienteActivoStore';
import {
  asignarCliente, cambiarActivo, cambiarRol, invitar, NOMBRE_ROL, obtenerEquipo,
  revocarInvitacion, type Equipo, type Rol,
} from '../services/equipoApi';
import FilaUsuario from '../components/equipo/FilaUsuario';
import ErrorAlert from '../components/common/ErrorAlert';

const campo: React.CSSProperties = {
  background: 'var(--bg-input)', color: 'var(--text-primary)', border: '1px solid var(--border)',
  borderRadius: 'var(--radius-sm)', padding: '6px 10px', fontSize: '0.85rem',
};

export default function EquipoPage() {
  const { clientes } = useClienteActivo();
  const [equipo, setEquipo] = useState<Equipo | null>(null);
  const [error, setError] = useState('');
  const [aviso, setAviso] = useState('');
  const [ocupado, setOcupado] = useState(false);
  const [correo, setCorreo] = useState('');
  const [rol, setRol] = useState<Rol>('auxiliar');

  const cargar = useCallback(() => {
    obtenerEquipo()
      .then((e) => setEquipo(e))
      .catch((e: unknown) => setError(e instanceof Error ? e.message : 'No se pudo cargar el equipo.'));
  }, []);
  useEffect(() => { cargar(); }, [cargar]);

  const hacer = async (fn: () => Promise<unknown>, ok = '') => {
    setOcupado(true);
    setError('');
    setAviso('');
    try {
      await fn();
      if (ok) setAviso(ok);
      cargar();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo guardar.');
    } finally {
      setOcupado(false);
    }
  };

  if (!equipo) {
    return (
      <div style={{ padding: 24 }}>
        {error ? <ErrorAlert message={error} /> : (
          <span style={{ display: 'flex', gap: 8, alignItems: 'center', color: 'var(--text-secondary)' }}>
            <Loader size={16} className="spin" /> Cargando el equipo…
          </span>
        )}
      </div>
    );
  }
  const { plan, puede_gestionar: gestiona } = equipo;
  const lugares = plan.usuarios_activos + plan.invitaciones_pendientes;
  const enviar = (e: React.FormEvent) => {
    e.preventDefault();
    void hacer(async () => { await invitar(correo.trim(), rol); setCorreo(''); },
      `Invitación enviada a ${correo.trim()}.`);
  };

  return (
    <div style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 16, maxWidth: 900 }}>
      <h1 style={{ fontSize: '1.3rem', display: 'flex', alignItems: 'center', gap: 10 }}>
        <UsersRound size={20} /> Equipo del despacho
      </h1>
      <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
        Plan {plan.nombre}: {plan.usuarios_activos} de {plan.max_usuarios} usuarios
        {plan.invitaciones_pendientes > 0 && ` (+${plan.invitaciones_pendientes} invitaciones pendientes)`}.
        {' '}El auxiliar sólo ve los clientes que le asignes; el contador ve todos; el dueño
        además gestiona el equipo.
      </p>
      {error && <ErrorAlert message={error} />}
      {aviso && <p role="status" style={{ color: 'var(--success)', fontSize: '0.85rem' }}>{aviso}</p>}

      {gestiona && (
        <form className="card" onSubmit={enviar} style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: '0.75rem', flex: 1, minWidth: 220 }}>
            Correo
            <input type="email" required aria-label="Correo" style={campo} value={correo}
              onChange={(e) => setCorreo(e.target.value)} placeholder="persona@despacho.mx" />
          </label>
          <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: '0.75rem' }}>
            Rol
            <select aria-label="Rol de la invitación" style={campo} value={rol}
              onChange={(e) => setRol(e.target.value as Rol)}>
              {(Object.keys(NOMBRE_ROL) as Rol[]).map((r) => <option key={r} value={r}>{NOMBRE_ROL[r]}</option>)}
            </select>
          </label>
          <button className="btn-primary" type="submit" disabled={ocupado || lugares >= plan.max_usuarios}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <MailPlus size={14} /> Invitar
          </button>
          {lugares >= plan.max_usuarios && (
            <p style={{ width: '100%', fontSize: '0.8rem', color: 'var(--warning)' }}>
              El plan {plan.nombre} llega hasta {plan.max_usuarios}{' '}
              {plan.max_usuarios === 1 ? 'usuario' : 'usuarios'}. Cambia de plan o revoca una
              invitación para invitar a alguien más.
            </p>
          )}
        </form>
      )}

      <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 8 }}>
        {equipo.usuarios.map((u) => (
          <FilaUsuario key={u.uid} usuario={u} esYo={u.uid === equipo.yo.uid} editable={gestiona}
            clientes={clientes} ocupado={ocupado}
            onRol={(r) => void hacer(() => cambiarRol(u.uid, r))}
            onActivo={(a) => void hacer(() => cambiarActivo(u.uid, a))}
            onAsignar={(clave, si) => void hacer(() => asignarCliente(u.uid, clave, si))} />
        ))}
      </ul>

      {gestiona && equipo.invitaciones.length > 0 && (
        <section className="card" aria-label="Invitaciones pendientes">
          <h2 style={{ fontSize: '0.95rem', marginBottom: 8 }}>Invitaciones pendientes</h2>
          <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 6 }}>
            {equipo.invitaciones.map((i) => (
              <li key={i.id} style={{ display: 'flex', gap: 12, alignItems: 'center', fontSize: '0.85rem' }}>
                <span style={{ flex: 1 }}>{i.correo} · {NOMBRE_ROL[i.rol]}</span>
                <span style={{ color: 'var(--text-secondary)' }}>vence {i.expira_en.slice(0, 10)}</span>
                <button className="btn-secondary" aria-label={`Revocar invitación a ${i.correo}`}
                  disabled={ocupado} onClick={() => void hacer(() => revocarInvitacion(i.id))}>
                  <X size={14} />
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
