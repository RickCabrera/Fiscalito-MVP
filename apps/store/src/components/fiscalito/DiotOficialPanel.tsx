/**
 * DIOT con el layout de carga masiva 2025 del SAT (P3-05).
 *
 * Los cortes por tasa (16 %, 8 %, 0 %, exento, importación, IVA retenido y no acreditable)
 * salen de los conceptos de cada CFDI de la bóveda, y el `.txt` de 54 campos lo arma y lo
 * VALIDA el backend contra el instructivo vigente: si un renglón no cumple, no se entrega.
 * Tipo de tercero y de operación vienen deducidos y se corrigen por proveedor (se guardan).
 */

import { useCallback, useEffect, useState } from 'react';
import { AlertTriangle, FileDown, Loader } from 'lucide-react';
import {
  descargarDiotTxt, guardarConfigProveedor, obtenerDiot, TIPOS_OPERACION, TIPOS_TERCERO,
  type DiotMes, type ProveedorDiot,
} from '../../services/diotApi';
import { descargarBlob } from '../contabilidad/comun';
import { fmtMoney } from '../../utils/format';
import { thStyle, tdStyle, tdMonoStyle } from '../../utils/styles';
import ErrorAlert from '../common/ErrorAlert';

const OPS_POR_TERCERO: Record<string, string[]> = {
  '04': ['02', '03', '06', '08', '85'], '05': ['02', '03', '07'], '15': ['87'],
};

const select: React.CSSProperties = {
  background: 'var(--bg-input)', color: 'var(--text-primary)', border: '1px solid var(--border)',
  borderRadius: 'var(--radius-sm)', padding: '2px 4px', fontSize: '0.75rem',
};

const suma = (p: ProveedorDiot, ...claves: string[]) =>
  claves.reduce((s, k) => s + (p.campos[k] ?? 0), 0);

export default function DiotOficialPanel({ clave, anio, mes }: { clave: string; anio: number; mes: number }) {
  const [diot, setDiot] = useState<DiotMes | null>(null);
  const [error, setError] = useState('');
  const [bajando, setBajando] = useState(false);

  const cargar = useCallback(() => {
    if (anio < 2025) return;
    obtenerDiot(clave, anio, mes).then((d) => { setError(''); setDiot(d); })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : 'No se pudo cargar la DIOT.'));
  }, [clave, anio, mes]);

  useEffect(() => { cargar(); }, [cargar]);

  const cambiar = async (p: ProveedorDiot, campo: 'tipo_tercero' | 'tipo_operacion', valor: string) => {
    const config = { ...p.config, [campo]: valor };
    if (campo === 'tipo_tercero') config.tipo_operacion = null;
    try {
      await guardarConfigProveedor(clave, p.rfc, config as ProveedorDiot['config']);
      cargar();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo guardar.');
    }
  };

  const bajar = async () => {
    setBajando(true);
    setError('');
    try {
      descargarBlob(`DIOT_${clave}_${anio}${String(mes).padStart(2, '0')}.txt`,
        await descargarDiotTxt(clave, anio, mes));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo generar el archivo.');
    } finally {
      setBajando(false);
    }
  };

  if (anio < 2025) {
    return <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
      El archivo de carga masiva de 54 campos aplica desde el ejercicio 2025.
    </p>;
  }
  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <h3 style={{ fontSize: '0.95rem', fontWeight: 600 }}>DIOT — carga masiva (layout SAT 2025)</h3>
      {error && <ErrorAlert message={error} />}
      {!diot && !error && <Loader size={16} className="spin" aria-label="Cargando DIOT" />}
      {diot && diot.proveedores.length === 0 && (
        <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', margin: 0 }}>
          No hay operaciones con proveedores pagadas en el mes.
        </p>
      )}
      {diot && diot.proveedores.length > 0 && (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.78rem' }}>
            <thead>
              <tr>{['Proveedor', 'Tercero', 'Operación', '16 %', '8 %', '0 % / exento', 'IVA acred.', 'IVA no acred.', 'IVA ret.']
                .map((h) => <th key={h} style={thStyle}>{h}</th>)}</tr>
            </thead>
            <tbody>
              {diot.proveedores.map((p) => (
                <tr key={p.rfc} style={{ borderTop: '1px solid var(--border)' }}>
                  <td style={tdStyle}>{p.nombre || p.rfc}<br />
                    <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '0.7rem' }}>{p.rfc}</span></td>
                  <td style={tdStyle}>
                    <select aria-label={`Tipo de tercero de ${p.rfc}`} style={select} value={p.tipo_tercero}
                      onChange={(e) => cambiar(p, 'tipo_tercero', e.target.value)}>
                      {Object.entries(TIPOS_TERCERO).map(([k, v]) => <option key={k} value={k}>{k} {v}</option>)}
                    </select>
                  </td>
                  <td style={tdStyle}>
                    <select aria-label={`Tipo de operación de ${p.rfc}`} style={select} value={p.tipo_operacion}
                      onChange={(e) => cambiar(p, 'tipo_operacion', e.target.value)}>
                      {(OPS_POR_TERCERO[p.tipo_tercero] ?? []).map((k) => (
                        <option key={k} value={k}>{k} {TIPOS_OPERACION[k]}</option>))}
                    </select>
                  </td>
                  <td style={tdMonoStyle}>{fmtMoney(suma(p, 'valor_tasa_16', 'valor_importacion_tangibles', 'valor_importacion_intangibles'))}</td>
                  <td style={tdMonoStyle}>{fmtMoney(suma(p, 'valor_region_norte', 'valor_region_sur'))}</td>
                  <td style={tdMonoStyle}>{fmtMoney(suma(p, 'tasa_0', 'exentos', 'importacion_exentos'))}</td>
                  <td style={tdMonoStyle}>{fmtMoney(Object.entries(p.campos)
                    .filter(([k]) => k.startsWith('acreditable_')).reduce((s, [, v]) => s + v, 0))}</td>
                  <td style={tdMonoStyle}>{fmtMoney(Object.entries(p.campos)
                    .filter(([k]) => k.startsWith('no_acreditable_')).reduce((s, [, v]) => s + v, 0))}</td>
                  <td style={tdMonoStyle}>{fmtMoney(suma(p, 'iva_retenido'))}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {diot && [...diot.advertencias, ...diot.proveedores.flatMap((p) => p.advertencias)].map((a) => (
        <p key={a} style={{ fontSize: '0.78rem', color: 'var(--warning)', margin: 0, display: 'flex', gap: 6 }}>
          <AlertTriangle size={14} /> {a}
        </p>
      ))}
      {diot && diot.errores_layout.length > 0 && (
        <ErrorAlert message={`El archivo no cumple el layout: ${diot.errores_layout.slice(0, 3).join(' · ')}`} />
      )}
      {diot && diot.proveedores.length > 0 && (
        <div>
          <button className="btn-secondary" onClick={bajar} disabled={bajando || diot.errores_layout.length > 0}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
            {bajando ? <Loader size={16} className="spin" /> : <FileDown size={16} />} Descargar DIOT (.txt)
          </button>
          <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: 6 }}>
            {diot.layout}. Importes en pesos enteros, validado contra el instructivo del SAT (enero 2025).
          </p>
        </div>
      )}
    </div>
  );
}
