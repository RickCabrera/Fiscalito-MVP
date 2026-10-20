/**
 * Saldos iniciales por cuenta afectable (P2-04): con lo que arranca la
 * contabilidad del cliente en el sistema. Entran al saldo inicial de la balanza
 * de cualquier periodo. Una captura que no cuadra se guarda, pero se avisa.
 */

import { useEffect, useState } from 'react';
import { Save } from 'lucide-react';
import {
  guardarSaldosIniciales, listarCuentas, listarSaldosIniciales, type Cuenta,
} from '../../services/contabilidadApi';
import ErrorAlert from '../common/ErrorAlert';
import SuccessNotice from '../common/SuccessNotice';
import { aCentavos, mensaje, sumaCentavos } from './comun';
import { tdStyle, thStyle } from '../../utils/styles';
import { fmtMoney } from '../../utils/format';

interface Props {
  clave: string;
  onGuardado: () => void;
}

type Captura = Record<number, { deudor: string; acreedor: string }>;

export default function SaldosIniciales({ clave, onGuardado }: Props) {
  const [cuentas, setCuentas] = useState<Cuenta[]>([]);
  const [captura, setCaptura] = useState<Captura>({});
  const [error, setError] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([listarCuentas(clave), listarSaldosIniciales(clave)])
      .then(([c, s]) => {
        setCuentas(c.cuentas.filter((x) => x.afectable && ['activo', 'pasivo', 'capital'].includes(x.tipo)));
        setCaptura(Object.fromEntries(s.saldos.map((x) => [x.cuenta_id, { deudor: x.deudor, acreedor: x.acreedor }])));
      })
      .catch((e: unknown) => setError(mensaje(e, 'No se pudieron cargar los saldos iniciales.')));
  }, [clave]);

  const valores = Object.values(captura);
  const deudor = sumaCentavos(valores.map((v) => aCentavos(v.deudor)));
  const acreedor = sumaCentavos(valores.map((v) => aCentavos(v.acreedor)));

  async function guardar() {
    setError(null);
    setAviso(null);
    try {
      const r = await guardarSaldosIniciales(clave, Object.entries(captura).map(([id, v]) => ({
        cuenta_id: Number(id), deudor: aCentavos(v.deudor) || '0.00', acreedor: aCentavos(v.acreedor) || '0.00',
      })));
      setAviso(r.totales.cuadra ? 'Saldos iniciales guardados.' : 'Guardados, pero deudor y acreedor no cuadran.');
      onGuardado();
    } catch (e) {
      setError(mensaje(e, 'No se pudieron guardar los saldos.'));
    }
  }

  const cambiar = (id: number, campo: 'deudor' | 'acreedor', valor: string) =>
    setCaptura({ ...captura, [id]: { ...(captura[id] ?? { deudor: '', acreedor: '' }), [campo]: valor } });

  return (
    <section className="card" aria-label="Saldos iniciales" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
      <strong>Saldos iniciales (cuentas de balance)</strong>
      {error && <ErrorAlert message={error} />}
      {aviso && <SuccessNotice message={aviso} />}
      <div style={{ maxHeight: 360, overflowY: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem' }}>
          <thead><tr><th style={thStyle}>Cuenta</th><th style={thStyle}>Deudor</th><th style={thStyle}>Acreedor</th></tr></thead>
          <tbody>
            {cuentas.map((c) => (
              <tr key={c.id}>
                <td style={tdStyle}><span style={{ fontFamily: "'JetBrains Mono', monospace" }}>{c.numero}</span> {c.nombre}</td>
                <td style={tdStyle}><input className="input-field" inputMode="decimal" aria-label={`Deudor ${c.numero}`}
                  value={captura[c.id]?.deudor ?? ''} onChange={(e) => cambiar(c.id, 'deudor', e.target.value)} /></td>
                <td style={tdStyle}><input className="input-field" inputMode="decimal" aria-label={`Acreedor ${c.numero}`}
                  value={captura[c.id]?.acreedor ?? ''} onChange={(e) => cambiar(c.id, 'acreedor', e.target.value)} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div style={{ display: 'flex', gap: 'var(--space-md)', alignItems: 'center' }}>
        <span style={{ fontSize: '0.85rem', color: deudor === acreedor ? 'var(--success)' : 'var(--warning)' }}>
          Deudor {fmtMoney(deudor / 100)} · Acreedor {fmtMoney(acreedor / 100)}
        </span>
        <span style={{ flex: 1 }} />
        <button type="button" className="btn-primary" onClick={() => void guardar()}><Save size={14} /> Guardar saldos</button>
      </div>
    </section>
  );
}
