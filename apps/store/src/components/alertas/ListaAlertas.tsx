/**
 * Lista de alertas fiscales con su botón "Resuelta" (P3-09).
 *
 * La usan la página `/app/alertas` (toda la cartera) y la sección de la ficha del cliente.
 * Carga, error y vacío se pintan aquí para que las dos pantallas digan lo mismo.
 */

import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { CheckCircle2, Loader } from 'lucide-react';
import {
  listarAlertas, NOMBRE_TIPO_ALERTA, resolverAlerta,
  type AlertaFiscal, type FiltrosAlertas, type Severidad,
} from '../../services/alertasApi';
import ErrorAlert from '../common/ErrorAlert';

const COLOR_SEVERIDAD: Record<Severidad, string> = {
  alta: 'var(--danger)', media: 'var(--warning)', baja: 'var(--text-secondary)',
};

interface Props {
  filtros: FiltrosAlertas;
  /** Ocultar la columna de cliente (en la ficha ya se sabe de quién son). */
  sinCliente?: boolean;
  /** Cambia para forzar una recarga (p. ej. tras "Revisar ahora"). */
  version?: number;
}

export default function ListaAlertas({ filtros, sinCliente = false, version = 0 }: Props) {
  const [alertas, setAlertas] = useState<AlertaFiscal[] | null>(null);
  const [error, setError] = useState('');
  const [resolviendo, setResolviendo] = useState<number | null>(null);
  const clave = JSON.stringify(filtros);

  const cargar = useCallback(() => {
    listarAlertas(JSON.parse(clave) as FiltrosAlertas)
      .then((r) => { setError(''); setAlertas(r.alertas); })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : 'No se pudieron cargar.'));
  }, [clave]);

  useEffect(() => { cargar(); }, [cargar, version]);

  const resolver = async (id: number) => {
    setResolviendo(id);
    try {
      await resolverAlerta(id);
      setAlertas((xs) => (xs ?? []).filter((a) => a.id !== id));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo marcar.');
    } finally {
      setResolviendo(null);
    }
  };

  if (error) return <ErrorAlert message={error} />;
  if (!alertas) return <Loader size={18} className="spin" aria-label="Cargando alertas" />;
  if (alertas.length === 0) {
    return <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
      {filtros.resuelta ? 'No hay alertas resueltas.' : 'Sin alertas abiertas.'}
    </p>;
  }
  return (
    <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: 8 }}>
      {alertas.map((a) => (
        <li key={a.id} className="card" style={{
          padding: '10px 14px', borderLeft: `3px solid ${COLOR_SEVERIDAD[a.severidad]}`,
          display: 'flex', gap: 12, alignItems: 'flex-start',
        }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: 'flex', gap: 8, alignItems: 'baseline', flexWrap: 'wrap' }}>
              <strong style={{ fontSize: '0.88rem' }}>{a.titulo}</strong>
              <span style={{ fontSize: '0.7rem', color: COLOR_SEVERIDAD[a.severidad], textTransform: 'uppercase' }}>
                {a.severidad}
              </span>
              <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                {NOMBRE_TIPO_ALERTA[a.tipo] ?? a.tipo} · {a.fecha}
                {!sinCliente && ` · ${a.cliente_nombre || a.cliente}`}
              </span>
            </div>
            {a.detalle && (
              <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', margin: '4px 0 0' }}>{a.detalle}</p>
            )}
            {a.enlace && (
              <Link to={a.enlace} style={{ fontSize: '0.75rem', color: 'var(--accent-active)' }}>Ir a revisar</Link>
            )}
          </div>
          {!a.resuelta && (
            <button className="btn-secondary" onClick={() => resolver(a.id)} disabled={resolviendo === a.id}
              style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '4px 10px', fontSize: '0.75rem' }}>
              <CheckCircle2 size={13} /> Resuelta
            </button>
          )}
        </li>
      ))}
    </ul>
  );
}
