/**
 * Formulario para subir .cer + .key + contraseña de un tipo (e.firma o CSD).
 *
 * La contraseña se borra del estado en cuanto termina el envío, salga bien o mal.
 */

import { useState, type FormEvent } from 'react';
import { Upload, Loader } from 'lucide-react';
import ErrorAlert from '../common/ErrorAlert';
import { subirCredencial, type Credencial, type TipoCredencial } from '../../services/credencialesApi';

interface Props {
  clave: string;
  tipo: TipoCredencial;
  onGuardada: (c: Credencial) => void;
  onCancelar?: () => void;
}

const etiqueta: React.CSSProperties = {
  display: 'flex', flexDirection: 'column', gap: 4,
  fontSize: '0.8rem', color: 'var(--text-secondary)',
};

const campo: React.CSSProperties = {
  padding: 'var(--space-xs)', background: 'var(--bg-input)', color: 'var(--text-primary)',
  border: '1px solid var(--border)', borderRadius: 'var(--radius-xs)', fontSize: '0.85rem',
};

export default function FormCredencial({ clave, tipo, onGuardada, onCancelar }: Props) {
  const [cer, setCer] = useState<File | null>(null);
  const [key, setKey] = useState<File | null>(null);
  const [password, setPassword] = useState('');
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const completo = cer !== null && key !== null && password.length > 0;

  async function enviar(e: FormEvent) {
    e.preventDefault();
    if (!cer || !key || !password) return;
    setEnviando(true);
    setError(null);
    try {
      onGuardada(await subirCredencial(clave, tipo, cer, key, password));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo guardar la credencial.');
    } finally {
      setPassword('');
      setEnviando(false);
    }
  }

  return (
    <form
      onSubmit={enviar}
      aria-label={`Subir ${tipo}`}
      style={{ display: 'grid', gap: 'var(--space-sm)', marginTop: 'var(--space-sm)' }}
    >
      <div style={{ display: 'grid', gap: 'var(--space-sm)', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))' }}>
        <label style={etiqueta}>
          Certificado (.cer)
          <input
            type="file" accept=".cer" style={campo}
            onChange={(e) => setCer(e.target.files?.[0] ?? null)}
          />
        </label>
        <label style={etiqueta}>
          Llave privada (.key)
          <input
            type="file" accept=".key" style={campo}
            onChange={(e) => setKey(e.target.files?.[0] ?? null)}
          />
        </label>
        <label style={etiqueta}>
          Contraseña de la llave
          <input
            type="password" autoComplete="off" style={campo} value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>
      </div>
      {error && <ErrorAlert message={error} />}
      <div style={{ display: 'flex', gap: 'var(--space-xs)' }}>
        <button
          type="submit" disabled={!completo || enviando} className="btn-primary"
          style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
        >
          {enviando ? <Loader size={14} className="spin" /> : <Upload size={14} />}
          {enviando ? 'Validando…' : 'Validar y guardar'}
        </button>
        {onCancelar && (
          <button type="button" className="btn-secondary" onClick={onCancelar} disabled={enviando}>
            Cancelar
          </button>
        )}
      </div>
    </form>
  );
}
