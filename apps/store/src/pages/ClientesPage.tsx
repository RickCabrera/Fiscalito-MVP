/**
 * Clientes del despacho — STUB de E-01.
 *
 * E-01 solo agrega el perfil de contador y su navegación. La lista real (3
 * clientes demo servidos por `GET /api/v1/despacho/clientes`), el selector de
 * cliente activo y la ficha `/clientes/:id` son E-02, que reemplaza el cuerpo
 * de esta página.
 *
 * Existe desde ya porque el sidebar del contador la enlaza: sin ruta, el enlace
 * deja el área de contenido en blanco (no hay catch-all bajo `/app`).
 */

import { Users } from 'lucide-react';
import { useProfile } from '../context/ProfileContext';

export default function ClientesPage() {
  const { profile } = useProfile();
  const despacho = profile.nombreDespacho.trim();

  return (
    <div className="page-container">
      <div className="page-header animate-in">
        <h1>Clientes</h1>
        <p>{despacho ? `Cartera de ${despacho}` : 'Cartera del despacho'}</p>
      </div>

      <div
        className="card animate-in"
        style={{
          animationDelay: '0.1s',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 12,
          padding: '56px 24px',
          textAlign: 'center',
        }}
      >
        <div
          style={{
            width: 56,
            height: 56,
            borderRadius: 'var(--radius-sm)',
            background: 'var(--bg-input)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <Users size={24} color="var(--text-muted)" />
        </div>
        <div style={{ fontSize: '1.05rem', fontWeight: 600 }}>La cartera de clientes llega en la siguiente entrega</div>
        <p style={{ fontSize: '0.87rem', color: 'var(--text-secondary)', maxWidth: 420 }}>
          Aquí va la cartera del despacho: cada cliente con sus empleados, su prima de riesgo y
          su nómina. Mientras tanto, la nómina de demostración vive en el enlace “Nómina” del
          menú.
        </p>
      </div>
    </div>
  );
}
