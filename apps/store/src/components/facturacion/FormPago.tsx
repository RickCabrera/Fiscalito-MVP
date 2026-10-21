/**
 * CFDI de pago con complemento 2.0 (P5-04): a qué facturas PPD se aplica y cuánto.
 *
 * Parcialidad, saldo anterior, insoluto e impuestos proporcionales los calcula el backend; aquí
 * sólo se captura el importe pagado a cada factura (texto decimal).
 */

import { useState } from 'react';
import { Stamp } from 'lucide-react';
import type { Catalogos, Factura, PagoCaptura } from '../../services/facturacionApi';
import { pesos } from '../../services/cobranzaApi';

interface Props {
  catalogos: Catalogos;
  pendientes: Factura[];
  ocupado: boolean;
  onEmitir: (p: PagoCaptura) => void;
}

const campo = { padding: '4px 6px', background: 'var(--bg-input)', color: 'var(--text-primary)', border: '1px solid var(--border)', borderRadius: 'var(--radius)' };

export default function FormPago({ catalogos, pendientes, ocupado, onEmitir }: Props) {
  const [fecha, setFecha] = useState(new Date().toISOString().slice(0, 16));
  const [forma, setForma] = useState('03');
  const [operacion, setOperacion] = useState('');
  const [importes, setImportes] = useState<Record<number, string>>({});

  if (pendientes.length === 0) {
    return <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>No hay facturas PPD con saldo.</p>;
  }
  const emitir = () => onEmitir({
    fecha_pago: `${fecha}:00`, forma_pago: forma, num_operacion: operacion.trim(),
    documentos: Object.entries(importes).filter(([, v]) => Number(v) > 0)
      .map(([id, v]) => ({ factura_id: Number(id), importe_pagado: v })),
  });
  return (
    <form aria-label="Nuevo pago" onSubmit={(e) => { e.preventDefault(); emitir(); }}
      style={{ display: 'flex', flexDirection: 'column', gap: 8, fontSize: '0.85rem' }}>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
        <label>Fecha del pago <input style={campo} type="datetime-local" value={fecha} onChange={(e) => setFecha(e.target.value)} /></label>
        <label>Forma{' '}
          <select style={campo} value={forma} onChange={(e) => setForma(e.target.value)}>
            {catalogos.forma_pago.filter((f) => f.clave !== '99').map((f) => <option key={f.clave} value={f.clave}>{f.clave} {f.descripcion}</option>)}
          </select>
        </label>
        <input style={campo} aria-label="Número de operación" placeholder="Núm. de operación (opcional)" value={operacion} onChange={(e) => setOperacion(e.target.value)} />
      </div>
      {pendientes.map((f) => (
        <label key={f.id} style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <span style={{ flex: 1 }}>{f.serie}-{f.folio} · {f.nombre_receptor} · saldo {pesos(f.saldo ?? '0')}</span>
          <input style={{ ...campo, width: 120 }} aria-label={`Importe a ${f.serie}-${f.folio}`} inputMode="decimal" placeholder="0.00"
            value={importes[f.id] ?? ''} onChange={(e) => setImportes({ ...importes, [f.id]: e.target.value })} />
        </label>
      ))}
      <div><button type="submit" className="btn-primary" disabled={ocupado}><Stamp size={14} /> Timbrar pago</button></div>
    </form>
  );
}
