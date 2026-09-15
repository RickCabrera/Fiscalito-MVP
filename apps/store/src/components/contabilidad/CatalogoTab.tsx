/**
 * Tab Catálogo de Contabilito (T7).
 *
 * Pinta el subconjunto del código agrupador del SAT que trae `catalogoSAT.ts`,
 * agrupado por rubro. El aviso de arriba **no es decorativo**: los códigos y
 * los nombres están pendientes de contrastar contra el Anexo 24 publicado, y
 * un catálogo contable equivocado se ve igual que uno correcto.
 */

import { AlertTriangle, BookOpen } from 'lucide-react';
import {
  CATALOGO_SAT, ETIQUETA_RUBRO, ORDEN_RUBROS, FUENTE_CATALOGO,
} from '../../services/contabilidad/catalogoSAT';
import { thStyle, tdStyle } from '../../utils/styles';

export default function CatalogoTab() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div
        role="status"
        style={{
          display: 'flex', alignItems: 'flex-start', gap: 10,
          padding: '12px 14px', borderRadius: 'var(--radius)',
          background: 'var(--warning-bg)', border: '1px solid var(--warning-border)',
        }}
      >
        <AlertTriangle size={18} style={{ color: 'var(--warning)', flexShrink: 0, marginTop: 1 }} />
        <div>
          <strong style={{ fontSize: '0.85rem', color: 'var(--warning)' }}>
            Catálogo {FUENTE_CATALOGO} — no lo subas al buzón tributario
          </strong>
          <p style={{ margin: '4px 0 0', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
            Es un subconjunto de {CATALOGO_SAT.length} cuentas de primer nivel del código
            agrupador del SAT (Anexo 24 de la RMF), escrito sin el documento oficial enfrente.
            Sirve para ver la mecánica de las pólizas, no como catálogo definitivo.
          </p>
        </div>
      </div>

      <div className="card">
        <h3 style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '1rem', fontWeight: 600, marginBottom: 16 }}>
          <BookOpen size={18} /> Código agrupador SAT
        </h3>

        {ORDEN_RUBROS.map((rubro) => {
          const cuentas = CATALOGO_SAT.filter((c) => c.rubro === rubro);
          if (cuentas.length === 0) return null;
          return (
            <div key={rubro} style={{ marginBottom: 20 }}>
              <div style={{
                fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase',
                letterSpacing: 1, marginBottom: 6,
              }}>
                {ETIQUETA_RUBRO[rubro]}
              </div>
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--border)' }}>
                      <th style={{ ...thStyle, width: 90 }}>Código</th>
                      <th style={thStyle}>Cuenta</th>
                      <th style={{ ...thStyle, width: 120 }}>Naturaleza</th>
                    </tr>
                  </thead>
                  <tbody>
                    {cuentas.map((c) => (
                      <tr key={c.codigo} style={{ borderBottom: '1px solid var(--border)' }}>
                        <td style={{ ...tdStyle, fontFamily: "'JetBrains Mono', monospace", color: 'var(--teal-light)' }}>
                          {c.codigo}
                        </td>
                        <td style={{ ...tdStyle, color: 'var(--text-primary)' }}>{c.nombre}</td>
                        <td style={tdStyle}>{c.naturaleza === 'deudora' ? 'Deudora' : 'Acreedora'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
