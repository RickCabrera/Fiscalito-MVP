/**
 * Contrapartes del cliente en los listados del SAT (P1-04): proveedores en el 69-B (rojo si
 * son definitivos o presuntos), clientes a los que se les facturó y el propio RFC. Muestra
 * cuándo se cargó la lista por última vez, para que "no hay riesgos" no se lea como
 * "verificado" cuando la lista nunca se descargó.
 */

import { useEffect, useState } from 'react';
import { Loader } from 'lucide-react';
import ErrorAlert from '../common/ErrorAlert';
import { riesgos69b, type RiesgosCliente as Datos } from '../../services/satVerificacionApi';

const RELACION: Record<string, string> = {
  proveedor: 'Proveedor', cliente: 'Cliente', propio: 'El propio cliente',
};

export default function RiesgosCliente({ clave }: { clave: string }) {
  const [datos, setDatos] = useState<Datos | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let vigente = true;
    riesgos69b(clave)
      .then((d) => { if (vigente) setDatos(d); })
      .catch((e: unknown) => { if (vigente) setError(e instanceof Error ? e.message : 'No se pudieron cargar los riesgos.'); });
    return () => { vigente = false; };
  }, [clave]);

  const lista69b = datos?.listas.find((l) => l.lista === '69b');

  return (
    <div style={{ display: 'grid', gap: 'var(--space-sm)' }} aria-label="Riesgos 69-B">
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 'var(--space-sm)', flexWrap: 'wrap' }}>
        <strong style={{ fontSize: '0.92rem' }}>Listas del SAT (Art. 69-B)</strong>
        {lista69b && (
          <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
            {lista69b.cargada_en ? `Lista cargada ${lista69b.cargada_en.slice(0, 10)} · ${lista69b.registros} contribuyentes` : 'La lista aún no se ha descargado'}
          </span>
        )}
      </div>
      {!datos && !error && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
          <Loader size={14} className="spin" /> Cargando…
        </div>
      )}
      {error && <ErrorAlert message={error} />}
      {datos && datos.riesgos.length === 0 && (
        <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-muted)' }}>
          Ninguna contraparte de la bóveda aparece en los listados cargados.
        </p>
      )}
      {datos && datos.riesgos.length > 0 && (
        <ul style={{ listStyle: 'none', margin: 0, padding: 0 }}>
          {datos.riesgos.map((r) => (
            <li key={`${r.rfc}-${r.relacion}-${r.lista}`} data-riesgo={r.rojo ? 'rojo' : 'info'} style={{
              display: 'flex', gap: 'var(--space-sm)', alignItems: 'center', flexWrap: 'wrap', fontSize: '0.83rem',
              padding: 'var(--space-xs) var(--space-sm)', borderRadius: 'var(--radius-sm)', marginBottom: 4,
              background: r.rojo ? 'var(--danger-bg)' : 'transparent',
              border: `1px solid ${r.rojo ? 'var(--danger-border)' : 'var(--border)'}`,
            }}>
              <span style={{ fontFamily: "'JetBrains Mono', monospace", color: r.rojo ? 'var(--danger)' : 'var(--text-primary)' }}>{r.rfc}</span>
              <span style={{ flex: 1, minWidth: 140 }}>{r.nombre}</span>
              <span style={{ color: 'var(--text-secondary)' }}>{RELACION[r.relacion] ?? r.relacion}</span>
              <span style={{ fontWeight: 600, color: r.rojo ? 'var(--danger)' : 'var(--text-secondary)' }}>{r.situacion_texto || r.situacion}</span>
              <span style={{ color: 'var(--text-muted)' }}>{r.comprobantes} CFDI</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
