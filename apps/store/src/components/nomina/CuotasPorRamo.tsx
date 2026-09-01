/**
 * Cuotas patronales por ramo (D-07). DEMO: se borra en F2.
 *
 * El desglose por ramo no es adorno: es lo que permite conciliar contra la EMA
 * y la EBA renglón por renglón.
 */

import { AlertTriangle } from 'lucide-react';
import { fmtMoney } from '../../utils/format';
import type { NominaPeriodo, PorcionConsolidada } from '../../services/nominaDemoApi';

const NOMBRE_RAMO: Record<string, string> = {
  eym_cuota_fija: 'Enfermedades y Maternidad — cuota fija',
  eym_excedente: 'EyM — excedente sobre 3 UMA',
  eym_prestaciones_dinero: 'EyM — prestaciones en dinero',
  eym_gastos_medicos_pensionados: 'EyM — gastos médicos de pensionados',
  invalidez_vida: 'Invalidez y Vida',
  guarderias: 'Guarderías y Prestaciones Sociales',
  riesgos_trabajo: 'Riesgos de Trabajo',
  retiro: 'Retiro',
  ceav: 'Cesantía en Edad Avanzada y Vejez',
  infonavit: 'Infonavit',
};

function Bloque({ titulo, porcion }: { titulo: string; porcion: PorcionConsolidada }) {
  return (
    <div style={{ flex: '1 1 260px' }}>
      <h3 style={{ fontSize: '0.9rem', color: 'var(--text-muted)' }}>{titulo}</h3>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
        <tbody>
          {Object.entries(porcion.por_ramo).map(([clave, monto]) => (
            <tr key={clave}>
              <td style={{ padding: '3px 0' }}>{NOMBRE_RAMO[clave] ?? clave}</td>
              <td style={{ textAlign: 'right' }}>{fmtMoney(Number(monto))}</td>
            </tr>
          ))}
          <tr style={{ borderTop: '1px solid var(--border)', fontWeight: 700 }}>
            <td style={{ padding: '5px 0' }}>Patronal</td>
            <td style={{ textAlign: 'right' }}>{fmtMoney(Number(porcion.total_patron))}</td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}

export default function CuotasPorRamo({ nomina }: { nomina: NominaPeriodo }) {
  return (
    <section
      style={{
        background: 'var(--bg-surface)',
        border: '1px solid var(--border)',
        borderRadius: 12,
        padding: 20,
      }}
    >
      <h2 style={{ fontSize: '1rem', marginTop: 0 }}>Cuotas devengadas en el periodo</h2>

      {/* Es la diferencia entre informar y engañar: una quincena trae media
          mensualidad de EyM/IyV, no el entero del Art. 39. Viene del backend
          para que la pantalla no invente el texto. */}
      {nomina.advertencias.map((a) => (
        <p
          key={a}
          role="note"
          style={{
            display: 'flex',
            gap: 8,
            alignItems: 'flex-start',
            background: 'var(--warning-bg)',
            border: '1px solid var(--warning-border)',
            borderRadius: 8,
            padding: '8px 12px',
            fontSize: '0.85rem',
          }}
        >
          <AlertTriangle size={16} style={{ flexShrink: 0, marginTop: 2 }} />
          <span>{a}</span>
        </p>
      ))}

      <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap' }}>
        <Bloque titulo="Ramos de entero mensual" porcion={nomina.porcion_mensual} />
        <Bloque titulo="Ramos de entero bimestral" porcion={nomina.porcion_bimestral} />
      </div>
    </section>
  );
}
