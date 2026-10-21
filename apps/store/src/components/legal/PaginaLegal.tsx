/**
 * Marco común de las páginas públicas legales (P6-01): encabezado con la marca, la banda
 * "REVISAR CON ABOGADO" y los enlaces entre aviso y términos.
 */

import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { MARCA_LOGO } from '../../services/marca';

export const AVISO_ABOGADO =
  'PLANTILLA GENÉRICA — REVISAR CON ABOGADO antes de publicar. No es asesoría legal.';

interface Props {
  titulo: string;
  fecha: string;
  children: ReactNode;
}

export function Seccion({ titulo, children }: { titulo: string; children: ReactNode }) {
  return (
    <section style={{ marginBottom: 24 }}>
      <h2 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: 8 }}>{titulo}</h2>
      <div style={{ color: 'var(--text-secondary)', lineHeight: 1.6, fontSize: '0.92rem' }}>
        {children}
      </div>
    </section>
  );
}

export default function PaginaLegal({ titulo, fecha, children }: Props) {
  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg-dark)', color: 'var(--text-primary)' }}>
      <div style={{ maxWidth: 820, margin: '0 auto', padding: '32px 20px' }}>
        <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          marginBottom: 24 }}>
          <Link to="/" style={{ fontWeight: 700, fontSize: '1.2rem', color: 'var(--text-primary)' }}>
            {MARCA_LOGO}
          </Link>
          <nav style={{ display: 'flex', gap: 16, fontSize: '0.85rem' }}>
            <Link to="/privacidad">Aviso de privacidad</Link>
            <Link to="/terminos">Términos</Link>
          </nav>
        </header>
        <div role="note" className="card" style={{ borderColor: 'var(--warning)',
          color: 'var(--warning)', marginBottom: 24, fontWeight: 600 }}>
          {AVISO_ABOGADO}
        </div>
        <h1 style={{ fontSize: '1.6rem', fontWeight: 700, marginBottom: 4 }}>{titulo}</h1>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginBottom: 24 }}>
          Última actualización: {fecha}
        </p>
        {children}
      </div>
    </div>
  );
}
