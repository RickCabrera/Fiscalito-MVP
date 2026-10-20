/**
 * Crear la póliza de un movimiento del banco sin CFDI (comisiones, intereses) y
 * conciliarla en el mismo paso (P2-06). El backend sugiere la cuenta de la
 * contrapartida; el contador puede cambiarla y partir el importe (p. ej.
 * comisión + IVA). La suma la valida el backend.
 */

import { useEffect, useState } from 'react';
import { Loader, Save } from 'lucide-react';
import { listarCuentas, type Cuenta } from '../../services/contabilidadApi';
import { polizaDesdeBanco, sugerirCuenta, type MovBanco } from '../../services/conciliacionApi';
import ErrorAlert from '../common/ErrorAlert';
import { aCentavos, mensaje } from './comun';
import { labelStyle } from '../../utils/styles';

interface Props {
  clave: string;
  cuentaBancariaId: number;
  movimiento: MovBanco;
  onCreada: () => void;
  onCerrar: () => void;
}

interface Renglon { cuenta_id: number; importe: string }

export default function PolizaDesdeBanco({ clave, cuentaBancariaId, movimiento, onCreada, onCerrar }: Props) {
  const total = Number(movimiento.abono) > 0 ? movimiento.abono : movimiento.cargo;
  const [cuentas, setCuentas] = useState<Cuenta[]>([]);
  const [renglones, setRenglones] = useState<Renglon[]>([{ cuenta_id: 0, importe: total }]);
  const [concepto, setConcepto] = useState(movimiento.concepto);
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let vivo = true;
    Promise.all([listarCuentas(clave), sugerirCuenta(clave, cuentaBancariaId, movimiento.id)])
      .then(([c, s]) => {
        if (!vivo) return;
        setCuentas(c.cuentas.filter((x) => x.afectable));
        if (s.sugerida) setRenglones([{ cuenta_id: s.sugerida.cuenta_id, importe: total }]);
      })
      .catch((e: unknown) => { if (vivo) setError(mensaje(e, 'No se pudieron cargar las cuentas.')); });
    return () => { vivo = false; };
  }, [clave, cuentaBancariaId, movimiento.id, total]);

  const cambiar = (i: number, r: Partial<Renglon>) =>
    setRenglones(renglones.map((x, j) => (j === i ? { ...x, ...r } : x)));

  const guardar = async () => {
    setOcupado(true); setError(null);
    try {
      await polizaDesdeBanco(clave, cuentaBancariaId, movimiento.id,
        renglones.map((r) => ({ cuenta_id: r.cuenta_id, importe: aCentavos(r.importe) })), concepto);
      onCreada();
    } catch (e) {
      setError(mensaje(e, 'No se pudo crear la póliza.'));
    } finally {
      setOcupado(false);
    }
  };

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{ fontWeight: 600, fontSize: '0.9rem' }}>
        Póliza de {Number(movimiento.abono) > 0 ? 'ingreso' : 'egreso'} · {movimiento.fecha} · {total}
      </div>
      <label><span style={labelStyle}>Concepto</span>
        <input className="input-field" value={concepto} onChange={(e) => setConcepto(e.target.value)} style={{ width: '100%' }} /></label>
      {renglones.map((r, i) => (
        <div key={i} style={{ display: 'flex', gap: 'var(--space-sm)', alignItems: 'flex-end' }}>
          <label style={{ flex: 1 }}><span style={labelStyle}>Contrapartida</span>
            <select className="input-field" aria-label="Contrapartida" value={r.cuenta_id} style={{ width: '100%' }}
              onChange={(e) => cambiar(i, { cuenta_id: Number(e.target.value) })}>
              <option value={0}>Elige una cuenta…</option>
              {cuentas.map((c) => <option key={c.id} value={c.id}>{c.numero} · {c.nombre}</option>)}
            </select></label>
          <label><span style={labelStyle}>Importe</span>
            <input className="input-field" style={{ width: 120 }} value={r.importe} onChange={(e) => cambiar(i, { importe: e.target.value })} /></label>
        </div>
      ))}
      <div style={{ display: 'flex', gap: 8 }}>
        <button type="button" className="btn-secondary" onClick={() => setRenglones([...renglones, { cuenta_id: 0, importe: '' }])}>
          Partir importe
        </button>
        <span style={{ flex: 1 }} />
        <button type="button" className="btn-secondary" onClick={onCerrar}>Cancelar</button>
        <button type="button" className="btn-primary" onClick={guardar}
          disabled={ocupado || renglones.some((r) => !r.cuenta_id || !aCentavos(r.importe))}>
          {ocupado ? <Loader size={14} className="spin" /> : <Save size={14} />} Crear y conciliar
        </button>
      </div>
      {error && <ErrorAlert message={error} />}
    </div>
  );
}
