/**
 * Encabezado de la nómina (extraído en E-06).
 *
 * Dice DE QUIÉN es esta nómina y cómo volver a su ficha. El sidebar también lo
 * dice desde E-06, pero la migaja es la que da el camino de regreso, y el
 * título es lo que se lee cuando la pantalla está proyectada.
 *
 * O-01 · DOS COSAS QUE AQUÍ SE VOLVIERON MENTIRA CON EL PIVOTE
 * -------------------------------------------------------------
 * Las dos las cazó el test de rutas del modo empresa única, y ninguna habría
 * salido de leer el diff:
 *
 * 1. **La migaja empezaba en "Clientes"**, con enlace a `/app/clientes` — una
 *    ruta que en este modo redirige. El pivote promete que el concepto de
 *    cartera desaparece de la interfaz, y la pantalla principal lo contradecía
 *    en su primera línea.
 * 2. **La insignia "DEMO" era incondicional.** En el despacho es verdad: toda
 *    la cartera de E-02 es de demostración. Sobre la nómina real de la empresa
 *    es falsa, y encima justo al lado de su razón social.
 */

import { Link } from 'react-router-dom';
import { ChevronRight } from 'lucide-react';
import { etiquetaOrigen, type ClienteDetalle } from '../../services/despachoApi';
import { modoEmpresaUnica } from '../../services/modoEmpresa';
import { esClienteDemo } from '../../services/entorno';

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
  const empresaUnica = modoEmpresaUnica();
  /**
   * La insignia cuelga del ORIGEN del cliente, no de una constante.
   *
   * En modo despacho toda la cartera de E-02 es de demostración y sigue
   * marcada. En empresa única el cliente implícito nace `origen: 'propio'` y
   * **no** se marca: llamarle DEMO a la nómina real de la empresa, al lado de
   * su razón social, es peor que no decir nada.
   */
  const esDeDemostracion = empresaUnica ? esClienteDemo(cliente?.origen ?? '') : true;

  return (
    <header className="page-header" style={{ marginBottom: 0 }}>
      {/* Sin cartera no hay a dónde volver: `/app/clientes` redirige aquí
          mismo, así que una migaja de tres niveles sería un círculo. */}
      {!empresaUnica && (
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
      )}

      <h1 style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)', flexWrap: 'wrap' }}>
        Nómina de {cliente?.nombre || (empresaUnica ? 'la empresa' : 'cliente')}
        {esDeDemostracion && (
          <span
            style={{
              fontSize: '0.6em', fontWeight: 700, letterSpacing: 0.8,
              background: 'var(--accent-active)', color: 'var(--text-on-accent)',
              borderRadius: 'var(--radius-full)', padding: '3px 10px',
            }}
          >
            DEMO
          </span>
        )}
      </h1>

      {cliente ? (
        <p>
          {[cliente.giro, empresaUnica ? '' : etiquetaOrigen(cliente.origen),
            `${cliente.num_empleados} empleados`]
            .filter(Boolean)
            .join(' · ')}
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
          <span style={SOLO_LECTORES}>
            {empresaUnica ? 'Cargando la empresa...' : 'Cargando el cliente...'}
          </span>
        </p>
      ) : (
        <p style={{ color: 'var(--danger)' }}>
          {empresaUnica ? 'No se pudo cargar la empresa' : 'No se pudo cargar el cliente'}
        </p>
      )}
    </header>
  );
}
