/**
 * Cuotas IMSS del mes (EMA) o del bimestre (EBA) y conciliación contra la cédula del IMSS
 * (P4-10).
 *
 * El backend calcula con el historial de SBC y las nóminas cerradas, lee la cédula (CSV, XLSX
 * o TXT con la plantilla) y marca las diferencias por trabajador. La pantalla no suma nada.
 */

import { useState } from 'react';
import { Calculator, Download, Loader, Upload } from 'lucide-react';
import {
  calcularCuotas, importarCedula, reporteCedula,
  type CedulaImportada, type CuotasPeriodo,
} from '../../services/nominaImssApi';
import { descargarBlob, dinero } from '../contabilidad/comun';
import { tdStyle, thStyle } from '../../utils/styles';
import ErrorAlert from '../common/ErrorAlert';

export default function CuotasCedula({ clienteId }: { clienteId: string }) {
  const [tipo, setTipo] = useState<'EMA' | 'EBA'>('EMA');
  const [ejercicio, setEjercicio] = useState(new Date().getFullYear());
  const [periodo, setPeriodo] = useState(1);
  const [cuotas, setCuotas] = useState<CuotasPeriodo | null>(null);
  const [cedula, setCedula] = useState<CedulaImportada | null>(null);
  const [error, setError] = useState('');
  const [ocupado, setOcupado] = useState(false);

  const correr = async (fn: () => Promise<void>) => {
    setOcupado(true);
    setError('');
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo completar.');
    } finally {
      setOcupado(false);
    }
  };

  const calcular = () => correr(async () => {
    setCuotas(await calcularCuotas(clienteId, ejercicio, tipo === 'EMA' ? { mes: periodo } : { bimestre: periodo }));
  });

  const importar = (archivo: File | undefined) => archivo && correr(async () => {
    const r = await importarCedula(clienteId, archivo, { tipo, ejercicio, periodo });
    setCedula(r.cedula);
  });

  const bajar = (formato: 'csv' | 'xlsx') => cedula && correr(async () => {
    descargarBlob(`conciliacion-${tipo}-${ejercicio}-${periodo}.${formato}`,
      await reporteCedula(clienteId, cedula.id, formato));
  });

  const maximo = tipo === 'EMA' ? 12 : 6;
  return (
    <section className="card" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
      <h2 style={{ fontSize: '1rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 8, margin: 0 }}>
        <Calculator size={16} /> Cuotas IMSS y cédula EMA/EBA
      </h2>
      {error && <ErrorAlert message={error} />}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-xs)', alignItems: 'center' }}>
        <select aria-label="Tipo de cédula" value={tipo} onChange={(e) => { setTipo(e.target.value as 'EMA' | 'EBA'); setPeriodo(1); }}>
          <option value="EMA">EMA (mensual)</option>
          <option value="EBA">EBA (bimestral)</option>
        </select>
        <input aria-label="Ejercicio" type="number" value={ejercicio} onChange={(e) => setEjercicio(Number(e.target.value))} />
        <select aria-label={tipo === 'EMA' ? 'Mes' : 'Bimestre'} value={periodo} onChange={(e) => setPeriodo(Number(e.target.value))}>
          {Array.from({ length: maximo }, (_, i) => i + 1).map((n) => (
            <option key={n} value={n}>{tipo === 'EMA' ? `Mes ${n}` : `Bimestre ${n}`}</option>
          ))}
        </select>
        <button className="btn-primary" disabled={ocupado} onClick={calcular}>
          {ocupado ? <Loader size={14} className="spin" /> : <Calculator size={14} />} Calcular
        </button>
        <label className="btn-secondary" style={{ cursor: 'pointer' }}>
          <Upload size={14} /> Importar cédula
          <input
            aria-label="Archivo de la cédula"
            type="file"
            accept=".csv,.xlsx,.txt"
            style={{ display: 'none' }}
            onChange={(e) => importar(e.target.files?.[0])}
          />
        </label>
      </div>
      {cuotas && (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 600 }}>
            <thead>
              <tr>
                <th style={thStyle}>NSS</th><th style={thStyle}>Empleado</th><th style={thStyle}>Días</th>
                <th style={thStyle}>Aus./Inc.</th><th style={thStyle}>SBC</th><th style={thStyle}>Importe</th>
              </tr>
            </thead>
            <tbody>
              {cuotas.trabajadores.map((t) => (
                <tr key={t.empleado_no}>
                  <td style={tdStyle}>{t.nss || '—'}</td>
                  <td style={tdStyle}>{t.empleado_no} {t.nombre}</td>
                  <td style={tdStyle}>{t.dias}</td>
                  <td style={tdStyle}>{t.dias_ausentismo}/{t.dias_incapacidad}</td>
                  <td style={tdStyle}>{t.sbc}</td>
                  <td style={tdStyle}>{dinero(t.total)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p style={{ margin: 0, fontWeight: 600 }}>Total {cuotas.tipo}: {dinero(cuotas.total)}</p>
          {cuotas.advertencias.map((a) => (
            <p key={a} style={{ margin: 0, fontSize: '0.8rem', color: 'var(--warning)' }}>{a}</p>
          ))}
        </div>
      )}
      {cedula && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-xs)' }}>
          <p role="status" style={{ margin: 0 }}>
            {cedula.diferencias === 0
              ? 'La cédula cuadra trabajador por trabajador.'
              : `${cedula.diferencias} trabajador(es) con diferencias.`}{' '}
            Cálculo {dinero(cedula.conciliacion.total_calculo)} · cédula {dinero(cedula.conciliacion.total_cedula)}.
          </p>
          <ul style={{ margin: 0, paddingLeft: 18, fontSize: '0.85rem' }}>
            {cedula.conciliacion.trabajadores.filter((t) => !t.cuadra).map((t) => (
              <li key={t.nss}>
                <strong>{t.nss}</strong> {t.nombre}:{' '}
                {t.diferencias.map((d) => d.nota ?? `${d.campo} cálculo ${d.calculado} vs cédula ${d.cedula}`).join('; ')}
              </li>
            ))}
          </ul>
          <div style={{ display: 'flex', gap: 'var(--space-xs)' }}>
            <button className="btn-secondary" onClick={() => bajar('csv')}><Download size={14} /> CSV</button>
            <button className="btn-secondary" onClick={() => bajar('xlsx')}><Download size={14} /> Excel</button>
          </div>
        </div>
      )}
    </section>
  );
}
