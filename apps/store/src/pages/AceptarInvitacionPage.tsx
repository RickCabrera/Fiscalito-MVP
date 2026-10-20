/**
 * Aceptar una invitación al equipo de un despacho (P5-01) — `/aceptar-invitacion?token=`.
 *
 * Pública: el enlace llega por correo. Sin sesión pide iniciarla (y regresa aquí con
 * `?volver=`); con sesión manda el token al backend, que une al usuario a ESE despacho. Si su
 * cuenta ya tiene un despacho propio con datos, el backend lo rechaza con un error claro.
 */

import { useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { Loader, UsersRound } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { aceptarInvitacion, NOMBRE_ROL } from '../services/equipoApi';
import ErrorAlert from '../components/common/ErrorAlert';

export default function AceptarInvitacionPage() {
  const { user, loading } = useAuth();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const token = params.get('token') ?? '';
  const [nombre, setNombre] = useState('');
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState('');
  const [listo, setListo] = useState('');

  const aceptar = async () => {
    setEnviando(true);
    setError('');
    try {
      const r = await aceptarInvitacion(token, nombre.trim());
      setListo(`Ya eres parte del despacho como ${NOMBRE_ROL[r.rol]}.`);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo aceptar la invitación.');
    } finally {
      setEnviando(false);
    }
  };

  const volver = `/aceptar-invitacion?token=${encodeURIComponent(token)}`;
  return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: 'var(--bg-dark)', padding: 24 }}>
      <div className="card" style={{ maxWidth: 440, width: '100%', display: 'flex', flexDirection: 'column', gap: 14 }}>
        <h1 style={{ fontSize: '1.2rem', display: 'flex', alignItems: 'center', gap: 8 }}>
          <UsersRound size={20} /> Invitación a un despacho
        </h1>
        {!token ? (
          <ErrorAlert message="El enlace no trae invitación. Ábrelo tal cual desde el correo." />
        ) : loading ? (
          <span style={{ display: 'flex', gap: 8, alignItems: 'center' }}><Loader size={16} className="spin" /> Cargando…</span>
        ) : !user ? (
          <>
            <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
              Inicia sesión (o crea tu cuenta) para aceptar la invitación. Te regresamos aquí.
            </p>
            <Link to={`/login?volver=${encodeURIComponent(volver)}`}>
              <button className="btn-primary" style={{ width: '100%' }}>Iniciar sesión</button>
            </Link>
          </>
        ) : listo ? (
          <>
            <p role="status" style={{ color: 'var(--success)' }}>{listo}</p>
            <button className="btn-primary" onClick={() => navigate('/app')}>Entrar al despacho</button>
          </>
        ) : (
          <>
            <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
              Vas a unirte con la cuenta <b>{user.email}</b>. El enlace sirve una sola vez.
            </p>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: '0.8rem' }}>
              Tu nombre (opcional)
              <input aria-label="Tu nombre" value={nombre} onChange={(e) => setNombre(e.target.value)}
                style={{ background: 'var(--bg-input)', color: 'var(--text-primary)',
                  border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', padding: '8px 10px' }} />
            </label>
            {error && <ErrorAlert message={error} />}
            <button className="btn-primary" onClick={() => void aceptar()} disabled={enviando}>
              {enviando ? 'Aceptando…' : 'Aceptar invitación'}
            </button>
          </>
        )}
      </div>
    </div>
  );
}
