/**
 * Vistas del calendario de la cartera (P3-10): semana (7 columnas), mes (cuadrícula) y
 * agenda (lista por día, sólo los días con algo).
 */

import { iso, sumarDias, type ObligacionCartera, type TareaAgenda, type Vista } from '../../services/agendaApi';
import ItemsDelDia from './ItemsDelDia';

const DIAS = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom'];

interface Props {
  vista: Vista;
  desde: Date;
  hasta: Date;
  hoy: Date;
  obligaciones: ObligacionCartera[];
  tareas: TareaAgenda[];
  onMarcar: (o: ObligacionCartera) => void;
  onTarea: (t: TareaAgenda) => void;
}

function porDia<T>(xs: T[], fecha: (x: T) => string): Map<string, T[]> {
  const m = new Map<string, T[]>();
  for (const x of xs) m.set(fecha(x), [...(m.get(fecha(x)) ?? []), x]);
  return m;
}

export default function VistaCalendario(p: Props) {
  const obl = porDia(p.obligaciones, (o) => o.fecha_limite);
  const tar = porDia(p.tareas, (t) => t.fecha);
  const dias: Date[] = [];
  for (let d = p.desde; d <= p.hasta; d = sumarDias(d, 1)) dias.push(d);
  const hoy = iso(p.hoy);

  if (p.vista === 'agenda') {
    const conAlgo = dias.filter((d) => obl.has(iso(d)) || tar.has(iso(d)));
    if (conAlgo.length === 0) {
      return <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>Sin vencimientos ni tareas en el periodo.</p>;
    }
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {conAlgo.map((d) => (
          <section key={iso(d)} aria-label={`Día ${iso(d)}`}>
            <h3 style={{ fontSize: '0.85rem', margin: '0 0 6px', color: iso(d) === hoy ? 'var(--accent-active)' : 'var(--text-primary)' }}>
              {DIAS[(d.getDay() + 6) % 7]} {d.getDate()}/{d.getMonth() + 1}/{d.getFullYear()}
            </h3>
            <ItemsDelDia obligaciones={obl.get(iso(d)) ?? []} tareas={tar.get(iso(d)) ?? []}
              onMarcar={p.onMarcar} onTarea={p.onTarea} />
          </section>
        ))}
      </div>
    );
  }

  const compacto = p.vista === 'mes';
  const mesAncla = p.vista === 'mes' ? dias[Math.min(10, dias.length - 1)].getMonth() : -1;
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, minmax(0, 1fr))', gap: 6 }}>
      {DIAS.map((d) => (
        <div key={d} style={{ fontSize: '0.72rem', color: 'var(--text-muted)', textAlign: 'center' }}>{d}</div>
      ))}
      {dias.map((d) => (
        <section key={iso(d)} aria-label={`Día ${iso(d)}`} style={{
          minHeight: compacto ? 70 : 160, padding: 6, borderRadius: 'var(--radius-sm)',
          border: `1px solid ${iso(d) === hoy ? 'var(--accent-active)' : 'var(--border)'}`,
          background: 'var(--bg-card)', opacity: compacto && d.getMonth() !== mesAncla ? 0.45 : 1,
          display: 'flex', flexDirection: 'column', gap: 4, minWidth: 0,
        }}>
          <div style={{ fontSize: '0.72rem', fontWeight: 600 }}>{d.getDate()}</div>
          <ItemsDelDia obligaciones={obl.get(iso(d)) ?? []} tareas={tar.get(iso(d)) ?? []}
            compacto={compacto} onMarcar={p.onMarcar} onTarea={p.onTarea} />
        </section>
      ))}
    </div>
  );
}
