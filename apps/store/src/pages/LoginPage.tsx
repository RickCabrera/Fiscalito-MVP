import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function LoginPage() {
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { signIn, signUp, signInWithGoogle } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      if (isRegister) {
        await signUp(email, password);
      } else {
        await signIn(email, password);
      }
      navigate('/app');
    } catch (err: unknown) {
      const code = (err instanceof Object && 'code' in err) ? (err as { code: string }).code : '';
      if (code === 'auth/user-not-found') setError('No existe una cuenta con ese correo.');
      else if (code === 'auth/wrong-password') setError('Contrasena incorrecta.');
      else if (code === 'auth/email-already-in-use') setError('Ese correo ya esta registrado.');
      else if (code === 'auth/weak-password') setError('La contrasena debe tener al menos 6 caracteres.');
      else if (code === 'auth/invalid-email') setError('Correo invalido.');
      else setError(err instanceof Error ? err.message : 'Error al autenticar. Intenta de nuevo.');
    } finally {
      setLoading(false);
    }
  };

  const handleGoogle = async () => {
    setError('');
    setLoading(true);
    try {
      await signInWithGoogle();
      navigate('/app');
    } catch {
      setError('Error con Google. Intenta de nuevo.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'var(--bg-dark)',
      padding: 24,
      position: 'relative',
      overflow: 'hidden',
    }}>
      {/* Background glows */}
      <div style={{
        position: 'absolute', width: 400, height: 400, borderRadius: '50%',
        background: 'var(--purple-muted)', filter: 'blur(120px)',
        top: -100, left: -100, pointerEvents: 'none',
      }} />
      <div style={{
        position: 'absolute', width: 300, height: 300, borderRadius: '50%',
        background: 'var(--teal-muted)', filter: 'blur(120px)',
        bottom: -50, right: -50, pointerEvents: 'none',
      }} />

      <div className="animate-in" style={{
        width: '100%',
        maxWidth: 420,
        position: 'relative',
        zIndex: 2,
      }}>
        {/* Header */}
        <div style={{ textAlign: 'center', marginBottom: 40 }}>
          <Link to="/" style={{ textDecoration: 'none' }}>
            <div style={{ fontSize: '1.8rem', fontWeight: 800, letterSpacing: -1, marginBottom: 8 }}>
              <span className="gradient-text">Fiscalito</span>{' '}
              <span style={{ color: 'var(--text-muted)' }}>Store</span>
            </div>
          </Link>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.95rem' }}>
            {isRegister ? 'Crea tu cuenta para empezar' : 'Inicia sesion en tu cuenta'}
          </p>
        </div>

        {/* Form card */}
        <div className="card" style={{ padding: 32 }}>
          <form onSubmit={handleSubmit}>
            <div style={{ marginBottom: 20 }}>
              <label style={{ display: 'block', fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: 6 }}>
                Correo electronico
              </label>
              <input
                className="input-field"
                type="email"
                placeholder="tu@correo.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>

            <div style={{ marginBottom: 24 }}>
              <label style={{ display: 'block', fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: 6 }}>
                Contrasena
              </label>
              <input
                className="input-field"
                type="password"
                placeholder="Minimo 6 caracteres"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={6}
              />
            </div>

            {error && (
              <div style={{
                padding: '10px 14px',
                background: 'var(--danger-bg)',
                border: '1px solid var(--danger-border)',
                borderRadius: 'var(--radius-xs)',
                color: 'var(--danger)',
                fontSize: '0.85rem',
                marginBottom: 20,
              }}>
                {error}
              </div>
            )}

            <button
              className="btn-primary"
              type="submit"
              disabled={loading}
              style={{ width: '100%', padding: '14px', fontSize: '1rem' }}
            >
              {loading ? 'Cargando...' : isRegister ? 'Crear cuenta' : 'Iniciar sesion'}
            </button>
          </form>

          <div style={{
            display: 'flex', alignItems: 'center', gap: 12,
            margin: '20px 0', color: 'var(--text-muted)', fontSize: '0.8rem',
          }}>
            <div style={{ flex: 1, height: 1, background: 'var(--border)' }} />
            o
            <div style={{ flex: 1, height: 1, background: 'var(--border)' }} />
          </div>

          <button
            onClick={handleGoogle}
            className="btn-secondary"
            style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}
          >
            <svg width="18" height="18" viewBox="0 0 24 24">
              <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"/>
              <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
              <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
              <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
            </svg>
            Continuar con Google
          </button>
        </div>

        {/* Toggle */}
        <p style={{ textAlign: 'center', marginTop: 20, fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
          {isRegister ? 'Ya tienes cuenta?' : 'No tienes cuenta?'}{' '}
          <span
            onClick={() => { setIsRegister(!isRegister); setError(''); }}
            style={{ color: 'var(--teal-light)', cursor: 'pointer', fontWeight: 600 }}
          >
            {isRegister ? 'Inicia sesion' : 'Registrate'}
          </span>
        </p>
      </div>
    </div>
  );
}
