/**
 * Tab Buzón de Contabilito (T7) — pantalla de "todavía no", a propósito.
 *
 * El envío de contabilidad electrónica al buzón tributario se firma con la
 * **e.firma** del contribuyente y se sella. Nada de eso existe en el producto,
 * y una pantalla que insinuara lo contrario sería la más cara de desmentir de
 * toda la app. Se dice lo que falta, en concreto, y no hay un botón que
 * prometa lo que no hace.
 */

import { Inbox, KeyRound } from 'lucide-react';

const LO_QUE_FALTA = [
  'Carga de la e.firma (.cer y .key) y su contraseña',
  'Sellado y firmado de los XML de catálogo, balanza y pólizas',
  'Generación del XML conforme al Anexo 24 (catálogo, balanza mensual y pólizas del periodo)',
  'Envío al buzón tributario y acuse de recepción del SAT',
];

export default function BuzonTab() {
  return (
    <div className="card" style={{ textAlign: 'center', padding: 'var(--space-lg)' }}>
      <Inbox size={30} color="var(--text-muted)" />
      <h3 style={{ margin: '12px 0 6px', fontSize: '1rem', fontWeight: 600 }}>
        Requiere e.firma — próximamente
      </h3>
      <p style={{ margin: '0 auto', maxWidth: 520, fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
        La contabilidad electrónica se envía firmada con la e.firma del contribuyente. Hoy
        Contabilito arma el catálogo, las pólizas y la balanza; el envío todavía no.
      </p>

      <ul style={{
        listStyle: 'none', margin: '18px auto 0', padding: 0,
        maxWidth: 520, textAlign: 'left',
      }}>
        {LO_QUE_FALTA.map((f) => (
          <li key={f} style={{
            display: 'flex', alignItems: 'flex-start', gap: 8,
            padding: '5px 0', fontSize: '0.82rem', color: 'var(--text-muted)',
          }}>
            <KeyRound size={13} style={{ flexShrink: 0, marginTop: 3 }} />
            {f}
          </li>
        ))}
      </ul>
    </div>
  );
}
