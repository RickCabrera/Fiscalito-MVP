/**
 * Un paso numerado del flujo de nómina (E-06). DEMO: se borra en F2.
 *
 * POR QUÉ EXISTE
 * --------------
 * La pantalla era un panel, dos fechas y tres botones sueltos: quien la ve por
 * primera vez —en la demo, proyectada— no sabe en qué orden se usan ni qué hace
 * cada uno. Aquí cada paso lleva su número, su título y **una línea de qué
 * hace**, y dice si todavía no se puede usar y por qué.
 *
 * EL ESTADO SE DERIVA, NO SE GUARDA
 * ---------------------------------
 * `estado` lo calcula quien lo usa a partir de los datos que ya tiene (ficha,
 * cierre, nómina). Un `useState` de "paso actual" sería un segundo origen de
 * verdad que puede quedar desincronizado de los datos que la pantalla pinta.
 *
 * Presentacional puro: sin fetch, sin contexto, sin router.
 */

import { Check } from 'lucide-react';
import { tituloSeccion } from './estilosTabla';

export type EstadoPaso = 'bloqueado' | 'disponible' | 'listo';

export default function PasoNomina({
  numero,
  titulo,
  descripcion,
  estado,
  motivoBloqueo,
  extra,
  children,
}: {
  numero: number;
  titulo: string;
  descripcion: string;
  estado: EstadoPaso;
  /** Qué falta para poder usarlo. Obligatorio de hecho cuando está bloqueado. */
  motivoBloqueo?: string;
  /** Dato al margen derecho del encabezado (el contador de checadas). */
  extra?: React.ReactNode;
  children: React.ReactNode;
}) {
  const listo = estado === 'listo';
  const bloqueado = estado === 'bloqueado';

  const colorInsignia = listo
    ? 'var(--success)'
    : bloqueado
      ? 'var(--text-muted)'
      : 'var(--accent-active)';

  return (
    <section
      className="card"
      aria-label={`Paso ${numero}: ${titulo}`}
      style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}
    >
      <header style={{ display: 'flex', alignItems: 'flex-start', gap: 'var(--space-sm)' }}>
        <span
          aria-hidden="true"
          style={{
            flexShrink: 0,
            width: 26,
            height: 26,
            borderRadius: '50%',
            border: `1.5px solid ${colorInsignia}`,
            color: listo ? 'var(--text-on-accent)' : colorInsignia,
            background: listo ? 'var(--success)' : 'transparent',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '0.78rem',
            fontWeight: 700,
            fontFamily: "'JetBrains Mono', monospace",
          }}
        >
          {listo ? <Check size={15} /> : numero}
        </span>
        <div style={{ minWidth: 0, flex: 1 }}>
          <h2 style={tituloSeccion}>
            {numero}. {titulo}
          </h2>
          <p
            style={{
              margin: '2px 0 0',
              fontSize: '0.82rem',
              color: 'var(--text-secondary)',
            }}
          >
            {descripcion}
          </p>
          {bloqueado && motivoBloqueo && (
            <p
              style={{
                margin: '6px 0 0',
                fontSize: '0.8rem',
                color: 'var(--text-muted)',
                fontStyle: 'italic',
              }}
            >
              {motivoBloqueo}
            </p>
          )}
        </div>
        {extra}
      </header>

      {children}
    </section>
  );
}
