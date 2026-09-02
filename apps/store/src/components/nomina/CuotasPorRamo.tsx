/**
 * Cuotas patronales por ramo (D-07). DEMO: se borra en F2.
 *
 * El desglose por ramo no es adorno: es lo que permite conciliar contra la EMA
 * y la EBA renglón por renglón.
 */

import { AlertTriangle } from 'lucide-react';
import { fmtMoney } from '../../utils/format';
import type { NominaPeriodo, PorcionConsolidada } from '../../services/nominaDemoApi';
import { td, tdNum, tdNumFuerte, tituloSeccion } from './estilosTabla';

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
    <div style={{ flex: '1 1 300px', minWidth: 0 }}>
      <h3
        style={{
          fontSize: '0.75rem',
          fontWeight: 600,
          textTransform: 'uppercase',
          letterSpacing: 0.5,
          color: 'var(--text-muted)',
          margin: '0 0 var(--space-xs)',
        }}
      >
        {titulo}
      </h3>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', minWidth: 280, borderCollapse: 'collapse', fontSize: '0.85rem' }}>
          <tbody>
            {Object.entries(porcion.por_ramo).map(([clave, monto]) => (
              <tr key={clave}>
                <td style={{ ...td, color: 'var(--text-secondary)' }}>
                  {NOMBRE_RAMO[clave] ?? clave}
                </td>
                <td style={tdNum}>{fmtMoney(Number(monto))}</td>
              </tr>
            ))}
            <tr style={{ borderTop: '2px solid var(--border-active)' }}>
              <td style={{ ...td, fontWeight: 700 }}>Patronal</td>
              <td style={tdNumFuerte}>{fmtMoney(Number(porcion.total_patron))}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function CuotasPorRamo({ nomina }: { nomina: NominaPeriodo }) {
  return (
    <section className="card" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
      <h2 style={tituloSeccion}>Cuotas devengadas en el periodo</h2>

      {/* Es la diferencia entre informar y engañar: una quincena trae media
          mensualidad de EyM/IyV, no el entero del Art. 39. Viene del backend
          para que la pantalla no invente el texto. */}
      {nomina.advertencias.map((a) => (
        <p
          key={a}
          role="note"
          style={{
            display: 'flex',
            gap: 'var(--space-xs)',
            alignItems: 'flex-start',
            margin: 0,
            background: 'var(--warning-bg)',
            border: '1px solid var(--warning-border)',
            borderRadius: 'var(--radius-sm)',
            padding: 'var(--space-sm) var(--space-md)',
            fontSize: '0.85rem',
            color: 'var(--text-primary)',
          }}
        >
          <AlertTriangle size={16} style={{ flexShrink: 0, marginTop: 2 }} />
          <span>{a}</span>
        </p>
      ))}

      <div style={{ display: 'flex', gap: 'var(--space-xl)', flexWrap: 'wrap' }}>
        <Bloque titulo="Ramos de entero mensual" porcion={nomina.porcion_mensual} />
        <Bloque titulo="Ramos de entero bimestral" porcion={nomina.porcion_bimestral} />
      </div>
    </section>
  );
}
