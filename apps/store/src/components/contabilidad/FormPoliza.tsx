/**
 * Captura de póliza manual (P2-03). Sólo cuentas afectables; cada renglón lleva
 * cargo O abono. La diferencia se enseña mientras se captura (en centavos
 * enteros, sin ruido de flotantes) y el botón no se habilita hasta que cuadra;
 * el backend vuelve a validar todo.
 */

import { useEffect, useMemo, useState } from 'react';
import { Plus, Trash2 } from 'lucide-react';
import {
  crearPoliza, listarCuentas, type Cuenta, type Poliza, type TipoPoliza,
} from '../../services/contabilidadApi';
import ErrorAlert from '../common/ErrorAlert';
import { aCentavos, mensaje, sumaCentavos } from './comun';
import { labelStyle, tdStyle, thStyle } from '../../utils/styles';
import { fmtMoney } from '../../utils/format';

interface Renglon {
  cuenta_id: string;
  concepto: string;
  cargo: string;
  abono: string;
}

const VACIO: Renglon = { cuenta_id: '', concepto: '', cargo: '', abono: '' };

interface Props {
  clave: string;
  onListo: (p: Poliza) => void;
  onCancelar: () => void;
}

export default function FormPoliza({ clave, onListo, onCancelar }: Props) {
  const [cuentas, setCuentas] = useState<Cuenta[]>([]);
  const [tipo, setTipo] = useState<TipoPoliza>('diario');
  const [fecha, setFecha] = useState(new Date().toISOString().slice(0, 10));
  const [concepto, setConcepto] = useState('');
  const [renglones, setRenglones] = useState<Renglon[]>([{ ...VACIO }, { ...VACIO }]);
  const [error, setError] = useState<string | null>(null);
  const [guardando, setGuardando] = useState(false);

  useEffect(() => {
    listarCuentas(clave)
      .then((r) => setCuentas(r.cuentas.filter((c) => c.afectable)))
      .catch((e: unknown) => setError(mensaje(e, 'No se pudo cargar el catálogo.')));
  }, [clave]);

  const cargos = useMemo(() => sumaCentavos(renglones.map((r) => aCentavos(r.cargo))), [renglones]);
  const abonos = useMemo(() => sumaCentavos(renglones.map((r) => aCentavos(r.abono))), [renglones]);
  const completos = renglones.every((r) => r.cuenta_id && (aCentavos(r.cargo) !== '') !== (aCentavos(r.abono) !== ''));
  const cuadra = cargos === abonos && cargos > 0;

  const cambiar = (i: number, p: Partial<Renglon>) =>
    setRenglones(renglones.map((r, j) => (j === i ? { ...r, ...p } : r)));

  async function guardar(e: React.FormEvent) {
    e.preventDefault();
    setGuardando(true);
    setError(null);
    try {
      const r = await crearPoliza(clave, {
        tipo, fecha, concepto,
        movimientos: renglones.map((x) => ({
          cuenta_id: Number(x.cuenta_id), concepto: x.concepto,
          cargo: aCentavos(x.cargo) || '0.00', abono: aCentavos(x.abono) || '0.00', uuid: '', rfc: '',
        })),
      });
      onListo(r.poliza);
    } catch (err) {
      setError(mensaje(err, 'No se pudo guardar la póliza.'));
    } finally {
      setGuardando(false);
    }
  }

  return (
    <form className="card" onSubmit={guardar} aria-label="Nueva póliza manual" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
      <strong>Nueva póliza manual</strong>
      {error && <ErrorAlert message={error} />}
      <div style={{ display: 'flex', gap: 'var(--space-md)', flexWrap: 'wrap', alignItems: 'flex-end' }}>
        <label><span style={labelStyle}>Tipo</span>
          <select className="input-field" value={tipo} onChange={(e) => setTipo(e.target.value as TipoPoliza)}>
            <option value="diario">Diario</option><option value="ingreso">Ingreso</option><option value="egreso">Egreso</option>
          </select></label>
        <label><span style={labelStyle}>Fecha</span>
          <input className="input-field" type="date" required value={fecha} onChange={(e) => setFecha(e.target.value)} /></label>
        <label style={{ flex: 1, minWidth: 240 }}><span style={labelStyle}>Concepto</span>
          <input className="input-field" value={concepto} onChange={(e) => setConcepto(e.target.value)} /></label>
      </div>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.84rem' }}>
          <thead>
            <tr><th style={thStyle}>Cuenta</th><th style={thStyle}>Concepto</th>
              <th style={thStyle}>Cargo</th><th style={thStyle}>Abono</th><th style={thStyle} /></tr>
          </thead>
          <tbody>
            {renglones.map((r, i) => (
              <tr key={i}>
                <td style={tdStyle}>
                  <select className="input-field" aria-label={`Cuenta del renglón ${i + 1}`} required value={r.cuenta_id}
                    onChange={(e) => cambiar(i, { cuenta_id: e.target.value })}>
                    <option value="">Elige una cuenta</option>
                    {cuentas.map((c) => <option key={c.id} value={c.id}>{c.numero} {c.nombre}</option>)}
                  </select>
                </td>
                <td style={tdStyle}><input className="input-field" value={r.concepto} onChange={(e) => cambiar(i, { concepto: e.target.value })} /></td>
                <td style={tdStyle}><input className="input-field" inputMode="decimal" aria-label={`Cargo del renglón ${i + 1}`} value={r.cargo}
                  onChange={(e) => cambiar(i, { cargo: e.target.value, abono: e.target.value ? '' : r.abono })} /></td>
                <td style={tdStyle}><input className="input-field" inputMode="decimal" aria-label={`Abono del renglón ${i + 1}`} value={r.abono}
                  onChange={(e) => cambiar(i, { abono: e.target.value, cargo: e.target.value ? '' : r.cargo })} /></td>
                <td style={tdStyle}>
                  <button type="button" className="btn-secondary" style={{ padding: '3px 8px' }} aria-label={`Quitar renglón ${i + 1}`}
                    disabled={renglones.length <= 2} onClick={() => setRenglones(renglones.filter((_x, j) => j !== i))}>
                    <Trash2 size={13} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div style={{ display: 'flex', gap: 'var(--space-md)', flexWrap: 'wrap', alignItems: 'center' }}>
        <button type="button" className="btn-secondary" onClick={() => setRenglones([...renglones, { ...VACIO }])}>
          <Plus size={14} /> Renglón
        </button>
        <span style={{ fontSize: '0.85rem', color: cuadra ? 'var(--success)' : 'var(--warning)' }}>
          Cargos {fmtMoney(cargos / 100)} · Abonos {fmtMoney(abonos / 100)}
          {cuadra ? ' · cuadra' : ` · diferencia ${fmtMoney((cargos - abonos) / 100)}`}
        </span>
        <span style={{ flex: 1 }} />
        <button type="submit" className="btn-primary" disabled={guardando || !cuadra || !completos}>Guardar póliza</button>
        <button type="button" className="btn-secondary" onClick={onCancelar}>Cancelar</button>
      </div>
    </form>
  );
}
