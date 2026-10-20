/**
 * Alertas fiscales de toda la cartera (P3-09). Ruta `/app/alertas`.
 *
 * Las genera un trabajo diario del backend (tope RESICO, listas 69-B, CFDI cancelados, e.firma
 * o CSD por vencer, opinión negativa, descarga SAT atorada, vencimientos, diferencias con lo
 * declarado y meses sin pólizas). "Revisar ahora" corre las reglas sin esperar al diario.
 */

import { useState } from 'react';
import { Bell, Loader, RefreshCw } from 'lucide-react';
import { useClienteActivo } from '../context/clienteActivoStore';
import { evaluarAlertas, NOMBRE_TIPO_ALERTA, type FiltrosAlertas } from '../services/alertasApi';
import ListaAlertas from '../components/alertas/ListaAlertas';
import ErrorAlert from '../components/common/ErrorAlert';

const campo: React.CSSProperties = {
  background: 'var(--bg-input)', color: 'var(--text-primary)', border: '1px solid var(--border)',
  borderRadius: 'var(--radius-sm)', padding: '6px 10px', fontSize: '0.85rem',
};

export default function AlertasPage() {
  const { clientes } = useClienteActivo();
  const [filtros, setFiltros] = useState<FiltrosAlertas>({});
  const [version, setVersion] = useState(0);
  const [revisando, setRevisando] = useState(false);
  const [error, setError] = useState('');

  const poner = (k: keyof FiltrosAlertas, v: string | boolean) =>
    setFiltros((f) => ({ ...f, [k]: v || undefined }));

  const revisar = async () => {
    setRevisando(true);
    setError('');
    try {
      await evaluarAlertas(filtros.cliente);
      setVersion((x) => x + 1);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudieron revisar.');
    } finally {
      setRevisando(false);
    }
  };

  return (
    <div style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 16, maxWidth: 1000 }}>
      <h1 style={{ fontSize: '1.3rem', display: 'flex', alignItems: 'center', gap: 10 }}>
        <Bell size={20} /> Alertas fiscales
      </h1>
      <div className="card" style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'flex-end' }}>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: '0.75rem' }}>
          Cliente
          <select aria-label="Cliente" style={campo} value={filtros.cliente ?? ''}
            onChange={(e) => poner('cliente', e.target.value)}>
            <option value="">Todos</option>
            {clientes.map((c) => <option key={c.id} value={c.id}>{c.nombre}</option>)}
          </select>
        </label>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: '0.75rem' }}>
          Severidad
          <select aria-label="Severidad" style={campo} value={filtros.severidad ?? ''}
            onChange={(e) => poner('severidad', e.target.value)}>
            <option value="">Todas</option>
            <option value="alta">Alta</option>
            <option value="media">Media</option>
            <option value="baja">Baja</option>
          </select>
        </label>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: '0.75rem' }}>
          Tipo
          <select aria-label="Tipo" style={campo} value={filtros.tipo ?? ''}
            onChange={(e) => poner('tipo', e.target.value)}>
            <option value="">Todos</option>
            {Object.entries(NOMBRE_TIPO_ALERTA).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
        <label style={{ display: 'flex', gap: 6, alignItems: 'center', fontSize: '0.8rem' }}>
          <input type="checkbox" checked={!!filtros.resuelta}
            onChange={(e) => poner('resuelta', e.target.checked)} />
          Ver resueltas
        </label>
        <button className="btn-secondary" onClick={revisar} disabled={revisando}
          style={{ display: 'inline-flex', alignItems: 'center', gap: 6, marginLeft: 'auto' }}>
          {revisando ? <Loader size={14} className="spin" /> : <RefreshCw size={14} />} Revisar ahora
        </button>
      </div>
      {error && <ErrorAlert message={error} />}
      <ListaAlertas filtros={filtros} version={version} />
    </div>
  );
}
