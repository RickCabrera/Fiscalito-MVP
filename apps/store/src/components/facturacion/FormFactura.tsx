/**
 * Captura de un CFDI de ingreso o egreso (P5-04).
 *
 * Sólo CAPTURA: cantidad, valor unitario y qué impuestos lleva cada concepto (presets del
 * catálogo del backend). Subtotal, impuestos y total los calcula el motor del backend y se ven
 * en la factura emitida; aquí no se suma nada.
 */

import { useState } from 'react';
import { Plus, Stamp, Trash2 } from 'lucide-react';
import type {
  Catalogos, ConceptoCaptura, FacturaCaptura, ImpuestoCaptura,
} from '../../services/facturacionApi';

interface Props {
  catalogos: Catalogos;
  /** Otros clientes del despacho que pueden ser receptores. */
  receptores: { id: string; nombre: string }[];
  ocupado: boolean;
  onEmitir: (f: FacturaCaptura) => void;
}

interface Fila {
  descripcion: string;
  clave_prod_serv: string;
  clave_unidad: string;
  cantidad: string;
  valor_unitario: string;
  traslado: string;
  retenciones: string[];
}

const NUEVA: Fila = {
  descripcion: '', clave_prod_serv: '84111500', clave_unidad: 'E48', cantidad: '1',
  valor_unitario: '', traslado: 'iva16', retenciones: [],
};
const campo = { padding: '4px 6px', background: 'var(--bg-input)', color: 'var(--text-primary)', border: '1px solid var(--border)', borderRadius: 'var(--radius)' };

function impuestosDe(f: Fila, cat: Catalogos): ImpuestoCaptura[] {
  const salida: ImpuestoCaptura[] = [];
  const t = cat.presets.traslados.find((p) => p.clave === f.traslado);
  if (t) salida.push({ tipo: 'traslado', impuesto: t.impuesto, tipo_factor: t.tipo_factor ?? 'Tasa', tasa: t.tasa });
  for (const clave of f.retenciones) {
    const r = cat.presets.retenciones.find((p) => p.clave === clave);
    if (r) salida.push({ tipo: 'retencion', impuesto: r.impuesto, tipo_factor: 'Tasa', tasa: r.tasa });
  }
  return salida;
}

