/**
 * Tab de pagos provisionales de PERSONA MORAL (régimen 601) — T6, CASCARÓN.
 *
 * QUÉ ES Y QUÉ NO ES
 * ------------------
 * Es una **estimación de servilleta que se calcula en el navegador**, no una
 * pre-declaración. El motor de personas morales no existe: `calculadora.py`
 * sólo sabe de personas físicas, y `routes/declaraciones.py` rechaza el 601 con
 * un 400 antes de llegar a él (T6). Por eso esta pantalla **no llama al API**:
 * si llamara, o mentiría el número o reventaría con el guard.
 *
 * Lo único que hace es la aritmética del Art. 14 LISR en su forma más corta:
 *
 *     utilidad fiscal estimada = ingresos nominales × coeficiente de utilidad
 *     ISR estimado             = utilidad fiscal estimada × 30 %   (Art. 9 LISR)
 *
 * Lo que un pago provisional real lleva ENCIMA de eso y aquí NO se resta —
 * pagos provisionales anteriores del ejercicio, retenciones, PTU pagada,
 * pérdidas fiscales pendientes de amortizar, el ajuste anual por inflación— se
 * dice en pantalla en vez de esconderse: un número que sale bajo por olvidar
 * una resta se lee igual de creíble que uno correcto.
 *
 * El banner amarillo no es decorativo: es la única señal que distingue esta
 * pantalla de las que sí pasan por el motor determinístico.
 */

import { useState } from 'react';
import { fmtMoney } from '../../utils/format';
import { labelStyle } from '../../utils/styles';
import { AlertTriangle, Building2, Calculator } from 'lucide-react';

/** Tasa del ISR de personas morales — Art. 9 LISR. */
const TASA_ISR_PM = 0.30;

/** Lo que el pago provisional real lleva y esta estimación no. */
const LO_QUE_FALTA = [
  'Pagos provisionales del ejercicio ya efectuados',
  'ISR retenido por instituciones del sistema financiero',
  'PTU pagada en el ejercicio (Art. 14, fracc. II)',
  'Pérdidas fiscales de ejercicios anteriores pendientes de amortizar',
  'Ajuste anual por inflación',
];

export default function PagosProvisionalesPMTab() {
  const [coeficiente, setCoeficiente] = useState('');
  const [ingresos, setIngresos] = useState('');

  const cu = parseFloat(coeficiente);
  const ing = parseFloat(ingresos);
  // El coeficiente se captura en DECIMAL (0.0823), que es como lo arroja la
  // declaración anual del ejercicio anterior. Un `> 1` casi siempre es alguien
  // tecleando "8.23" por 8.23 %, así que se rechaza en vez de estimar un ISR
  // ocho veces mayor que los ingresos.
  const cuValido = Number.isFinite(cu) && cu > 0 && cu <= 1;
  const ingValido = Number.isFinite(ing) && ing > 0;
  const listo = cuValido && ingValido;

  const utilidad = listo ? ing * cu : 0;
  const isr = utilidad * TASA_ISR_PM;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* La advertencia va ARRIBA del formulario, no debajo del resultado:
          quien captura tiene que saber qué está capturando antes de creerle
          al número. */}
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
            Estimación — motor PM en desarrollo
          </strong>
          <p style={{ margin: '4px 0 0', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
            Este cálculo se hace en tu navegador y no pasa por el motor fiscal. Sirve para
            dimensionar el pago, no para presentarlo.
          </p>
        </div>
      </div>

      <div className="card">
        <h3 style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '1rem', fontWeight: 600, marginBottom: 6 }}>
          <Building2 size={18} /> Pago provisional de ISR — Personas morales (601)
        </h3>
        <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: 20 }}>
          Ingresos nominales del periodo × coeficiente de utilidad × 30 % (Arts. 9 y 14 LISR).
        </p>

        <div style={{ display: 'grid', gap: 16, gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))' }}>
          <div>
            <label style={labelStyle} htmlFor="pm-coeficiente">
              Coeficiente de utilidad (decimal)
            </label>
            <input
              id="pm-coeficiente"
              className="input-field"
              type="number"
              step="0.0001"
              min="0"
              max="1"
              placeholder="Ej: 0.0823"
              value={coeficiente}
              onChange={(e) => setCoeficiente(e.target.value)}
              style={{ fontFamily: "'JetBrains Mono', monospace" }}
            />
            <p style={{ margin: '6px 0 0', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              El de tu declaración anual del ejercicio anterior. 8.23 % se captura como 0.0823.
            </p>
          </div>

          <div>
            <label style={labelStyle} htmlFor="pm-ingresos">
              Ingresos nominales del periodo
            </label>
            <input
              id="pm-ingresos"
              className="input-field"
              type="number"
              step="0.01"
              min="0"
              placeholder="Ej: 1250000"
              value={ingresos}
              onChange={(e) => setIngresos(e.target.value)}
              style={{ fontFamily: "'JetBrains Mono', monospace" }}
            />
            <p style={{ margin: '6px 0 0', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              Acumulados desde el inicio del ejercicio hasta el último día del mes que declaras.
            </p>
          </div>
        </div>

        {coeficiente !== '' && !cuValido && (
          <p style={{ margin: '14px 0 0', fontSize: '0.8rem', color: 'var(--warning)' }}>
            El coeficiente va en decimal, entre 0 y 1.
          </p>
        )}
      </div>

      {listo && (
        <div className="card">
          <h3 style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '1rem', fontWeight: 600, marginBottom: 16 }}>
            <Calculator size={18} /> Estimación
          </h3>

          <Renglon etiqueta="Ingresos nominales" valor={fmtMoney(ing)} />
          <Renglon
            etiqueta={`Utilidad fiscal estimada (× ${cu})`}
            valor={fmtMoney(utilidad)}
          />
          <Renglon
            etiqueta={`ISR estimado (× ${(TASA_ISR_PM * 100).toFixed(0)} %)`}
            valor={fmtMoney(isr)}
            destacado
          />

          <p style={{ margin: '18px 0 6px', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
            <strong>Esta estimación NO resta:</strong>
          </p>
          <ul style={{ margin: 0, paddingLeft: 18, fontSize: '0.78rem', color: 'var(--text-muted)' }}>
            {LO_QUE_FALTA.map((item) => <li key={item} style={{ marginBottom: 2 }}>{item}</li>)}
          </ul>
        </div>
      )}
    </div>
  );
}

function Renglon({ etiqueta, valor, destacado = false }: {
  etiqueta: string;
  valor: string;
  destacado?: boolean;
}) {
  return (
    <div style={{
      display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 16,
      padding: '10px 0', borderTop: '1px solid var(--border)',
    }}>
      <span style={{
        fontSize: destacado ? '0.9rem' : '0.85rem',
        fontWeight: destacado ? 600 : 400,
        color: destacado ? 'var(--text-primary)' : 'var(--text-secondary)',
      }}>
        {etiqueta}
      </span>
      <span style={{
        fontFamily: "'JetBrains Mono', monospace",
        fontSize: destacado ? '1.15rem' : '0.9rem',
        fontWeight: destacado ? 700 : 500,
        color: destacado ? 'var(--warning)' : 'var(--text-primary)',
      }}>
        {valor}
      </span>
    </div>
  );
}
