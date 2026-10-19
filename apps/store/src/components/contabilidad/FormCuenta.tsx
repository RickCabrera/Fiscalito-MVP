/**
 * Alta de cuenta o subcuenta (P2-01). Con padre, propone el siguiente número
 * (`padre.NN`) y hereda su código agrupador; el nivel, la naturaleza y el tipo
 * los decide el backend a partir del padre y del agrupador.
 */

import { useState } from 'react';
import type { CodigoAgrupador, Cuenta } from '../../services/contabilidadApi';
import { crearCuenta } from '../../services/contabilidadApi';
import ErrorAlert from '../common/ErrorAlert';
import { mensaje } from './comun';
import { labelStyle } from '../../utils/styles';

interface Props {
  clave: string;
  /** null = cuenta de mayor (nivel 1). */
  padre: Cuenta | null;
  agrupador: CodigoAgrupador[];
  onListo: () => void;
  onCancelar: () => void;
}

export default function FormCuenta({ clave, padre, agrupador, onListo, onCancelar }: Props) {
  const [numero, setNumero] = useState(padre ? `${padre.numero}.` : '');
  const [nombre, setNombre] = useState('');
  const [codigo, setCodigo] = useState(padre?.codigo_agrupador ?? '');
  const [error, setError] = useState<string | null>(null);
  const [guardando, setGuardando] = useState(false);

  async function guardar(e: React.FormEvent) {
    e.preventDefault();
    setGuardando(true);
    setError(null);
    try {
      await crearCuenta(clave, {
        numero: numero.trim(), nombre: nombre.trim(), codigo_agrupador: codigo.trim(),
        padre_id: padre?.id ?? null,
      });
      onListo();
    } catch (err) {
      setError(mensaje(err, 'No se pudo crear la cuenta.'));
    } finally {
      setGuardando(false);
    }
  }

  return (
    <form className="card" onSubmit={guardar} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
      <strong>{padre ? `Subcuenta de ${padre.numero} ${padre.nombre}` : 'Cuenta de mayor'}</strong>
      {error && <ErrorAlert message={error} />}
      <div style={{ display: 'flex', gap: 'var(--space-md)', flexWrap: 'wrap', alignItems: 'flex-end' }}>
        <label style={{ minWidth: 140 }}>
          <span style={labelStyle}>Número</span>
          <input className="input-field" value={numero} required onChange={(e) => setNumero(e.target.value)} />
        </label>
        <label style={{ flex: 1, minWidth: 220 }}>
          <span style={labelStyle}>Nombre</span>
          <input className="input-field" value={nombre} required onChange={(e) => setNombre(e.target.value)} />
        </label>
        <label style={{ minWidth: 260 }}>
          <span style={labelStyle}>Código agrupador SAT</span>
          <input className="input-field" list="lista-agrupador" value={codigo} required
            onChange={(e) => setCodigo(e.target.value.split(' ')[0])} />
          <datalist id="lista-agrupador">
            {agrupador.filter((c) => c.nivel > 0).map((c) => (
              <option key={c.codigo} value={c.codigo}>{`${c.codigo} ${c.nombre}`}</option>
            ))}
          </datalist>
        </label>
        <button type="submit" className="btn-primary" disabled={guardando}>Guardar</button>
        <button type="button" className="btn-secondary" onClick={onCancelar}>Cancelar</button>
      </div>
    </form>
  );
}
