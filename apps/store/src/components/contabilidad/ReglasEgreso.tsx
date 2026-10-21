/**
 * Reglas de asignación de egresos (P2-02): por RFC del proveedor, ClaveProdServ
 * exacta o por prefijo, UsoCFDI o palabra en la descripción → cuenta. Se aplican
 * por prioridad (menor primero) a cada concepto de las facturas recibidas; gana
 * la primera que coincide.
 */

import { useState } from 'react';
import { Plus, Trash2 } from 'lucide-react';
import {
  borrarRegla, crearRegla, editarRegla, type Cuenta, type Regla,
} from '../../services/contabilidadApi';
import ErrorAlert from '../common/ErrorAlert';
import { mensaje } from './comun';
import { labelStyle, tdStyle, thStyle } from '../../utils/styles';

const CRITERIOS: [Regla['criterio'], string][] = [
  ['rfc', 'RFC del proveedor'], ['clave', 'ClaveProdServ'], ['prefijo', 'ClaveProdServ que empieza con'],
  ['uso', 'UsoCFDI'], ['descripcion', 'Palabra en la descripción'],
];
const NOMBRE_CRITERIO = Object.fromEntries(CRITERIOS);

interface Props {
  clave: string;
  reglas: Regla[];
  cuentas: Cuenta[];
  onCambio: () => void;
}

export default function ReglasEgreso({ clave, reglas, cuentas, onCambio }: Props) {
  const [nueva, setNueva] = useState<Omit<Regla, 'id'>>({
    criterio: 'rfc', valor: '', cuenta_numero: '', prioridad: 100, activa: true,
  });
  const [error, setError] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);

  async function correr(fn: () => Promise<unknown>, falla: string) {
    setOcupado(true);
    setError(null);
    try {
      await fn();
      onCambio();
    } catch (e) {
      setError(mensaje(e, falla));
    } finally {
      setOcupado(false);
    }
  }

  return (
    <section className="card" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
      <h3 style={{ fontSize: '1rem', margin: 0 }}>Reglas de asignación de egresos</h3>
      <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--text-muted)' }}>
        Sin regla, un gasto va a la cuenta por default; los UsoCFDI de inversión (I01–I08) y lo que
        pase el tope van a activo fijo, y G01 a compras.
      </p>
      {error && <ErrorAlert message={error} />}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void correr(async () => {
            await crearRegla(clave, nueva);
            setNueva({ ...nueva, valor: '' });
          }, 'No se pudo crear la regla.');
        }}
        style={{ display: 'flex', gap: 'var(--space-sm)', flexWrap: 'wrap', alignItems: 'flex-end' }}
      >
        <label style={{ width: 90 }}>
          <span style={labelStyle}>Prioridad</span>
          <input className="input-field" type="number" min={0} value={nueva.prioridad}
            onChange={(e) => setNueva({ ...nueva, prioridad: Number(e.target.value) })} />
        </label>
        <label>
          <span style={labelStyle}>Criterio</span>
          <select className="input-field" value={nueva.criterio}
            onChange={(e) => setNueva({ ...nueva, criterio: e.target.value as Regla['criterio'] })}>
            {CRITERIOS.map(([v, t]) => <option key={v} value={v}>{t}</option>)}
          </select>
        </label>
        <label style={{ minWidth: 160 }}>
          <span style={labelStyle}>Valor</span>
          <input className="input-field" required value={nueva.valor}
            onChange={(e) => setNueva({ ...nueva, valor: e.target.value })} />
        </label>
        <label style={{ minWidth: 240 }}>
          <span style={labelStyle}>Cuenta</span>
          <select className="input-field" required value={nueva.cuenta_numero}
            onChange={(e) => setNueva({ ...nueva, cuenta_numero: e.target.value })}>
            <option value="">Elige una cuenta</option>
            {cuentas.map((c) => <option key={c.id} value={c.numero}>{c.numero} {c.nombre}</option>)}
          </select>
        </label>
        <button type="submit" className="btn-primary" disabled={ocupado}><Plus size={14} /> Agregar regla</button>
      </form>

      {reglas.length > 0 && (
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.84rem' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border)' }}>
              <th style={thStyle}>Prioridad</th><th style={thStyle}>Criterio</th>
              <th style={thStyle}>Valor</th><th style={thStyle}>Cuenta</th>
              <th style={thStyle}>Activa</th><th style={thStyle} />
            </tr>
          </thead>
          <tbody>
            {reglas.map((r) => (
              <tr key={r.id} style={{ borderBottom: '1px solid var(--border)' }}>
                <td style={tdStyle}>{r.prioridad}</td>
                <td style={tdStyle}>{NOMBRE_CRITERIO[r.criterio] ?? r.criterio}</td>
                <td style={{ ...tdStyle, fontFamily: "'JetBrains Mono', monospace" }}>{r.valor}</td>
                <td style={{ ...tdStyle, fontFamily: "'JetBrains Mono', monospace" }}>{r.cuenta_numero}</td>
                <td style={tdStyle}>
                  <input type="checkbox" aria-label={`Regla ${r.id} activa`} checked={r.activa} disabled={ocupado}
                    onChange={(e) => void correr(() => editarRegla(clave, r.id, { activa: e.target.checked }),
                      'No se pudo cambiar la regla.')} />
                </td>
                <td style={tdStyle}>
                  <button type="button" className="btn-secondary" style={{ padding: '3px 8px' }}
                    aria-label={`Borrar regla ${r.id}`} disabled={ocupado}
                    onClick={() => void correr(() => borrarRegla(clave, r.id), 'No se pudo borrar la regla.')}>
                    <Trash2 size={13} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
