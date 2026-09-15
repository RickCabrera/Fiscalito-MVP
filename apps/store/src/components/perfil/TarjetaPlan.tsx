/**
 * El plan de la cuenta y su uso, dentro del Perfil. (T8)
 *
 * Vive en su propio archivo y no dentro de `ProfilePage` porque esa pantalla ya
 * estaba en 287 líneas contra el tope de 300 de `apps/store/CLAUDE.md`.
 *
 * ES LA ÚNICA ENTRADA A `/app/planes`. El sidebar está congelado por
 * `navigation.test.ts` con la lista exacta de cada perfil, y Planes no es una
 * herramienta diaria: se visita cuando la cartera crece. Si algún día entra al
 * sidebar, este enlace se queda igual — dos caminos a la misma pantalla no
 * estorban; cero caminos sí.
 */

import { Link } from 'react-router-dom';
import { ArrowRight, Layers } from 'lucide-react';
import { planDelPerfil, usoDeClientes } from '../../services/planes';

export default function TarjetaPlan({
  plan, clientes, conCartera,
}: {
  /** `users/{uid}.plan`. `undefined` = nunca eligió, y manda el default. */
  plan: string | undefined;
  clientes: number;
  /**
   * Si esta instalación lleva cartera de clientes.
   *
   * En modo empresa única no hay clientes que contar —hay una empresa
   * implícita— y "1 / 1 clientes" describiría una cartera que no existe.
   */
  conCartera: boolean;
}) {
  const elPlan = planDelPerfil(plan);
  const uso = usoDeClientes(elPlan, clientes);

  return (
    <div
      className="card animate-in"
      style={{
        marginBottom: 24, display: 'flex', alignItems: 'center',
        gap: 'var(--space-md)', flexWrap: 'wrap',
      }}
    >
      <div
        style={{
          width: 40, height: 40, borderRadius: 'var(--radius-sm)', flexShrink: 0,
          background: 'var(--accent-gradient)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}
      >
        <Layers size={18} color="var(--text-on-accent)" />
      </div>

      <div style={{ flex: 1, minWidth: 180 }}>
        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 1 }}>
          Plan
        </div>
        <div style={{ fontWeight: 600, fontSize: '1.02rem' }}>{elPlan.nombre}</div>
        {conCartera && (
          <div
            style={{
              fontSize: '0.85rem', marginTop: 2,
              color: uso.alLimite ? 'var(--warning)' : 'var(--text-secondary)',
              fontFamily: "'JetBrains Mono', monospace",
            }}
          >
            {uso.texto}
            {uso.alLimite ? ' · al límite' : ''}
          </div>
        )}
      </div>

      <Link to="/app/planes">
        <button className="btn-secondary" style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
          Ver planes <ArrowRight size={15} />
        </button>
      </Link>
    </div>
  );
}
