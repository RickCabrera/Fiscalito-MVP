/**
 * "Procesos en segundo plano" de la ficha del cliente (P0-04, demo de `EstadoTrabajos`).
 *
 * El botón encola `diagnostico.cliente`, que corre en el worker y cuenta los empleados
 * del cliente en la base. La casilla lo hace fallar una vez para ver el reintento con
 * backoff. Cuando haya trabajos reales (descarga SAT, recálculos) se listan aquí mismo.
 */

import { useState } from 'react';
import { Play } from 'lucide-react';
import EstadoTrabajos from '../common/EstadoTrabajos';
import ErrorAlert from '../common/ErrorAlert';
import { encolarDiagnostico } from '../../services/trabajosApi';

export default function ProcesosCliente({ cliente }: { cliente: string }) {
  const [recarga, setRecarga] = useState(0);
  const [fallar, setFallar] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const encolar = async () => {
    setEnviando(true);
    setError(null);
    try {
      await encolarDiagnostico(cliente, fallar ? 1 : 0);
      setRecarga((r) => r + 1);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo encolar el diagnóstico.');
    } finally {
      setEnviando(false);
    }
  };

  return (
    <section className="card animate-in" style={{ marginTop: 'var(--space-lg)', padding: 'var(--space-lg)' }}>
      <div
        style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          flexWrap: 'wrap', gap: 'var(--space-sm)', marginBottom: 'var(--space-md)',
        }}
      >
        <h3 style={{ margin: 0, fontSize: '1rem' }}>Procesos en segundo plano</h3>
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)', fontSize: '0.82rem' }}>
          <label style={{ display: 'inline-flex', alignItems: 'center', gap: 6, color: 'var(--text-secondary)' }}>
            <input type="checkbox" checked={fallar} onChange={(e) => setFallar(e.target.checked)} />
            Simular una falla
          </label>
          <button className="btn-secondary" onClick={() => void encolar()} disabled={enviando}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <Play size={14} /> Correr diagnóstico
          </button>
        </div>
      </div>
      {error && <div style={{ marginBottom: 'var(--space-sm)' }}><ErrorAlert message={error} /></div>}
      <EstadoTrabajos cliente={cliente} recarga={recarga} />
    </section>
  );
}
