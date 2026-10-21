/**
 * Captura de un servicio extra (cargo) o de un pago recibido (P5-03). El pago puede ligarse
 * al UUID de un CFDI que el despacho emitió y está en su bóveda (opcional).
 */

import { useState } from 'react';

const campo: React.CSSProperties = {
  background: 'var(--bg-input)', color: 'var(--text-primary)', border: '1px solid var(--border)',
  borderRadius: 'var(--radius-sm)', padding: '6px 8px', fontSize: '0.82rem',
};
const etiqueta: React.CSSProperties = { display: 'flex', flexDirection: 'column', gap: 4, fontSize: '0.75rem' };

export interface DatosMovimiento {
  fecha: string;
  importe: string;
  texto: string;
  extra: string;
  facturar: boolean;
}

interface Props {
  tipo: 'cargo' | 'pago';
  hoy: string;
  ocupado: boolean;
  /** Resuelve `true` si se guardó (entonces se limpia el formulario). */
  onGuardar: (d: DatosMovimiento) => Promise<boolean>;
}

export default function FormMovimiento({ tipo, hoy, ocupado, onGuardar }: Props) {
  const vacio: DatosMovimiento = { fecha: hoy, importe: '', texto: '', extra: '', facturar: false };
  const [d, setD] = useState<DatosMovimiento>(vacio);
  const poner = (k: keyof DatosMovimiento, v: string | boolean) => setD((x) => ({ ...x, [k]: v }));
  const esCargo = tipo === 'cargo';

  return (
    <form aria-label={esCargo ? 'Nuevo cargo' : 'Nuevo pago'}
      onSubmit={(e) => { e.preventDefault(); void onGuardar(d).then((ok) => { if (ok) setD(vacio); }); }}
      style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'flex-end' }}>
      <label style={etiqueta}>Fecha
        <input type="date" required style={campo} value={d.fecha} onChange={(e) => poner('fecha', e.target.value)} />
      </label>
      <label style={etiqueta}>Importe
        <input required aria-label={esCargo ? 'Importe del cargo' : 'Importe del pago'} inputMode="decimal"
          style={campo} value={d.importe} onChange={(e) => poner('importe', e.target.value)} />
      </label>
      <label style={{ ...etiqueta, flex: 1, minWidth: 160 }}>{esCargo ? 'Concepto' : 'Forma de pago'}
        <input required={esCargo} aria-label={esCargo ? 'Concepto del cargo' : 'Forma de pago'} style={campo}
          value={d.texto} onChange={(e) => poner('texto', e.target.value)}
          placeholder={esCargo ? 'Declaración anual, trámite…' : 'Transferencia, efectivo…'} />
      </label>
      {esCargo ? (
        <label style={{ ...etiqueta, flexDirection: 'row', alignItems: 'center' }}>
          <input type="checkbox" checked={d.facturar} onChange={(e) => poner('facturar', e.target.checked)} />
          Facturar
        </label>
      ) : (
        <label style={{ ...etiqueta, minWidth: 220 }}>UUID del CFDI (opcional)
          <input aria-label="UUID del CFDI" style={campo} value={d.extra}
            onChange={(e) => poner('extra', e.target.value)} />
        </label>
      )}
      <button className="btn-secondary" type="submit" disabled={ocupado}>
        {esCargo ? 'Agregar cargo' : 'Registrar pago'}
      </button>
    </form>
  );
}
