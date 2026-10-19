/**
 * Tab Configuración de Contabilito (P2-02), como la pantalla "Configuración de
 * pólizas automáticas" de Contadigital: reglas de automatización, opciones
 * especiales, concepto de las pólizas, cuentas contables por rol y las reglas
 * de asignación de egresos (`ReglasEgreso`). Lo que se guarda vale para las
 * pólizas NUEVAS: las ya generadas no se tocan.
 */

import { useEffect, useState } from 'react';
import { Loader, Save } from 'lucide-react';
import {
  guardarConfigContable, listarCuentas, obtenerConfigContable,
  type ConfigContable, type Cuenta,
} from '../../services/contabilidadApi';
import ErrorAlert from '../common/ErrorAlert';
import SuccessNotice from '../common/SuccessNotice';
import ReglasEgreso from './ReglasEgreso';
import { mensaje } from './comun';
import { labelStyle } from '../../utils/styles';

type Interruptor = 'automatica_ingresos' | 'automatica_egresos' | 'automatica_pagos' | 'automatica_nomina'
  | 'pue_registra_cobro' | 'uso_s01_no_deducible' | 'efectivo_no_deducible' | 'retenciones_al_pago';

const AUTOMATIZACION: [Interruptor, string][] = [
  ['automatica_ingresos', 'Contabilidad automática de ingresos (facturas y notas emitidas)'],
  ['automatica_egresos', 'Contabilidad automática de egresos (facturas y notas recibidas)'],
  ['automatica_pagos', 'Complementos de pago (cobros, pagos e IVA efectivamente cobrado/pagado)'],
  ['automatica_nomina', 'Nómina (recibos emitidos por el cliente patrón)'],
];

const ESPECIALES: [Interruptor, string][] = [
  ['pue_registra_cobro', 'Facturas PUE: registrar el cobro/pago en la misma póliza'],
  ['uso_s01_no_deducible', 'UsoCFDI S01 (sin efectos fiscales) va a gastos no deducibles'],
  ['efectivo_no_deducible', 'Pagos en efectivo de más de $2,000 van a no deducibles (Art. 27-III LISR)'],
  ['retenciones_al_pago', 'Retenciones de facturas PPD: quedan pendientes y se reconocen al pago (la obligación de retener nace con el pago)'],
];

interface Props {
  clave: string;
}

export default function ConfigPolizas({ clave }: Props) {
  const [config, setConfig] = useState<ConfigContable | null>(null);
  const [cuentas, setCuentas] = useState<Cuenta[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [guardado, setGuardado] = useState(false);
  const [guardando, setGuardando] = useState(false);

  const [recarga, setRecarga] = useState(0);

  useEffect(() => {
    let vivo = true;
    Promise.all([obtenerConfigContable(clave), listarCuentas(clave)])
      .then(([c, l]) => {
        if (!vivo) return;
        setConfig(c.config);
        setCuentas(l.cuentas.filter((x) => x.afectable));
        setError(null);
      })
      .catch((e: unknown) => { if (vivo) setError(mensaje(e, 'No se pudo cargar la configuración.')); });
    return () => { vivo = false; };
  }, [clave, recarga]);

  if (!config) {
    return error ? <ErrorAlert message={error} />
      : <div className="card"><Loader size={16} className="spin" /> Cargando configuración…</div>;
  }

  const cambiar = (parcial: Partial<ConfigContable>) => {
    setGuardado(false);
    setConfig({ ...config, ...parcial });
  };

  async function guardar() {
    if (!config) return;
    setGuardando(true);
    setError(null);
    try {
      const r = await guardarConfigContable(clave, {
        automatica_ingresos: config.automatica_ingresos, automatica_egresos: config.automatica_egresos,
        automatica_pagos: config.automatica_pagos, automatica_nomina: config.automatica_nomina,
        pue_registra_cobro: config.pue_registra_cobro, uso_s01_no_deducible: config.uso_s01_no_deducible,
        efectivo_no_deducible: config.efectivo_no_deducible,
        retenciones_al_pago: config.retenciones_al_pago, tope_activo: config.tope_activo || '0',
        plantilla_concepto: config.plantilla_concepto, cuentas: config.cuentas_personalizadas,
      });
      setConfig(r.config);
      setGuardado(true);
    } catch (e) {
      setError(mensaje(e, 'No se pudo guardar la configuración.'));
    } finally {
      setGuardando(false);
    }
  }

  const casilla = ([campo, texto]: [Interruptor, string]) => (
    <label key={campo} style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: '0.85rem' }}>
      <input type="checkbox" checked={config[campo]} onChange={(e) => cambiar({ [campo]: e.target.checked })} />
      {texto}
    </label>
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
      {error && <ErrorAlert message={error} />}
      <section className="card" style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <h3 style={{ fontSize: '1rem', margin: 0 }}>Reglas de automatización</h3>
        {AUTOMATIZACION.map(casilla)}
      </section>

      <section className="card" style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <h3 style={{ fontSize: '1rem', margin: 0 }}>Opciones especiales</h3>
        {ESPECIALES.map(casilla)}
        <div style={{ display: 'flex', gap: 'var(--space-md)', flexWrap: 'wrap', marginTop: 8 }}>
          <label style={{ minWidth: 220 }}>
            <span style={labelStyle}>Tope para activo fijo (0 = no aplica)</span>
            <input className="input-field" inputMode="decimal" value={config.tope_activo}
              onChange={(e) => cambiar({ tope_activo: e.target.value })} />
          </label>
          <label style={{ flex: 1, minWidth: 280 }}>
            <span style={labelStyle}>Concepto de las pólizas ({'{etiqueta} {folio} {contraparte} {rfc} {uuid}'})</span>
            <input className="input-field" value={config.plantilla_concepto} placeholder="{etiqueta} {folio} {contraparte}"
              onChange={(e) => cambiar({ plantilla_concepto: e.target.value })} />
          </label>
        </div>
      </section>

      <section className="card">
        <h3 style={{ fontSize: '1rem', marginTop: 0 }}>Cuentas contables</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 'var(--space-sm)' }}>
          {config.roles.map((r) => (
            <label key={r.rol}>
              <span style={labelStyle}>{r.descripcion}</span>
              <select className="input-field" value={config.cuentas[r.rol] ?? r.default}
                onChange={(e) => {
                  const personal = { ...config.cuentas_personalizadas };
                  if (e.target.value === r.default) delete personal[r.rol];
                  else personal[r.rol] = e.target.value;
                  cambiar({ cuentas_personalizadas: personal, cuentas: { ...config.cuentas, [r.rol]: e.target.value } });
                }}>
                {!cuentas.some((c) => c.numero === (config.cuentas[r.rol] ?? r.default)) && (
                  <option value={config.cuentas[r.rol] ?? r.default}>{config.cuentas[r.rol] ?? r.default} (no está en el catálogo)</option>
                )}
                {cuentas.map((c) => <option key={c.id} value={c.numero}>{c.numero} {c.nombre}</option>)}
              </select>
            </label>
          ))}
        </div>
      </section>

      <div style={{ display: 'flex', gap: 'var(--space-md)', alignItems: 'center' }}>
        <button type="button" className="btn-primary" disabled={guardando} onClick={() => void guardar()}>
          <Save size={14} /> Guardar configuración
        </button>
        {guardado && <SuccessNotice message="Configuración guardada: aplica a las pólizas nuevas" />}
      </div>

      <ReglasEgreso clave={clave} reglas={config.reglas} cuentas={cuentas} onCambio={() => setRecarga((n) => n + 1)} />
    </div>
  );
}
