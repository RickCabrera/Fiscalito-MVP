/**
 * Tab Conciliación de Contabilito (P2-06), como la "Conciliación bancaria" de
 * Contadigital: se elige la cuenta bancaria y el periodo, se sube el estado de
 * cuenta (plantilla CSV/XLSX, OFX o PDF), y se ven lado a lado los movimientos
 * de libros (pólizas y CFDI que mueven bancos) y los del banco, con su marca.
 * "Conciliar" empareja en el backend; la conciliación manual concilia lo
 * seleccionado de los dos lados; "Deshacer" lo regresa a pendiente; un
 * movimiento del banco sin CFDI genera su póliza. Ningún cuadre se decide aquí.
 */

import { useCallback, useEffect, useState } from 'react';
import { Link2, Loader, Plus, Wand2 } from 'lucide-react';
import {
  conciliarAutomatico, conciliarManual, deshacerConciliacion, listarCuentasBancarias, obtenerVista,
  type CuentaBancaria, type MovBanco, type VistaConciliacion,
} from '../../services/conciliacionApi';
import ErrorAlert from '../common/ErrorAlert';
import FormCuentaBancaria from './FormCuentaBancaria';
import ImportarEstado from './ImportarEstado';
import PolizaDesdeBanco from './PolizaDesdeBanco';
import ReporteConciliacion from './ReporteConciliacion';
import TablaConciliacion, { type FilaConciliacion } from './TablaConciliacion';
import { mensaje, mesDe, sumaCentavos } from './comun';
import { labelStyle } from '../../utils/styles';

interface Props { clave: string }

