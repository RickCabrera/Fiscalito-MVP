/**
 * Panel de checador en vivo (D-07). DEMO: se borra en F2.
 *
 * E-06: dejó de traer su propia card y su propio título — ahora es el contenido
 * del **paso 1** y el encabezado lo pone `PasoNomina`. Dos encabezados encima
 * del mismo contenido ("1. Checadas recibidas" y "Checador en vivo") competían
 * por decir lo mismo.
 */

import { Radio } from 'lucide-react';
import type { EventoChecada } from '../../services/nominaDemoApi';
import { envoltura, fila, tabla, td, th, thNum } from './estilosTabla';
import { modoEmpresaUnica } from '../../services/modoEmpresa';

/**
 * Contador de checadas, para el encabezado del paso.
 *
 * Vive aquí y no en la página porque es del panel: si el panel cambia de forma,
 * su contador cambia con él.
 */
export function ContadorChecadas({ total }: { total: number }) {
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'baseline',
        gap: 6,
        padding: '4px 12px',
        borderRadius: 'var(--radius-full)',
        background: 'var(--teal-bg)',
        color: 'var(--accent-active)',
        fontSize: '0.8rem',
        fontWeight: 600,
        whiteSpace: 'nowrap',
      }}
    >
      <span style={{ fontFamily: "'JetBrains Mono', monospace", fontVariantNumeric: 'tabular-nums' }}>
        {total}
      </span>
      checadas
    </span>
  );
}

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
    <>
      {error && (
        <p
          role="alert"
          style={{
            margin: 0,
            padding: 'var(--space-sm) var(--space-md)',
            borderRadius: 'var(--radius-sm)',
            background: 'var(--danger-bg)',
            border: '1px solid var(--danger-border)',
            color: 'var(--danger)',
            fontSize: '0.88rem',
          }}
        >
          No se pudieron leer las checadas: {error}
        </p>
      )}

      {!error && eventos.length === 0 && (
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: 6,
            padding: 'var(--space-xl) var(--space-md)',
            textAlign: 'center',
          }}
        >
          <Radio size={22} color="var(--text-muted)" />
          <div style={{ fontWeight: 600, fontSize: '0.95rem' }}>Sin checadas todavía</div>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', margin: 0, maxWidth: 420 }}>
            {modoEmpresaUnica()
              ? 'Corre el simulador del checador, o conecta el dispositivo.'
              : 'Corre el simulador del checador para este cliente, o conecta el dispositivo.'}
          </p>
        </div>
      )}

      {ultimos.length > 0 && (
        <div style={envoltura}>
          <table style={tabla(560)}>
            <thead>
              <tr>
                <th style={th}>Empleado</th>
                <th style={th}>Día</th>
                <th style={thNum}>Hora</th>
                <th style={th}>Tipo</th>
              </tr>
            </thead>
            <tbody>
              {ultimos.map((e, i) => (
                <tr key={`${e.empleado_no}-${e.timestamp}-${e.tipo}`} style={fila(i)}>
                  <td style={td}>
                    {e.raw?.name ?? e.empleado_no}{' '}
                    <span style={{ color: 'var(--text-muted)' }}>({e.empleado_no})</span>
                  </td>
                  <td style={{ ...td, fontFamily: "'JetBrains Mono', monospace" }}>
                    {fechaLocal(e.timestamp)}
                  </td>
                  <td
                    style={{
                      ...td,
                      textAlign: 'right',
                      fontFamily: "'JetBrains Mono', monospace",
                      fontVariantNumeric: 'tabular-nums',
                    }}
                  >
                    {horaLocal(e.timestamp)}
                  </td>
                  <td style={{ ...td, color: 'var(--text-secondary)' }}>{e.tipo}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
