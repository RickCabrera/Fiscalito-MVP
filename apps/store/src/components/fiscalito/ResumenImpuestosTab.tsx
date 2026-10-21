/**
 * Resumen y actualización de impuestos del CLIENTE ACTIVO (P3-02).
 *
 * La tabla de todos los impuestos del periodo, con importe del sistema, importe
 * a pagar, actualización, recargos, subsidio, compensaciones y total a una
 * fecha de pago. Los importes salen del backend (bóveda + motores); aquí sólo
 * se capturan importe a pagar, subsidio y compensaciones. Exporta a Excel (el
 * backend arma el .xlsx con openpyxl), CSV y PDF.
 */

import { useCallback, useState } from 'react';
import { Download, FileText, Loader, RefreshCw } from 'lucide-react';
import { usePerfilFiscal } from '../../context/usePerfilFiscal';
import {
  exportarResumen, obtenerResumen,
  type CapturaRenglon, type PeticionResumen, type ResumenImpuestos,
} from '../../services/impuestosApi';
import TablaResumen from './TablaResumen';
import { exportarResumenPdf } from './resumenPdf';

const hoy = new Date();

export default function ResumenImpuestosTab() {
  const perfil = usePerfilFiscal();
  const clave = perfil.clienteId;
  const [anio, setAnio] = useState(hoy.getFullYear());
  const [mes, setMes] = useState(hoy.getMonth() === 0 ? 12 : hoy.getMonth());
  const [fechaPago, setFechaPago] = useState(hoy.toISOString().slice(0, 10));
  const [capturas, setCapturas] = useState<Record<string, CapturaRenglon>>({});
  const [resumen, setResumen] = useState<ResumenImpuestos | null>(null);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const peticion = useCallback(
    (): PeticionResumen => ({ anio, mes, fecha_pago: fechaPago, capturas }),
    [anio, mes, fechaPago, capturas],
  );

  const calcularResumen = async () => {
    if (!clave) return;
    setCargando(true);
    setError(null);
    try {
      setResumen(await obtenerResumen(clave, peticion()));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo calcular el resumen.');
    } finally {
      setCargando(false);
    }
  };

  const exportar = async (formato: 'xlsx' | 'csv') => {
    if (!clave) return;
    setError(null);
    try {
      const blob = await exportarResumen(clave, peticion(), formato);
      // El Blob ya trae el tipo que mandó el servidor (xlsx o csv): se descarga tal cual.
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `resumen-impuestos-${clave}-${anio}-${String(mes).padStart(2, '0')}.${formato}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo exportar.');
    }
  };

  const capturar = (claveRenglon: string, campo: keyof CapturaRenglon, valor: string) => {
    setCapturas((prev) => ({
      ...prev,
      [claveRenglon]: { ...prev[claveRenglon], [campo]: valor === '' && campo === 'importe_a_pagar' ? null : valor },
    }));
  };

  if (!clave) {
    return <p className="card">Elige un cliente para ver su resumen de impuestos.</p>;
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div className="card" style={{ display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'end' }}>
        <label style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>Año
          <input className="input-field" type="number" value={anio} aria-label="Año"
            onChange={(e) => setAnio(Number(e.target.value))} style={{ width: 90 }} />
        </label>
        <label style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>Mes
          <input className="input-field" type="number" min={1} max={12} value={mes} aria-label="Mes"
            onChange={(e) => setMes(Number(e.target.value))} style={{ width: 70 }} />
        </label>
        <label style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>Fecha de pago
          <input className="input-field" type="date" value={fechaPago} aria-label="Fecha de pago"
            onChange={(e) => setFechaPago(e.target.value)} />
        </label>
        <button className="btn-primary" onClick={calcularResumen} disabled={cargando}
          style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          {cargando ? <Loader size={14} className="spin" /> : <RefreshCw size={14} />} Calcular
        </button>
        {resumen && (
          <>
            <button className="btn-secondary" onClick={() => exportar('xlsx')}
              style={{ display: 'flex', alignItems: 'center', gap: 6 }}><Download size={14} /> Excel</button>
            <button className="btn-secondary" onClick={() => exportar('csv')}
              style={{ display: 'flex', alignItems: 'center', gap: 6 }}><Download size={14} /> CSV</button>
            <button className="btn-secondary" onClick={() => exportarResumenPdf(resumen, perfil.nombre || clave)}
              style={{ display: 'flex', alignItems: 'center', gap: 6 }}><FileText size={14} /> PDF</button>
          </>
        )}
      </div>
      {error && <p role="alert" style={{ color: 'var(--danger)', margin: 0 }}>{error}</p>}
      {resumen && <TablaResumen resumen={resumen} capturas={capturas} onCapturar={capturar} />}
    </div>
  );
}
