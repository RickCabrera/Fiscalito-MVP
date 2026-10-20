/**
 * Campana de alertas fiscales del layout (P3-09).
 *
 * Pide el conteo de alertas abiertas al montar y al cambiar de ruta, y lleva a `/app/alertas`.
 * Si el backend no responde, la campana se queda sin número: no rompe el layout ni pinta un
 * error en cada pantalla (la página de alertas sí lo dice).
 */

import { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Bell } from 'lucide-react';
import { conteoAlertas } from '../../services/alertasApi';

export default function CampanaAlertas({ mini = false }: { mini?: boolean }) {
  const { pathname } = useLocation();
  const [conteo, setConteo] = useState<{ total: number; alta: number } | null>(null);

  useEffect(() => {
    let vivo = true;
    conteoAlertas()
      .then((c) => { if (vivo) setConteo({ total: c.total, alta: c.alta }); })
      .catch(() => { if (vivo) setConteo(null); });
    return () => { vivo = false; };
  }, [pathname]);

  const total = conteo?.total ?? 0;
  const etiqueta = total ? `Alertas fiscales: ${total} abiertas` : 'Alertas fiscales';
  return (
    <Link to="/app/alertas" aria-label={etiqueta} title={etiqueta} style={{
      position: 'relative', display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
      width: mini ? 44 : 34, height: mini ? 44 : 34, borderRadius: 'var(--radius-sm)',
      color: total ? 'var(--warning)' : 'var(--text-secondary)', textDecoration: 'none',
    }}>
      <Bell size={18} />
      {total > 0 && (
        <span data-testid="contador-alertas" style={{
          position: 'absolute', top: 0, right: 0, minWidth: 16, height: 16, padding: '0 4px',
          borderRadius: 'var(--radius-full)', fontSize: '0.62rem', fontWeight: 700,
          lineHeight: '16px', textAlign: 'center', color: 'var(--text-on-accent)',
          background: conteo && conteo.alta > 0 ? 'var(--danger)' : 'var(--warning)',
        }}>
          {total > 99 ? '99+' : total}
        </span>
      )}
    </Link>
  );
}
