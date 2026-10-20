/**
 * Dispersión bancaria de una nómina CERRADA (P4-12).
 *
 * Elegir layout (banco) y la cuenta de cargo del patrón —las cuentas bancarias del cliente
 * que ya existen en conciliación (P2-06)—, capturar los datos del contrato con el banco y
 * generar. El backend arma el archivo, lo relee y lo cuadra al centavo contra la nómina;
 * aquí se pintan los excluidos con su motivo ANTES de descargar, y un layout
 * POR CONFIRMAR lo dice encima del botón.
 */

import { useEffect, useMemo, useState } from 'react';
import { listarCuentasBancarias, type CuentaBancaria } from '../../services/conciliacionApi';
import {
  bytesDeBase64,
  generarDispersion,
  listarLayouts,
  type Layouts,
  type ResultadoDispersion,
} from '../../services/dispersionApi';
import { descargarBytes } from '../../services/exportadores/descargar';
import { fmtMoney } from '../../utils/format';
import { envoltura, fila, tabla, td, tdNum, th, thNum } from './estilosTabla';

const campo: React.CSSProperties = {
  padding: 'var(--space-xs) var(--space-sm)', background: 'var(--bg-input)', color: 'var(--text-primary)',
  border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)',
};

export default function PanelDispersion({ clienteId, periodoId }: { clienteId: string; periodoId: number }) {
  const [catalogo, setCatalogo] = useState<Layouts | null>(null);
  const [cuentas, setCuentas] = useState<CuentaBancaria[]>([]);
  const [layoutId, setLayoutId] = useState('generico');
  const [cuentaId, setCuentaId] = useState<number | null>(null);
  const [datos, setDatos] = useState<Record<string, string>>({});
  const [formato, setFormato] = useState<'csv' | 'xlsx'>('csv');
  const [resultado, setResultado] = useState<ResultadoDispersion | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);

  useEffect(() => {
    let vivo = true;
    Promise.all([listarLayouts(clienteId), listarCuentasBancarias(clienteId).catch(() => ({ cuentas: [] }))])
      .then(([l, c]) => {
        if (!vivo) return;
        setCatalogo(l);
        if (!l.layouts.some((x) => x.id === 'generico') && l.layouts[0]) setLayoutId(l.layouts[0].id);
        setCuentas(c.cuentas.filter((x) => x.activa));
      })
      .catch((e: Error) => vivo && setError(e.message));
    return () => {
      vivo = false;
    };
  }, [clienteId]);

  const layout = useMemo(() => catalogo?.layouts.find((l) => l.id === layoutId) ?? null, [catalogo, layoutId]);
  const cuentasDelBanco = cuentas.filter((c) => !layout?.banco || c.banco === layout.banco);

  function elegirLayout(id: string) {
    setLayoutId(id);
    setResultado(null);
    setCuentaId(null);
    setDatos({ ...(catalogo?.datos_guardados[id] ?? {}) });
  }

  async function generar() {
    if (!layout) return;
    setCargando(true);
    setError(null);
    setResultado(null);
    try {
      setResultado(
        await generarDispersion(clienteId, periodoId, {
          layout: layout.id,
          cuenta_cargo_id: cuentaId,
          datos_banco: datos,
          ...(layout.id === 'generico' ? { formato } : {}),
        }),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo generar la dispersión');
    } finally {
      setCargando(false);
    }
  }

  if (!catalogo && !error) return <p style={{ color: 'var(--text-muted)' }}>Cargando layouts…</p>;

  return (
    <section aria-label="Dispersión bancaria" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
      <h3 style={{ margin: 0, fontSize: '1rem' }}>Dispersión bancaria</h3>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-sm)', alignItems: 'end' }}>
        <label style={{ display: 'flex', flexDirection: 'column', fontSize: '0.8rem' }}>
          Banco / layout
          <select style={campo} value={layoutId} onChange={(e) => elegirLayout(e.target.value)}>
            {catalogo?.layouts.map((l) => (
              <option key={l.id} value={l.id}>
                {l.nombre}
                {l.estado === 'por_confirmar' ? ' (por confirmar)' : ''}
              </option>
            ))}
          </select>
        </label>
        {layout?.banco && (
          <label style={{ display: 'flex', flexDirection: 'column', fontSize: '0.8rem' }}>
            Cuenta de cargo
            <select
              style={campo}
              value={cuentaId ?? ''}
              onChange={(e) => setCuentaId(e.target.value ? Number(e.target.value) : null)}
            >
              <option value="">— elige —</option>
              {cuentasDelBanco.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.nombre || c.banco} · {c.numero}
                </option>
              ))}
            </select>
          </label>
        )}
        {layout?.datos_requeridos.map((d) => (
          <label key={d.clave} style={{ display: 'flex', flexDirection: 'column', fontSize: '0.8rem' }}>
            {d.etiqueta}
            {d.obligatorio ? ' *' : ''}
            <input
              style={campo}
              value={datos[d.clave] ?? ''}
              placeholder={d.default}
              onChange={(e) => setDatos({ ...datos, [d.clave]: e.target.value })}
            />
          </label>
        ))}
        {layout?.id === 'generico' && (
          <label style={{ display: 'flex', flexDirection: 'column', fontSize: '0.8rem' }}>
            Formato
            <select style={campo} value={formato} onChange={(e) => setFormato(e.target.value as 'csv' | 'xlsx')}>
              <option value="csv">CSV</option>
              <option value="xlsx">Excel (XLSX)</option>
            </select>
          </label>
        )}
        <button className="btn-primary" disabled={cargando || !layout} onClick={generar}>
          {cargando ? 'Generando…' : 'Generar archivo'}
        </button>
      </div>
      {layout?.banco && cuentasDelBanco.length === 0 && (
        <p style={{ margin: 0, color: 'var(--warning)', fontSize: '0.82rem' }}>
          Este cliente no tiene cuentas {layout.nombre} activas. Dalas de alta en Contabilito → Conciliación.
        </p>
      )}
      {layout && (
        <p style={{ margin: 0, fontSize: '0.78rem', color: layout.estado === 'por_confirmar' ? 'var(--warning)' : 'var(--text-muted)' }}>
          {layout.estado === 'por_confirmar' ? 'POR CONFIRMAR CON MANUAL DEL BANCO. ' : 'Verificado. '}
          Fuente: {layout.fuente}
        </p>
      )}
      {error && (
        <p role="alert" style={{ margin: 0, color: 'var(--danger)' }}>
          {error}
        </p>
      )}
      {resultado && <ResultadoPanel r={resultado} />}
    </section>
  );
}

