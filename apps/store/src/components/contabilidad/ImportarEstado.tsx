/**
 * Subir un estado de cuenta (P2-06): CSV, XLSX, OFX o PDF. Para CSV/XLSX se
 * puede elegir una plantilla guardada o capturar el mapeo de columnas y
 * guardarlo como plantilla del banco. Sin mapeo, el backend reconoce los
 * encabezados comunes. Los PDF se leen con diseños POR CONFIRMAR: el reporte de
 * la importación lo advierte.
 */

import { useEffect, useState } from 'react';
import { Loader, Upload } from 'lucide-react';
import {
  guardarPlantilla, importarEstado, listarPlantillas,
  type CuentaBancaria, type EstadoImportado, type Plantilla,
} from '../../services/conciliacionApi';
import ErrorAlert from '../common/ErrorAlert';
import { mensaje } from './comun';
import { labelStyle } from '../../utils/styles';

const CAMPOS = ['fecha', 'concepto', 'referencia', 'cargo', 'abono', 'importe', 'saldo'] as const;

interface Props {
  clave: string;
  cuenta: CuentaBancaria;
  onImportado: () => void;
}

export default function ImportarEstado({ clave, cuenta, onImportado }: Props) {
  const [archivo, setArchivo] = useState<File | null>(null);
  const [plantillas, setPlantillas] = useState<Plantilla[]>([]);
  const [plantillaId, setPlantillaId] = useState<number | null>(null);
  const [verMapeo, setVerMapeo] = useState(false);
  const [mapeo, setMapeo] = useState<Record<string, string>>({});
  const [nombrePlantilla, setNombrePlantilla] = useState('');
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hecho, setHecho] = useState<EstadoImportado | null>(null);

  useEffect(() => {
    let vivo = true;
    listarPlantillas(clave)
      .then((r) => { if (vivo) setPlantillas(r.plantillas); })
      .catch((e: unknown) => { if (vivo) setError(mensaje(e, 'No se pudieron cargar las plantillas.')); });
    return () => { vivo = false; };
  }, [clave]);

  const mapeoLimpio = Object.fromEntries(Object.entries(mapeo).filter(([, v]) => v.trim() !== ''));

  const subir = async () => {
    if (!archivo) return;
    setOcupado(true); setError(null); setHecho(null);
    try {
      const usarMapeo = verMapeo && Object.keys(mapeoLimpio).length > 0;
      if (usarMapeo && nombrePlantilla.trim()) {
        const formato = archivo.name.toLowerCase().endsWith('.xlsx') ? 'xlsx' : 'csv';
        const p = (await guardarPlantilla(clave, { nombre: nombrePlantilla.trim(), banco: cuenta.banco, formato, mapeo: mapeoLimpio })).plantilla;
        setPlantillas((xs) => [...xs.filter((x) => x.id !== p.id), p]);
      }
      const r = await importarEstado(clave, cuenta.id, archivo, {
        plantillaId, mapeo: usarMapeo ? mapeoLimpio : null,
      });
      setHecho(r.estado);
      onImportado();
    } catch (e) {
      setError(mensaje(e, 'No se pudo importar el estado de cuenta.'));
    } finally {
      setOcupado(false);
    }
  };

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{ display: 'flex', gap: 'var(--space-md)', flexWrap: 'wrap', alignItems: 'flex-end' }}>
        <label><span style={labelStyle}>Estado de cuenta (CSV, XLSX, OFX o PDF)</span>
          <input type="file" aria-label="Estado de cuenta" accept=".csv,.xlsx,.ofx,.qfx,.pdf"
            onChange={(e) => setArchivo(e.target.files?.[0] ?? null)} /></label>
        <label><span style={labelStyle}>Plantilla</span>
          <select className="input-field" value={plantillaId ?? ''} onChange={(e) => setPlantillaId(e.target.value ? Number(e.target.value) : null)}>
            <option value="">Detectar columnas</option>
            {plantillas.map((p) => <option key={p.id} value={p.id}>{p.nombre}</option>)}
          </select></label>
        <button type="button" className="btn-secondary" onClick={() => setVerMapeo(!verMapeo)}>
          {verMapeo ? 'Ocultar columnas' : 'Mapear columnas'}
        </button>
        <button type="button" className="btn-primary" onClick={subir} disabled={!archivo || ocupado}>
          {ocupado ? <Loader size={14} className="spin" /> : <Upload size={14} />} Subir
        </button>
      </div>
      {verMapeo && (
        <div style={{ display: 'flex', gap: 'var(--space-sm)', flexWrap: 'wrap' }}>
          {CAMPOS.map((c) => (
            <label key={c}><span style={labelStyle}>{c}</span>
              <input className="input-field" style={{ width: 120 }} placeholder="Encabezado o letra" value={mapeo[c] ?? ''}
                onChange={(e) => setMapeo({ ...mapeo, [c]: e.target.value })} /></label>
          ))}
          <label><span style={labelStyle}>formato_fecha</span>
            <input className="input-field" style={{ width: 110 }} placeholder="%d/%m/%Y" value={mapeo.formato_fecha ?? ''}
              onChange={(e) => setMapeo({ ...mapeo, formato_fecha: e.target.value })} /></label>
          <label><span style={labelStyle}>Guardar como plantilla</span>
            <input className="input-field" placeholder="p. ej. BBVA CSV" value={nombrePlantilla}
              onChange={(e) => setNombrePlantilla(e.target.value)} /></label>
        </div>
      )}
      {error && <ErrorAlert message={error} />}
      {hecho && (
        <div role="status" style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
          {hecho.nuevos} movimientos nuevos, {hecho.duplicados} ya estaban ({hecho.desde} a {hecho.hasta}).
          {hecho.advertencias.map((a) => <div key={a} style={{ color: 'var(--warning)' }}>{a}</div>)}
        </div>
      )}
    </div>
  );
}
