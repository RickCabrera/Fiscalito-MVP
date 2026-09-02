/**
 * Encabezado de la nómina de un cliente (extraído en E-06). DEMO: se borra en F2.
 *
 * Dice DE QUIÉN es esta nómina y cómo volver a su ficha. El sidebar también lo
 * dice desde E-06, pero la migaja es la que da el camino de regreso, y el
 * título es lo que se lee cuando la pantalla está proyectada.
 */

import { Link } from 'react-router-dom';
import { ChevronRight } from 'lucide-react';
import { etiquetaOrigen, type ClienteDetalle } from '../../services/despachoApi';

/** Texto sólo para lectores de pantalla; `global.css` no tiene utilidad para esto. */
const SOLO_LECTORES: React.CSSProperties = {
  position: 'absolute',
  width: 1,
  height: 1,
  overflow: 'hidden',
  clip: 'rect(0 0 0 0)',
  whiteSpace: 'nowrap',
};

export default function EncabezadoNomina({
  cliente,
  cargando,
}: {
  cliente: ClienteDetalle | null;
  cargando: boolean;
}) {
  return (
    <header className="page-header" style={{ marginBottom: 0 }}>
      <nav
        aria-label="Ruta"
        style={{
          display: 'flex', alignItems: 'center', gap: 4, flexWrap: 'wrap',
          fontSize: '0.82rem', color: 'var(--text-muted)', marginBottom: 6,
        }}
      >
        <Link to="/app/clientes" style={{ color: 'var(--text-secondary)' }}>Clientes</Link>
        <ChevronRight size={13} aria-hidden="true" />
        {cliente ? (
          <Link to={`/app/clientes/${cliente.id}`} style={{ color: 'var(--text-secondary)' }}>
            {cliente.nombre}
          </Link>
        ) : (
          <span>Cliente</span>
        )}
        <ChevronRight size={13} aria-hidden="true" />
        <span style={{ color: 'var(--text-primary)' }}>Nómina</span>
      </nav>

      <h1 style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)', flexWrap: 'wrap' }}>
        Nómina de {cliente?.nombre ?? 'cliente'}
        <span
          style={{
            fontSize: '0.6em', fontWeight: 700, letterSpacing: 0.8,
            background: 'var(--accent-active)', color: 'var(--text-on-accent)',
            borderRadius: 'var(--radius-full)', padding: '3px 10px',
          }}
        >
          DEMO
        </span>
      </h1>

      {cliente ? (
        <p>
          {cliente.giro} · {etiquetaOrigen(cliente.origen)} · {cliente.num_empleados} empleados
        </p>
      ) : cargando ? (
        /* `role="status"` con texto accesible: un skeleton mudo dejaría sin
           forma de distinguir "cargando" de "falló", que es justo lo que la
           pantalla tiene que decir. */
        <p role="status">
          <span
            className="skeleton"
            aria-hidden="true"
            style={{ display: 'inline-block', width: 260, height: 14, verticalAlign: 'middle' }}
          />
          <span style={SOLO_LECTORES}>Cargando el cliente...</span>
        </p>
      ) : (
        <p style={{ color: 'var(--danger)' }}>No se pudo cargar el cliente</p>
      )}
    </header>
  );
}
