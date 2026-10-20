/**
 * Subir una declaración, acuse u otro PDF/XML al expediente del cliente (P5-05), para poder
 * enviarlo. El backend valida que sea PDF o XML y de máximo 10 MB.
 */

import { useState } from 'react';
import { Upload } from 'lucide-react';
import { subirAlExpediente } from '../../services/enviosDocumentosApi';
import ErrorAlert from '../common/ErrorAlert';

type TipoSubido = 'declaracion' | 'acuse' | 'otro';
const campo = { padding: '4px 6px', background: 'var(--bg-input)', color: 'var(--text-primary)', border: '1px solid var(--border)', borderRadius: 'var(--radius)' };

export default function SubirExpediente({ clave, onSubido }: { clave: string; onSubido: () => void }) {
  const [tipo, setTipo] = useState<TipoSubido>('acuse');
  const [descripcion, setDescripcion] = useState('');
  const [periodo, setPeriodo] = useState('');
  const [archivo, setArchivo] = useState<File | null>(null);
  const [error, setError] = useState('');
  const [ocupado, setOcupado] = useState(false);

  const subir = async () => {
    if (!archivo) return;
    setOcupado(true);
    setError('');
    try {
      await subirAlExpediente(clave, tipo, descripcion, periodo, archivo);
      setDescripcion('');
      setArchivo(null);
      onSubido();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo subir el archivo.');
    } finally {
      setOcupado(false);
    }
  };

  return (
    <form aria-label="Subir al expediente" onSubmit={(e) => { e.preventDefault(); void subir(); }}
      style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center', fontSize: '0.85rem' }}>
      <strong>Subir</strong>
      <select style={campo} aria-label="Tipo de documento" value={tipo} onChange={(e) => setTipo(e.target.value as TipoSubido)}>
        <option value="declaracion">Declaración</option>
        <option value="acuse">Acuse</option>
        <option value="otro">Otro</option>
      </select>
      <input style={campo} aria-label="Descripción" placeholder="Descripción" value={descripcion} onChange={(e) => setDescripcion(e.target.value)} />
      <input style={{ ...campo, width: 90 }} aria-label="Periodo" placeholder="AAAA-MM" value={periodo} onChange={(e) => setPeriodo(e.target.value)} />
      <input aria-label="Archivo" type="file" accept=".pdf,.xml,application/pdf,application/xml" onChange={(e) => setArchivo(e.target.files?.[0] ?? null)} />
      <button type="submit" className="btn-secondary" disabled={ocupado || !archivo}><Upload size={14} /> Subir</button>
      {error && <ErrorAlert message={error} />}
    </form>
  );
}
