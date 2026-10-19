/**
 * Cálculo anual del CLIENTE ACTIVO y sus papeles de trabajo (P3-06), como
 * "Cálculo anual ISR → Generar archivo" de Contadigital.
 *
 * El cálculo es del backend (`POST /impuestos/clientes/{clave}/anual`): personas
 * físicas 612/606/625/626 con su mes a mes, y morales 601 / RESICO PM con
 * ingresos, deducciones, ajuste anual por inflación, coeficiente, PTU, pérdidas
 * y pagos provisionales. "Generar archivo" baja el Excel de `.../anual/papeles`,
 * que sale del MISMO cálculo: lo que se ve aquí es lo que trae el archivo.
 */

import { useState } from 'react';
import { Download, FileCheck, Loader, RefreshCw } from 'lucide-react';
import { usePerfilFiscal } from '../../context/usePerfilFiscal';
import { calcularAnual, papelesAnual, type ResultadoAnual } from '../../services/anualApi';
import TablaMeses from './TablaMeses';
import { CELDA, type ColumnaMes } from './tablaMesesUtil';

const COLUMNAS_PF: ColumnaMes[] = [
  { campo: 'ingresos', titulo: 'Ingresos' },
  { campo: 'deducciones', titulo: 'Deducciones' },
  { campo: 'base', titulo: 'Base' },
  { campo: 'isr_causado', titulo: 'ISR causado' },
  { campo: 'retenciones', titulo: 'Retenciones' },
  { campo: 'pago_determinado', titulo: 'Pago determinado' },
  { campo: 'pago_efectuado', titulo: 'Pago efectuado' },
];

const COLUMNAS_PM: ColumnaMes[] = [
  { campo: 'ingresos', titulo: 'Ingresos' },
  { campo: 'deducciones', titulo: 'Deducciones' },
  { campo: 'no_deducibles', titulo: 'No deducibles' },
  { campo: 'retenciones', titulo: 'Retenciones' },
  { campo: 'pago_provisional', titulo: 'Pago provisional' },
];

const DESTACADOS = new Set(['isr_ejercicio', 'a_cargo', 'a_favor']);

export default function AnualClienteTab() {
  const perfil = usePerfilFiscal();
  const clave = perfil.clienteId;
  const [anio, setAnio] = useState(new Date().getFullYear() - 1);
  const [resultado, setResultado] = useState<ResultadoAnual | null>(null);
  const [cargando, setCargando] = useState(false);
  const [generando, setGenerando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const calcular = async () => {
    if (!clave) return;
    setCargando(true);
    setError(null);
    try {
      setResultado(await calcularAnual(clave, anio));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo calcular la anual.');
    } finally {
      setCargando(false);
    }
  };

  const generarArchivo = async () => {
    if (!clave) return;
    setGenerando(true);
    setError(null);
    try {
      const blob = await papelesAnual(clave, anio);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `papeles-anual-${clave}-${anio}.xlsx`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo generar el archivo.');
    } finally {
      setGenerando(false);
    }
  };

  if (!clave) return <p className="card">Elige un cliente para calcular su anual.</p>;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div className="card" style={{ display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'end' }}>
        <h3 style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '1rem', fontWeight: 600, margin: 0, flexBasis: '100%' }}>
          <FileCheck size={18} /> Cálculo anual ISR
        </h3>
        <label style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>Ejercicio
          <input className="input-field" type="number" value={anio} aria-label="Ejercicio"
            onChange={(e) => setAnio(Number(e.target.value))} style={{ width: 90 }} />
        </label>
        <button className="btn-primary" onClick={calcular} disabled={cargando}
          style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          {cargando ? <Loader size={14} className="spin" /> : <RefreshCw size={14} />} Calcular
        </button>
        <button className="btn-secondary" onClick={generarArchivo} disabled={generando}
          style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          {generando ? <Loader size={14} className="spin" /> : <Download size={14} />} Generar archivo
        </button>
      </div>

      {error && <p role="alert" style={{ color: 'var(--danger)', margin: 0 }}>{error}</p>}

      {resultado && (
        <>
          <div className="card" style={{ overflowX: 'auto' }}>
            <p style={{ margin: '0 0 8px', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
              Ejercicio {resultado.anio} · régimen {resultado.regimen} · fuente{' '}
              {resultado.fuente === 'contabilidad' ? 'contabilidad' : 'bóveda de CFDI'}
            </p>
            <table aria-label="Cálculo anual" style={{ width: '100%', borderCollapse: 'collapse' }}>
              <tbody>
                {resultado.renglones.map((r) => (
                  <tr key={r.clave} style={{ fontWeight: DESTACADOS.has(r.clave) ? 700 : 400 }}>
                    <td style={{ ...CELDA, textAlign: 'left', fontFamily: 'inherit' }}>{r.concepto}</td>
                    <td style={CELDA} data-testid={`anual-${r.clave}`}>{r.importe}</td>
                    <td style={{ ...CELDA, textAlign: 'left', color: 'var(--text-muted)', fontFamily: 'inherit' }}>
                      {r.fundamento}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {resultado.coeficiente && (
              <p style={{ margin: '10px 0 0', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                Coeficiente de utilidad para el ejercicio siguiente: <strong>{resultado.coeficiente.siguiente}</strong>
                {resultado.ptu && <> · PTU a repartir: <strong>{resultado.ptu.a_repartir}</strong></>}
              </p>
            )}
          </div>
          <TablaMeses etiqueta="Mes a mes" columnas={resultado.tipo === 'pf' ? COLUMNAS_PF : COLUMNAS_PM}
            filas={resultado.meses} />
          <ul style={{ margin: 0, paddingLeft: 18, fontSize: '0.78rem', color: 'var(--text-muted)' }}>
            {resultado.notas.map((n) => <li key={n}>{n}</li>)}
          </ul>
        </>
      )}
    </div>
  );
}