export default function FormFactura({ catalogos, receptores, ocupado, onEmitir }: Props) {
  const [tipo, setTipo] = useState<'I' | 'E'>('I');
  const [receptor, setReceptor] = useState(receptores[0]?.id ?? '');
  const [manual, setManual] = useState({ rfc: '', nombre: '', regimen: '601', codigo_postal: '' });
  const [uso, setUso] = useState('G03');
  const [metodo, setMetodo] = useState<'PUE' | 'PPD'>('PUE');
  const [forma, setForma] = useState('03');
  const [relTipo, setRelTipo] = useState('01');
  const [relUuid, setRelUuid] = useState('');
  const [filas, setFilas] = useState<Fila[]>([{ ...NUEVA }]);

  const cambiar = (i: number, parcial: Partial<Fila>) =>
    setFilas((fs) => fs.map((f, j) => (j === i ? { ...f, ...parcial } : f)));

  const emitir = () => {
    const conceptos: ConceptoCaptura[] = filas.map((f) => {
      const impuestos = impuestosDe(f, catalogos);
      return {
        clave_prod_serv: f.clave_prod_serv, cantidad: f.cantidad, clave_unidad: f.clave_unidad,
        descripcion: f.descripcion, valor_unitario: f.valor_unitario,
        objeto_imp: impuestos.length ? '02' : '01', impuestos,
      };
    });
    onEmitir({
      tipo,
      receptor: receptor ? { clave_cliente: receptor, uso_cfdi: uso } : { ...manual, uso_cfdi: uso },
      conceptos, metodo_pago: metodo, forma_pago: metodo === 'PPD' ? '99' : forma,
      relacionados: relUuid.trim() ? [{ tipo_relacion: relTipo, uuids: [relUuid.trim()] }] : [],
    });
  };

  return (
    <form aria-label="Nueva factura" onSubmit={(e) => { e.preventDefault(); emitir(); }}
      style={{ display: 'flex', flexDirection: 'column', gap: 10, fontSize: '0.85rem' }}>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
        <label>Tipo{' '}
          <select style={campo} value={tipo} onChange={(e) => { const v = e.target.value as 'I' | 'E'; setTipo(v); if (v === 'E') setMetodo('PUE'); }}>
            <option value="I">Ingreso</option><option value="E">Egreso (nota de crédito)</option>
          </select>
        </label>
        <label>Receptor{' '}
          <select style={campo} aria-label="Receptor" value={receptor} onChange={(e) => setReceptor(e.target.value)}>
            {receptores.map((r) => <option key={r.id} value={r.id}>{r.nombre}</option>)}
            <option value="">Otro (capturar)</option>
          </select>
        </label>
        <label>Uso CFDI{' '}
          <select style={campo} value={uso} onChange={(e) => setUso(e.target.value)}>
            {catalogos.uso_cfdi.filter((u) => u.clave !== 'CP01').map((u) => <option key={u.clave} value={u.clave}>{u.clave} {u.descripcion}</option>)}
          </select>
        </label>
      </div>
      {!receptor && (
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <input style={campo} aria-label="RFC del receptor" placeholder="RFC" value={manual.rfc} onChange={(e) => setManual({ ...manual, rfc: e.target.value.toUpperCase() })} />
          <input style={campo} aria-label="Nombre del receptor" placeholder="Nombre o razón social" value={manual.nombre} onChange={(e) => setManual({ ...manual, nombre: e.target.value })} />
          <select style={campo} aria-label="Régimen del receptor" value={manual.regimen} onChange={(e) => setManual({ ...manual, regimen: e.target.value })}>
            {catalogos.regimen_fiscal.map((r) => <option key={r.clave} value={r.clave}>{r.clave} {r.descripcion}</option>)}
          </select>
          <input style={campo} aria-label="CP del receptor" placeholder="CP" value={manual.codigo_postal} onChange={(e) => setManual({ ...manual, codigo_postal: e.target.value })} />
        </div>
      )}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
        <label>Método{' '}
          <select style={campo} value={metodo} disabled={tipo === 'E'} onChange={(e) => setMetodo(e.target.value as 'PUE' | 'PPD')}>
            {catalogos.metodo_pago.map((m) => <option key={m.clave} value={m.clave}>{m.clave} {m.descripcion}</option>)}
          </select>
        </label>
        <label>Forma{' '}
          <select style={campo} value={metodo === 'PPD' ? '99' : forma} disabled={metodo === 'PPD'} onChange={(e) => setForma(e.target.value)}>
            {catalogos.forma_pago.map((f) => <option key={f.clave} value={f.clave}>{f.clave} {f.descripcion}</option>)}
          </select>
        </label>
        <label>Relacionar{' '}
          <select style={campo} aria-label="Tipo de relación" value={relTipo} onChange={(e) => setRelTipo(e.target.value)}>
            {catalogos.tipo_relacion.map((t) => <option key={t.clave} value={t.clave}>{t.clave} {t.descripcion}</option>)}
          </select>
        </label>
        <input style={{ ...campo, minWidth: 280 }} aria-label="UUID relacionado" placeholder={tipo === 'E' ? 'UUID de la factura que acredita' : 'UUID relacionado (opcional)'} value={relUuid} onChange={(e) => setRelUuid(e.target.value)} />
      </div>
      {filas.map((f, i) => (
        <fieldset key={i} style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius)', padding: 8, display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
          <legend>Concepto {i + 1}</legend>
          <input style={{ ...campo, minWidth: 220 }} aria-label={`Descripción ${i + 1}`} placeholder="Descripción" value={f.descripcion} onChange={(e) => cambiar(i, { descripcion: e.target.value })} required />
          <input style={{ ...campo, width: 90 }} aria-label={`Clave SAT ${i + 1}`} list="claves-prod-serv" value={f.clave_prod_serv} onChange={(e) => cambiar(i, { clave_prod_serv: e.target.value })} />
          <select style={campo} aria-label={`Unidad ${i + 1}`} value={f.clave_unidad} onChange={(e) => cambiar(i, { clave_unidad: e.target.value })}>
            {catalogos.clave_unidad.map((u) => <option key={u.clave} value={u.clave}>{u.clave} {u.descripcion}</option>)}
          </select>
          <input style={{ ...campo, width: 60 }} aria-label={`Cantidad ${i + 1}`} inputMode="decimal" value={f.cantidad} onChange={(e) => cambiar(i, { cantidad: e.target.value })} />
          <input style={{ ...campo, width: 110 }} aria-label={`Valor unitario ${i + 1}`} inputMode="decimal" placeholder="Valor unitario" value={f.valor_unitario} onChange={(e) => cambiar(i, { valor_unitario: e.target.value })} required />
          <select style={campo} aria-label={`IVA ${i + 1}`} value={f.traslado} onChange={(e) => cambiar(i, { traslado: e.target.value })}>
            {catalogos.presets.traslados.map((p) => <option key={p.clave} value={p.clave}>{p.nombre}</option>)}
            <option value="">No objeto de impuesto</option>
          </select>
          {catalogos.presets.retenciones.map((p) => (
            <label key={p.clave} style={{ display: 'inline-flex', gap: 4, alignItems: 'center' }}>
              <input type="checkbox" checked={f.retenciones.includes(p.clave)} onChange={(e) => cambiar(i, {
                retenciones: e.target.checked ? [...f.retenciones, p.clave] : f.retenciones.filter((c) => c !== p.clave) })} />
              {p.nombre}
            </label>
          ))}
          {filas.length > 1 && (
            <button type="button" className="btn-secondary" aria-label={`Quitar concepto ${i + 1}`} onClick={() => setFilas(filas.filter((_, j) => j !== i))}><Trash2 size={12} /></button>
          )}
        </fieldset>
      ))}
      <datalist id="claves-prod-serv">
        {catalogos.clave_prod_serv.map((c) => <option key={c.clave} value={c.clave}>{c.descripcion}</option>)}
      </datalist>
      <div style={{ display: 'flex', gap: 8 }}>
        <button type="button" className="btn-secondary" onClick={() => setFilas([...filas, { ...NUEVA }])}><Plus size={14} /> Concepto</button>
        <button type="submit" className="btn-primary" disabled={ocupado}><Stamp size={14} /> Timbrar</button>
      </div>
    </form>
  );
}
