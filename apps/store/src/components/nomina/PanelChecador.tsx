/** Panel de checador en vivo (D-07). DEMO: se borra en F2. */

import { Radio } from 'lucide-react';
import type { EventoChecada } from '../../services/nominaDemoApi';

function horaLocal(iso: string): string {
  // La checada trae su offset (-06:00). Se muestra tal cual la mandó el
  // aparato, sin convertir a la zona del navegador: el retardo se mide en la
  // hora local del evento y una conversión haría que la pantalla y la tabla de
  // incidencias no coincidieran.
  const m = iso.match(/T(\d{2}:\d{2}):\d{2}/);
  return m ? m[1] : iso;
}

function fechaLocal(iso: string): string {
  return iso.slice(0, 10);
}

export default function PanelChecador({
  eventos,
  error,
}: {
  eventos: EventoChecada[];
  error: string | null;
}) {
  const ultimos = [...eventos].reverse().slice(0, 12);
  return (
    <section
      style={{
        background: 'var(--bg-surface)',
        border: '1px solid var(--border)',
        borderRadius: 12,
        padding: 20,
      }}
    >
      <header style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        <Radio size={18} color="var(--accent-active)" />
        <h2 style={{ fontSize: '1rem', margin: 0 }}>Checador en vivo</h2>
        <span style={{ marginLeft: 'auto', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
          {eventos.length} checadas
        </span>
      </header>

      {error && (
        <p role="alert" style={{ color: 'var(--danger)', fontSize: '0.9rem' }}>
          No se pudieron leer las checadas: {error}
        </p>
      )}

      {!error && eventos.length === 0 && (
        <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
          Sin checadas todavía. Corre el simulador del checador o conecta el dispositivo.
        </p>
      )}

      {ultimos.length > 0 && (
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem' }}>
          <thead>
            <tr style={{ textAlign: 'left', color: 'var(--text-muted)' }}>
              <th style={{ padding: '4px 0' }}>Empleado</th>
              <th>Día</th>
              <th>Hora</th>
              <th>Tipo</th>
            </tr>
          </thead>
          <tbody>
            {ultimos.map((e) => (
              <tr key={`${e.empleado_no}-${e.timestamp}-${e.tipo}`}>
                <td style={{ padding: '4px 0' }}>
                  {e.raw?.name ?? e.empleado_no}{' '}
                  <span style={{ color: 'var(--text-muted)' }}>({e.empleado_no})</span>
                </td>
                <td>{fechaLocal(e.timestamp)}</td>
                <td>{horaLocal(e.timestamp)}</td>
                <td>{e.tipo}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
