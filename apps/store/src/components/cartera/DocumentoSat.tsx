/**
 * Un documento del SAT en la ficha del cliente (P1-05): opinión de cumplimiento 32-D o
 * constancia de situación fiscal. Semáforo, última fecha, "Obtener ahora", subir PDF,
 * historial y descarga. El sentido de la opinión lo decide el servidor (lo lee del PDF o
 * del proveedor); aquí sólo se pinta.
 */

import { useCallback, useEffect, useState } from 'react';
import { Download, Loader, RefreshCw, Upload } from 'lucide-react';
import ErrorAlert from '../common/ErrorAlert';
import EstadoTrabajos from '../common/EstadoTrabajos';
import {
  COLOR_SEMAFORO, descargarPdfCumplimiento, historialCumplimiento,
  obtenerAhora, subirPdfCumplimiento,
  type HistorialCumplimiento, type ResultadoOpinion, type TipoDocumento,
} from '../../services/satVerificacionApi';
import { etiquetaSemaforo } from '../../services/semaforoSat';

const TITULO: Record<TipoDocumento, string> = {
  opinion: 'Opinión de cumplimiento (32-D)',
  constancia: 'Constancia de situación fiscal',
};

const RESULTADO: Record<ResultadoOpinion, string> = {
  positiva: 'Positiva', negativa: 'Negativa', sin_obligaciones: 'Sin obligaciones',
  desconocido: 'Sin leer',
};

const ORIGEN: Record<string, string> = {
  falso: 'Prueba', portal_sat: 'Portal SAT', proveedor: 'Proveedor', manual: 'Subido a mano',
};

export default function DocumentoSat({ clave, tipo }: { clave: string; tipo: TipoDocumento }) {
  const [datos, setDatos] = useState<HistorialCumplimiento | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const [trabajos, setTrabajos] = useState(0);
  const [vuelta, setVuelta] = useState(0);

  useEffect(() => {
    let vigente = true;
    historialCumplimiento(clave, tipo)
      .then((d) => { if (vigente) { setDatos(d); setError(null); } })
      .catch((e: unknown) => { if (vigente) setError(e instanceof Error ? e.message : 'No se pudo cargar.'); });
    return () => { vigente = false; };
  }, [clave, tipo, vuelta]);

  const accion = useCallback(async (fn: () => Promise<unknown>) => {
    setOcupado(true);
    setError(null);
    try {
      await fn();
      setVuelta((v) => v + 1);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo completar.');
    } finally {
      setOcupado(false);
    }
  }, []);

  const obtener = () => accion(async () => {
    await obtenerAhora(clave, tipo);
    setTrabajos((n) => n + 1);
  });

  const subir = (archivo: File | undefined) => {
    if (!archivo) return;
    void accion(() => subirPdfCumplimiento(clave, tipo, archivo));
  };

  const descargar = (id: number, fecha: string) => accion(async () => {
    const blob = await descargarPdfCumplimiento(clave, id);
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${tipo}-${clave}-${fecha}.pdf`;
    a.click();
    URL.revokeObjectURL(url);
  });

  const esOpinion = tipo === 'opinion';
  const manual = datos?.via === 'manual';

  return (
    <div style={{ display: 'grid', gap: 'var(--space-sm)' }} aria-label={TITULO[tipo]}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)', flexWrap: 'wrap' }}>
        <strong style={{ fontSize: '0.92rem' }}>{TITULO[tipo]}</strong>
        {datos && esOpinion && (
          <span data-semaforo={datos.semaforo} data-origen={datos.origen ?? undefined}
            title={datos.marca ?? undefined} style={{
              display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: '0.8rem',
              fontWeight: 600, color: COLOR_SEMAFORO[datos.semaforo],
            }}>
            <span aria-hidden style={{ width: 10, height: 10, borderRadius: '50%', background: COLOR_SEMAFORO[datos.semaforo] }} />
            {etiquetaSemaforo(datos.semaforo, datos.origen)}
          </span>
        )}
        {datos && esOpinion && datos.marca && (
          <span role="note" style={{ fontSize: '0.75rem', color: 'var(--warning)' }}>{datos.marca}</span>
        )}
        {datos?.ultimo && (
          <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
            Última: {datos.ultimo.fecha}{datos.ultimo.folio ? ` · folio ${datos.ultimo.folio}` : ''}
          </span>
        )}
        <span style={{ flex: 1 }} />
        {!manual && (
          <button type="button" className="btn-secondary" disabled={ocupado} onClick={() => void obtener()}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <RefreshCw size={14} /> Obtener ahora
          </button>
        )}
        <label className="btn-secondary" style={{ display: 'inline-flex', alignItems: 'center', gap: 6, cursor: 'pointer' }}>
          <Upload size={14} /> Subir PDF
          <input type="file" accept="application/pdf,.pdf" hidden aria-label={`Subir PDF de ${TITULO[tipo]}`}
            disabled={ocupado} onChange={(e) => { subir(e.target.files?.[0]); e.target.value = ''; }} />
        </label>
      </div>

      {!datos && !error && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
          <Loader size={14} className="spin" /> Cargando…
        </div>
      )}
      {error && <ErrorAlert message={error} />}
      {datos?.ultimo?.aviso && <ErrorAlert message={datos.ultimo.aviso} />}
      {trabajos > 0 && <EstadoTrabajos cliente={clave} tipo="sat.cumplimiento_obtener" limite={2} recarga={trabajos} />}
      {trabajos > 0 && (
        <button type="button" className="btn-secondary" style={{ justifySelf: 'start' }}
          onClick={() => setVuelta((v) => v + 1)}>Ver resultado</button>
      )}

      {datos && datos.historial.length === 0 && (
        <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-muted)' }}>
          Sin documentos todavía.{manual ? ' La vía configurada es manual: descárgalo del portal del SAT y súbelo.' : ''}
        </p>
      )}
      {datos && datos.historial.length > 0 && (
        <ul style={{ listStyle: 'none', margin: 0, padding: 0 }} aria-label={`Historial de ${TITULO[tipo]}`}>
          {datos.historial.map((d) => (
            <li key={d.id} style={{
              display: 'flex', alignItems: 'center', gap: 'var(--space-sm)', fontSize: '0.83rem',
              padding: 'var(--space-xs) 0', borderBottom: '1px solid var(--border)',
            }}>
              <span style={{ fontFamily: "'JetBrains Mono', monospace", minWidth: 90 }}>{d.fecha}</span>
              {esOpinion && <span style={{ minWidth: 110, fontWeight: 600 }}>{RESULTADO[d.resultado]}</span>}
              <span style={{ color: 'var(--text-secondary)', flex: 1 }}>{ORIGEN[d.origen] ?? d.origen}</span>
              <button type="button" className="btn-secondary" disabled={ocupado} aria-label={`Descargar PDF del ${d.fecha}`}
                onClick={() => void descargar(d.id, d.fecha)} style={{ padding: '2px 10px' }}>
                <Download size={14} />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
