/**
 * Alta de cuenta bancaria del cliente (P2-06): banco (c_Banco del SAT), número,
 * CLABE y la cuenta contable afectable a la que se liga. La ventana de fechas y
 * el umbral del emparejamiento son criterio del despacho (defaults 3 días / 60).
 */

import { useEffect, useState } from 'react';
import { Loader, Save } from 'lucide-react';
import { listarCuentas, type Cuenta } from '../../services/contabilidadApi';
import { crearCuentaBancaria, listarBancos, type CuentaBancaria } from '../../services/conciliacionApi';
import ErrorAlert from '../common/ErrorAlert';
import { mensaje } from './comun';
import { labelStyle } from '../../utils/styles';

interface Props {
  clave: string;
  onCreada: (c: CuentaBancaria) => void;
  onCancelar: () => void;
}

export default function FormCuentaBancaria({ clave, onCreada, onCancelar }: Props) {
  const [bancos, setBancos] = useState<{ clave: string; nombre: string }[]>([]);
  const [cuentas, setCuentas] = useState<Cuenta[]>([]);
  const [f, setF] = useState({ banco: '012', nombre: '', numero: '', clabe: '', cuenta_contable_id: 0, ventana_dias: 3, umbral: 60 });
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let vivo = true;
    Promise.all([listarBancos(), listarCuentas(clave)])
      .then(([b, c]) => {
        if (!vivo) return;
        setBancos(b.bancos);
        const afectables = c.cuentas.filter((x) => x.afectable && x.codigo_agrupador.startsWith('102'));
        setCuentas(afectables);
        if (afectables[0]) setF((p) => ({ ...p, cuenta_contable_id: afectables[0].id }));
      })
      .catch((e: unknown) => { if (vivo) setError(mensaje(e, 'No se pudieron cargar bancos y cuentas.')); });
    return () => { vivo = false; };
  }, [clave]);

  const guardar = async (e: React.FormEvent) => {
    e.preventDefault();
    setGuardando(true); setError(null);
    try { onCreada((await crearCuentaBancaria(clave, f)).cuenta); }
    catch (err) { setError(mensaje(err, 'No se pudo guardar la cuenta bancaria.')); }
    finally { setGuardando(false); }
  };

  return (
    <form className="card" onSubmit={guardar} style={{ display: 'flex', gap: 'var(--space-md)', flexWrap: 'wrap', alignItems: 'flex-end' }}>
      <label><span style={labelStyle}>Banco</span>
        <select className="input-field" value={f.banco} onChange={(e) => setF({ ...f, banco: e.target.value })}>
          {bancos.map((b) => <option key={b.clave} value={b.clave}>{b.nombre}</option>)}
        </select></label>
      <label><span style={labelStyle}>Nombre</span>
        <input className="input-field" value={f.nombre} onChange={(e) => setF({ ...f, nombre: e.target.value })} /></label>
      <label><span style={labelStyle}>Número de cuenta</span>
        <input className="input-field" value={f.numero} onChange={(e) => setF({ ...f, numero: e.target.value })} /></label>
      <label><span style={labelStyle}>CLABE</span>
        <input className="input-field" value={f.clabe} maxLength={18} inputMode="numeric"
          onChange={(e) => setF({ ...f, clabe: e.target.value.replace(/\D/g, '') })} /></label>
      <label><span style={labelStyle}>Cuenta contable</span>
        <select className="input-field" aria-label="Cuenta contable" value={f.cuenta_contable_id}
          onChange={(e) => setF({ ...f, cuenta_contable_id: Number(e.target.value) })}>
          {cuentas.map((c) => <option key={c.id} value={c.id}>{c.numero} · {c.nombre}</option>)}
        </select></label>
      <label><span style={labelStyle}>Ventana (días)</span>
        <input className="input-field" type="number" min={0} max={31} value={f.ventana_dias} style={{ width: 80 }}
          onChange={(e) => setF({ ...f, ventana_dias: Number(e.target.value) })} /></label>
      <label><span style={labelStyle}>Umbral</span>
        <input className="input-field" type="number" min={50} max={100} value={f.umbral} style={{ width: 80 }}
          onChange={(e) => setF({ ...f, umbral: Number(e.target.value) })} /></label>
      <button type="submit" className="btn-primary" disabled={guardando || !f.cuenta_contable_id}>
        {guardando ? <Loader size={14} className="spin" /> : <Save size={14} />} Guardar
      </button>
      <button type="button" className="btn-secondary" onClick={onCancelar}>Cancelar</button>
      {error && <div style={{ flexBasis: '100%' }}><ErrorAlert message={error} /></div>}
    </form>
  );
}
