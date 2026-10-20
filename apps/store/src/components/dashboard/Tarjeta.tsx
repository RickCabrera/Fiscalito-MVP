/**
 * Tarjeta del dashboard (P5-02): título con cifra, renglones y enlace "Ver detalle".
 * Toda tarjeta lleva a su detalle: el título mismo es un enlace.
 */

import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { ChevronRight } from 'lucide-react';

export interface RenglonTarjeta {
  id: string;
  texto: ReactNode;
  detalle?: ReactNode;
  enlace: string;
  tono?: 'normal' | 'alerta' | 'peligro' | 'ok';
}

const COLOR: Record<NonNullable<RenglonTarjeta['tono']>, string> = {
  normal: 'var(--text-secondary)', alerta: 'var(--warning)', peligro: 'var(--danger)',
  ok: 'var(--success)',
};

interface Props {
  titulo: string;
  icono: ReactNode;
  enlace: string;
  cifra: ReactNode;
  subtitulo?: ReactNode;
  renglones: RenglonTarjeta[];
  vacio: string;
}

export default function Tarjeta({ titulo, icono, enlace, cifra, subtitulo, renglones, vacio }: Props) {
  return (
    <section className="card" aria-label={titulo}
      style={{ display: 'flex', flexDirection: 'column', gap: 10, minWidth: 0 }}>
      <Link to={enlace} style={{ display: 'flex', alignItems: 'center', gap: 8,
        color: 'var(--text-primary)', textDecoration: 'none' }}>
        {icono}
        <h2 style={{ fontSize: '0.95rem', fontWeight: 600, flex: 1 }}>{titulo}</h2>
        <ChevronRight size={16} color="var(--text-muted)" />
      </Link>
      <div style={{ fontSize: '1.6rem', fontWeight: 700, fontFamily: 'var(--font-mono, monospace)' }}>
        {cifra}
      </div>
      {subtitulo && <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>{subtitulo}</div>}
      {renglones.length === 0 ? (
        <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{vacio}</p>
      ) : (
        <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 4 }}>
          {renglones.slice(0, 6).map((r) => (
            <li key={r.id}>
              <Link to={r.enlace} style={{ display: 'flex', justifyContent: 'space-between', gap: 8,
                fontSize: '0.8rem', color: 'var(--text-primary)', textDecoration: 'none' }}>
                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.texto}</span>
                {r.detalle && <span style={{ color: COLOR[r.tono ?? 'normal'], whiteSpace: 'nowrap' }}>{r.detalle}</span>}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
