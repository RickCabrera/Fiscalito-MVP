/**
 * Rejilla de captura de deducciones personales — la misma en el tab del
 * asalariado y en el de la declaración anual (T3).
 *
 * Es presentacional a propósito: recibe los valores y los devuelve, no llama al
 * API ni decide topes. Quien calcula es `POST /api/v1/deducciones-personales`.
 */

import { AlertTriangle } from 'lucide-react';
import { CAMPOS, NIVELES_EDUCATIVOS } from '../../services/deduccionesPersonales';
import { labelStyle } from '../../utils/styles';

interface Props {
  values: Record<string, string>;
  onChange: (values: Record<string, string>) => void;
  nivelEducativo: string;
  onNivelChange: (nivel: string) => void;
}

export default function CapturaDeducciones({ values, onChange, nivelEducativo, onNivelChange }: Props) {
  const faltaNivel = parseFloat(values['colegiaturas'] || '0') > 0 && !nivelEducativo;

  return (
    <>
      {faltaNivel && (
        <div style={{
          padding: '10px 14px', borderRadius: 'var(--radius-xs)',
          background: 'var(--warning-bg)', border: '1px solid var(--warning-border)',
          fontSize: '0.8rem', color: 'var(--warning)', display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14,
        }}>
          <AlertTriangle size={14} />
          Selecciona el nivel educativo para aplicar el tope correcto de colegiaturas
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
        {CAMPOS.map((campo) => (
          <div key={campo.key}>
            <label style={labelStyle}>{campo.label}</label>
            {campo.key === 'colegiaturas' ? (
              <div style={{ display: 'flex', gap: 8 }}>
                <input className="input-field" type="number" placeholder={campo.placeholder}
                  value={values[campo.key] || ''} onChange={(e) => onChange({ ...values, [campo.key]: e.target.value })}
                  style={{ flex: 1, fontFamily: "'JetBrains Mono', monospace" }} />
                <select className="input-field" value={nivelEducativo} onChange={(e) => onNivelChange(e.target.value)}
                  style={{ width: 160, cursor: 'pointer', fontSize: '0.82rem' }}>
                  <option value="">Nivel...</option>
                  {NIVELES_EDUCATIVOS.map((n) => <option key={n} value={n}>{n}</option>)}
                </select>
              </div>
            ) : (
              <input className="input-field" type="number" placeholder={campo.placeholder}
                value={values[campo.key] || ''} onChange={(e) => onChange({ ...values, [campo.key]: e.target.value })}
                style={{ fontFamily: "'JetBrains Mono', monospace" }} />
            )}
          </div>
        ))}
      </div>
    </>
  );
}
