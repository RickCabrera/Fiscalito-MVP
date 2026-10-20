/**
 * Iguala mensual y condiciones de cobro de un cliente (P5-03): monto, día del cargo, días de
 * crédito, contacto de cobranza y recordatorio automático.
 */

import { useState } from 'react';
import { HONORARIOS_VACIOS, type Honorarios } from '../../services/cobranzaApi';

const campo: React.CSSProperties = {
  background: 'var(--bg-input)', color: 'var(--text-primary)', border: '1px solid var(--border)',
  borderRadius: 'var(--radius-sm)', padding: '6px 8px', fontSize: '0.82rem',
};
const etiqueta: React.CSSProperties = { display: 'flex', flexDirection: 'column', gap: 4, fontSize: '0.75rem' };

interface Props {
  inicial: Honorarios | null;
  ocupado: boolean;
  onGuardar: (h: Honorarios) => void;
}

export default function FormHonorarios({ inicial, ocupado, onGuardar }: Props) {
  const [h, setH] = useState<Honorarios>(inicial ?? HONORARIOS_VACIOS);
  const poner = <K extends keyof Honorarios>(k: K, v: Honorarios[K]) => setH((x) => ({ ...x, [k]: v }));
  const numero = (k: 'dia_cargo' | 'dias_credito' | 'dias_entre_recordatorios') =>
    (e: React.ChangeEvent<HTMLInputElement>) => poner(k, Number(e.target.value) || 0);

  return (
    <form aria-label="Honorarios" onSubmit={(e) => { e.preventDefault(); onGuardar(h); }}
      style={{ display: 'grid', gap: 10, gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', alignItems: 'end' }}>
      <label style={etiqueta}>Iguala mensual
        <input aria-label="Iguala mensual" style={campo} inputMode="decimal" value={h.iguala_mensual}
          onChange={(e) => poner('iguala_mensual', e.target.value)} />
      </label>
      <label style={etiqueta}>Concepto
        <input aria-label="Concepto de la iguala" style={campo} value={h.concepto}
          onChange={(e) => poner('concepto', e.target.value)} />
      </label>
      <label style={etiqueta}>Día del cargo (1-28)
        <input type="number" min={1} max={28} style={campo} value={h.dia_cargo} onChange={numero('dia_cargo')} />
      </label>
      <label style={etiqueta}>Días de crédito
        <input type="number" min={0} max={180} style={campo} value={h.dias_credito} onChange={numero('dias_credito')} />
      </label>
      <label style={etiqueta}>Correo de cobranza
        <input type="email" aria-label="Correo de cobranza" style={campo} value={h.correo}
          onChange={(e) => poner('correo', e.target.value)} />
      </label>
      <label style={etiqueta}>WhatsApp de cobranza
        <input aria-label="WhatsApp de cobranza" style={campo} value={h.telefono} placeholder="+52…"
          onChange={(e) => poner('telefono', e.target.value)} />
      </label>
      <label style={{ ...etiqueta, flexDirection: 'row', alignItems: 'center' }}>
        <input type="checkbox" checked={h.activo} onChange={(e) => poner('activo', e.target.checked)} />
        Generar la iguala cada mes
      </label>
      <label style={{ ...etiqueta, flexDirection: 'row', alignItems: 'center' }}>
        <input type="checkbox" checked={h.facturar} onChange={(e) => poner('facturar', e.target.checked)} />
        Marcar para facturar
      </label>
      <label style={{ ...etiqueta, flexDirection: 'row', alignItems: 'center' }}>
        <input type="checkbox" checked={h.recordatorio_automatico}
          onChange={(e) => poner('recordatorio_automatico', e.target.checked)} />
        Recordatorio automático si hay vencido
      </label>
      {h.recordatorio_automatico && (
        <>
          <label style={etiqueta}>Canal
            <select style={campo} value={h.canal_recordatorio}
              onChange={(e) => poner('canal_recordatorio', e.target.value as Honorarios['canal_recordatorio'])}>
              <option value="correo">Correo</option>
              <option value="whatsapp">WhatsApp</option>
            </select>
          </label>
          <label style={etiqueta}>Cada cuántos días
            <input type="number" min={1} max={90} style={campo} value={h.dias_entre_recordatorios}
              onChange={numero('dias_entre_recordatorios')} />
          </label>
        </>
      )}
      <button className="btn-primary" type="submit" disabled={ocupado}>Guardar honorarios</button>
    </form>
  );
}
