/**
 * Lista compacta de los trabajos en segundo plano de un cliente (P0-04).
 *
 * Se refresca sola cada `intervaloMs` mientras haya algo en cola o corriendo, y se queda
 * quieta cuando todo terminó (no tiene caso pegarle al backend para ver lo mismo). Los
 * fallidos y cancelados llevan un botón para reintentar. Reutilizable: cualquier pantalla
 * que encole trabajos de un cliente la monta con su clave y, si quiere, un `tipo`.
 */

import { useCallback, useEffect, useState } from 'react';
import { Loader, RotateCcw } from 'lucide-react';
import ErrorAlert from './ErrorAlert';
import {
  etiquetaEstado, listarTrabajos, reintentarTrabajo,
  type EstadoTrabajo, type Trabajo,
} from '../../services/trabajosApi';

interface Props {
  cliente: string;
  tipo?: string;
  intervaloMs?: number;
  limite?: number;
  /** Cambia este número para forzar una recarga (p. ej. después de encolar). */
  recarga?: number;
}

const COLOR: Record<EstadoTrabajo, string> = {
  pendiente: 'var(--text-secondary)',
  corriendo: 'var(--accent-active)',
  hecho: 'var(--success)',
  fallido: 'var(--danger)',
  cancelado: 'var(--text-muted)',
};

function hora(iso: string | null): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('es-MX', {
    day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit',
  });
}

function resumen(t: Trabajo): string {
  if (t.estado === 'hecho' && t.resultado) {
    return Object.entries(t.resultado).map(([k, v]) => `${k}: ${String(v)}`).join(' · ');
  }
  if (t.error) return t.error;
  if (t.estado === 'pendiente' && t.intentos > 0) return `Reintento a las ${hora(t.ejecutar_en)}`;
  return '';
}

export default function EstadoTrabajos({
  cliente, tipo, intervaloMs = 5000, limite = 10, recarga = 0,
}: Props) {
  const [trabajos, setTrabajos] = useState<Trabajo[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reintentando, setReintentando] = useState<number | null>(null);
  const [vuelta, setVuelta] = useState(0);

  const cargar = useCallback(async () => {
    try {
      setTrabajos(await listarTrabajos({ cliente, tipo, limite }));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudieron cargar los trabajos.');
    }
  }, [cliente, tipo, limite]);

  useEffect(() => {
    let vigente = true;
    listarTrabajos({ cliente, tipo, limite })
      .then((t) => { if (vigente) { setTrabajos(t); setError(null); } })
      .catch((e: unknown) => {
        if (vigente) setError(e instanceof Error ? e.message : 'No se pudieron cargar los trabajos.');
      });
    return () => { vigente = false; };
  }, [cliente, tipo, limite, recarga, vuelta]);

  const activos = trabajos?.some((t) => t.estado === 'pendiente' || t.estado === 'corriendo');
  useEffect(() => {
    if (!activos) return;
    const id = setTimeout(() => setVuelta((v) => v + 1), intervaloMs);
    return () => clearTimeout(id);
  }, [activos, intervaloMs, trabajos]);

  const reintentar = async (id: number) => {
    setReintentando(id);
    try {
      await reintentarTrabajo(id);
      await cargar();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo reintentar.');
    } finally {
      setReintentando(null);
    }
  };

  if (trabajos === null && !error) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
        <Loader size={16} className="spin" /> Cargando procesos...
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-xs)' }}>
      {error && <ErrorAlert message={error} />}
      {trabajos?.length === 0 && (
        <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-muted)' }}>
          No hay procesos en segundo plano para este cliente.
        </p>
      )}
      {trabajos && trabajos.length > 0 && (
        <ul style={{ listStyle: 'none', margin: 0, padding: 0 }} aria-label="Procesos en segundo plano">
          {trabajos.map((t) => (
            <li
              key={t.id}
              style={{
                display: 'flex', alignItems: 'center', gap: 'var(--space-sm)',
                padding: 'var(--space-xs) 0', borderBottom: '1px solid var(--border)', fontSize: '0.85rem',
              }}
            >
              <span style={{ color: COLOR[t.estado], fontWeight: 600, minWidth: 80 }}>
                {etiquetaEstado(t.estado)}
              </span>
              <span style={{ fontFamily: "'JetBrains Mono', monospace", minWidth: 0, flexShrink: 0 }}>{t.tipo}</span>
              <span style={{ color: 'var(--text-secondary)', flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                title={resumen(t)}>
                {resumen(t)}
              </span>
              <span style={{ color: 'var(--text-muted)', fontSize: '0.78rem', whiteSpace: 'nowrap' }}>
                {t.intentos}/{t.max_intentos} · {hora(t.terminado_en ?? t.creado_en)}
              </span>
              {(t.estado === 'fallido' || t.estado === 'cancelado') && (
                <button
                  onClick={() => void reintentar(t.id)}
                  disabled={reintentando === t.id}
                  aria-label={`Reintentar trabajo ${t.id}`}
                  style={{
                    display: 'inline-flex', alignItems: 'center', gap: 4, padding: '2px 10px',
                    background: 'transparent', color: 'var(--text-primary)', cursor: 'pointer',
                    border: '1px solid var(--border-hover)', borderRadius: 'var(--radius-full)', fontSize: '0.78rem',
                  }}
                >
                  <RotateCcw size={12} /> Reintentar
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