export default function ConciliacionBancaria({ clave }: Props) {
  const [cuentas, setCuentas] = useState<CuentaBancaria[] | null>(null);
  const [cuentaId, setCuentaId] = useState<number | null>(null);
  const [alta, setAlta] = useState(false);
  const [periodo, setPeriodo] = useState(mesDe());
  const [vista, setVista] = useState<VistaConciliacion | null>(null);
  const [sel, setSel] = useState<Set<string>>(new Set());
  const [ocupado, setOcupado] = useState(false);
  const [aviso, setAviso] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [polizaDe, setPolizaDe] = useState<MovBanco | null>(null);
  const [verReporte, setVerReporte] = useState(false);

  useEffect(() => {
    let vivo = true;
    listarCuentasBancarias(clave)
      .then((r) => { if (vivo) { setCuentas(r.cuentas); setCuentaId(r.cuentas[0]?.id ?? null); } })
      .catch((e: unknown) => { if (vivo) setError(mensaje(e, 'No se pudieron cargar las cuentas bancarias.')); });
    return () => { vivo = false; };
  }, [clave]);

  const [version, setVersion] = useState(0);
  const recargar = useCallback(() => setVersion((n) => n + 1), []);

  useEffect(() => {
    if (!cuentaId) return;
    let vivo = true;
    obtenerVista(clave, cuentaId, periodo.desde, periodo.hasta)
      .then((v) => { if (vivo) { setVista(v); setSel(new Set()); setError(null); } })
      .catch((e: unknown) => { if (vivo) setError(mensaje(e, 'No se pudieron cargar los movimientos.')); });
    return () => { vivo = false; };
  }, [clave, cuentaId, periodo, version]);

  const accion = async (fn: () => Promise<string | null>) => {
    setOcupado(true); setError(null); setAviso(null);
    try { setAviso(await fn()); recargar(); }
    catch (e) { setError(mensaje(e, 'No se pudo completar la acción.')); }
    finally { setOcupado(false); }
  };

  const conciliar = () => accion(async () => {
    const r = (await conciliarAutomatico(clave, cuentaId as number, periodo.desde, periodo.hasta)).resultado;
    return `${r.conciliados} conciliaciones (${r.uno_a_varios} de uno a varios). Pendientes: ${r.pendientes_banco} del banco, ${r.pendientes_libros} de libros.`
      + (r.ambiguos.length ? ` ${r.ambiguos.length} con candidatos empatados: concílialos a mano.` : '');
  });

  const selBanco = [...sel].filter((k) => k.startsWith('b:'));
  const selLibros = [...sel].filter((k) => !k.startsWith('b:'));
  const signo = (cargo: string, abono: string) => [abono, `-${cargo}`];
  const sumaBanco = sumaCentavos((vista?.banco ?? []).filter((m) => sel.has(m.clave)).flatMap((m) => signo(m.cargo, m.abono)));
  const sumaLibros = sumaCentavos((vista?.libros ?? []).filter((m) => sel.has(m.clave)).flatMap((m) => signo(m.abono, m.cargo)));

  const manual = () => accion(async () => {
    await conciliarManual(clave, cuentaId as number, selBanco, selLibros);
    return 'Conciliación manual guardada.';
  });

  const alternar = (k: string) => {
    const n = new Set(sel);
    if (n.has(k)) n.delete(k); else n.add(k);
    setSel(n);
  };
  const deshacer = (id: number) => accion(async () => { await deshacerConciliacion(clave, cuentaId as number, id); return 'Conciliación deshecha.'; });

  if (cuentas === null) return error ? <ErrorAlert message={error} /> : <Loader size={16} className="spin" />;

  const filasLibros: FilaConciliacion[] = (vista?.libros ?? []).map((m) => ({
    clave: m.clave, fecha: m.fecha, concepto: m.concepto, cargo: m.cargo, abono: m.abono,
    detalle: `${m.origen === 'cfdi' ? 'CFDI sin póliza' : 'Póliza'} ${m.folio}${m.uuid ? ` · ${m.uuid.slice(0, 8)}` : ''}`,
    conciliacion_id: m.conciliacion_id,
  }));
  const filasBanco: FilaConciliacion[] = (vista?.banco ?? []).map((m) => ({
    clave: m.clave, fecha: m.fecha, concepto: m.concepto, cargo: m.cargo, abono: m.abono,
    detalle: m.referencia ? `Ref. ${m.referencia}` : '', conciliacion_id: m.conciliacion_id,
  }));
  const cuenta = cuentas.find((c) => c.id === cuentaId) ?? null;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
      <div className="card" style={{ display: 'flex', gap: 'var(--space-md)', flexWrap: 'wrap', alignItems: 'flex-end' }}>
        <label><span style={labelStyle}>Cuenta bancaria</span>
          <select className="input-field" aria-label="Cuenta bancaria" value={cuentaId ?? ''} onChange={(e) => setCuentaId(Number(e.target.value) || null)}>
            {cuentas.length === 0 && <option value="">Sin cuentas</option>}
            {cuentas.map((c) => <option key={c.id} value={c.id}>{c.nombre || c.banco} {c.numero} · {c.cuenta_contable}</option>)}
          </select></label>
        <button type="button" className="btn-secondary" onClick={() => setAlta(true)}><Plus size={14} /> Cuenta</button>
        <label><span style={labelStyle}>Mes</span>
          <input className="input-field" type="month" value={periodo.desde.slice(0, 7)}
            onChange={(e) => e.target.value && setPeriodo(mesDe(`${e.target.value}-01`))} /></label>
        <span style={{ flex: 1 }} />
        <button type="button" className="btn-primary" onClick={conciliar} disabled={!cuentaId || ocupado}>
          {ocupado ? <Loader size={14} className="spin" /> : <Wand2 size={14} />} Conciliar
        </button>
        <button type="button" className="btn-secondary" onClick={manual}
          disabled={ocupado || !selBanco.length || !selLibros.length || sumaBanco !== sumaLibros}
          title="Selecciona movimientos de los dos lados que sumen lo mismo">
          <Link2 size={14} /> Conciliar selección
        </button>
        <button type="button" className="btn-secondary" disabled={!cuentaId} onClick={() => setVerReporte(!verReporte)}>
          {verReporte ? 'Ocultar reporte' : 'Reporte'}
        </button>
      </div>

      {alta && (
        <FormCuentaBancaria clave={clave} onCancelar={() => setAlta(false)}
          onCreada={(c) => { setCuentas([...cuentas, c]); setCuentaId(c.id); setAlta(false); }} />
      )}
      {cuentas.length === 0 && !alta && (
        <div className="card" style={{ color: 'var(--text-secondary)' }}>
          Da de alta la cuenta bancaria del cliente y lígala a su cuenta contable de bancos para conciliar.
        </div>
      )}
      {cuenta && <ImportarEstado clave={clave} cuenta={cuenta} onImportado={recargar} />}
      {error && <ErrorAlert message={error} />}
      {aviso && <div role="status" style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>{aviso}</div>}
      {sel.size > 0 && (
        <div style={{ fontSize: '0.8rem', color: sumaBanco === sumaLibros ? 'var(--success)' : 'var(--warning)' }}>
          Selección: banco {(sumaBanco / 100).toFixed(2)} · libros {(sumaLibros / 100).toFixed(2)}
        </div>
      )}
      {verReporte && cuentaId && <ReporteConciliacion clave={clave} cuentaId={cuentaId} corte={periodo.hasta} />}
      {polizaDe && cuentaId && (
        <PolizaDesdeBanco clave={clave} cuentaBancariaId={cuentaId} movimiento={polizaDe}
          onCerrar={() => setPolizaDe(null)}
          onCreada={() => { setPolizaDe(null); setAviso('Póliza creada y conciliada.'); recargar(); }} />
      )}

      {vista && (
        <div style={{ display: 'flex', gap: 'var(--space-md)', flexWrap: 'wrap', alignItems: 'flex-start' }}>
          <TablaConciliacion titulo="Movimientos de pólizas" filas={filasLibros} seleccion={sel}
            onAlternar={alternar} onDeshacer={deshacer} etiquetas={['Cargo', 'Abono']} />
          <TablaConciliacion titulo="Estado de cuenta" filas={filasBanco} seleccion={sel}
            onAlternar={alternar} onDeshacer={deshacer} etiquetas={['Retiro', 'Depósito']}
            accion={(f) => (
              <button type="button" onClick={() => setPolizaDe(vista.banco.find((m) => m.clave === f.clave) ?? null)}
                style={{ background: 'none', border: 'none', color: 'var(--teal-light)', cursor: 'pointer', fontSize: '0.75rem' }}>
                Crear póliza
              </button>
            )} />
        </div>
      )}
    </div>
  );
}