function ResultadoPanel({ r }: { r: ResultadoDispersion }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
      <p style={{ margin: 0 }}>
        Nómina {fmtMoney(Number(r.total_nomina))} = archivo <strong>{fmtMoney(Number(r.total_archivo))}</strong> ({r.incluidos.length}{' '}
        pagos) + excluidos {fmtMoney(Number(r.total_excluidos))} ({r.excluidos.length}).{' '}
        <span style={{ color: r.cuadra ? 'var(--success)' : 'var(--danger)' }}>{r.cuadra ? 'Cuadra al centavo.' : 'NO cuadra.'}</span>
      </p>
      {r.advertencias.map((a) => (
        <p key={a} style={{ margin: 0, color: 'var(--warning)', fontSize: '0.85rem' }}>
          {a}
        </p>
      ))}
      {r.excluidos.length > 0 && (
        <div style={envoltura}>
          <table style={tabla(560)} aria-label="Excluidos de la dispersión">
            <thead>
              <tr>
                <th style={th}>Empleado</th>
                <th style={thNum}>Neto</th>
                <th style={th}>Motivo</th>
              </tr>
            </thead>
            <tbody>
              {r.excluidos.map((e, i) => (
                <tr key={e.empleado_no} style={fila(i)}>
                  <td style={td}>
                    {e.empleado_no} · {e.nombre}
                  </td>
                  <td style={tdNum}>{fmtMoney(Number(e.neto))}</td>
                  <td style={td}>{e.motivo}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {r.archivo && (
        <div>
          <button
            className="btn-secondary"
            onClick={() => r.archivo && descargarBytes(r.archivo.nombre, bytesDeBase64(r.archivo.base64))}
          >
            Descargar {r.archivo.nombre}
          </button>
        </div>
      )}
    </div>
  );
}
