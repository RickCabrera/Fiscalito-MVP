/**
 * Zona de carga de la bóveda (P0-03): XML sueltos y ZIP, varios a la vez, y el
 * reporte que devuelve el backend —importados, duplicados ("ya existía") y
 * rechazados con su razón—.
 *
 * No filtra por extensión antes de subir: el backend decide qué es XML, qué es
 * ZIP y qué se rechaza, y lo dice con nombre en el reporte. Filtrar aquí
 * escondería justo los archivos que el contador necesita ver rechazados.
 */

import { useRef, useState } from 'react';
import { Loader, UploadCloud } from 'lucide-react';
import { importarCfdi, type ReporteImportacion } from '../../services/bovedaApi';
import ErrorAlert from '../common/ErrorAlert';

interface Props {
  clave: string;
  /** Se llama tras una carga con al menos un importado, para refrescar la tabla. */
  onImportado: () => void;
}

export default function CargaBoveda({ clave, onImportado }: Props) {
  const entrada = useRef<HTMLInputElement>(null);
  const [subiendo, setSubiendo] = useState(false);
  const [arrastrando, setArrastrando] = useState(false);
  const [reporte, setReporte] = useState<ReporteImportacion | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function subir(lista: FileList | File[] | null) {
    const archivos = lista ? Array.from(lista) : [];
    if (archivos.length === 0 || subiendo) return;
    setSubiendo(true);
    setError(null);
    setReporte(null);
    try {
      const r = await importarCfdi(clave, archivos);
      setReporte(r);
      if (r.importados > 0) onImportado();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudieron subir los archivos.');
    } finally {
      setSubiendo(false);
      if (entrada.current) entrada.current.value = '';
    }
  }

  return (
    <div className="card" style={{ padding: 'var(--space-lg)', display: 'grid', gap: 'var(--space-md)' }}>
      <div
        role="button"
        tabIndex={0}
        aria-label="Subir XML o ZIP a la bóveda"
        onClick={() => entrada.current?.click()}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') entrada.current?.click(); }}
        onDragOver={(e) => { e.preventDefault(); setArrastrando(true); }}
        onDragLeave={() => setArrastrando(false)}
        onDrop={(e) => { e.preventDefault(); setArrastrando(false); void subir(e.dataTransfer.files); }}
        style={{
          border: `2px dashed ${arrastrando ? 'var(--border-active)' : 'var(--border)'}`,
          borderRadius: 'var(--radius-sm)', padding: 'var(--space-xl)', textAlign: 'center',
          cursor: subiendo ? 'progress' : 'pointer', background: arrastrando ? 'var(--teal-bg-subtle)' : 'transparent',
        }}
      >
        {subiendo ? <Loader size={24} className="spin" /> : <UploadCloud size={24} color="var(--teal-light)" />}
        <div style={{ fontWeight: 600, marginTop: 8 }}>
          {subiendo ? 'Subiendo y clasificando…' : 'Arrastra XML o ZIP aquí, o haz clic para elegir'}
        </div>
        <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginTop: 4 }}>
          Varios a la vez. Un mismo UUID se guarda una sola vez; un ZIP dentro de otro no se abre.
        </div>
        <input
          ref={entrada}
          type="file"
          multiple
          accept=".xml,.XML,.zip,.ZIP,application/xml,text/xml,application/zip"
          data-testid="entrada-boveda"
          style={{ display: 'none' }}
          onChange={(e) => void subir(e.target.files)}
        />
      </div>

      {error && <ErrorAlert message={error} />}
      {reporte && <ReporteCarga reporte={reporte} />}
    </div>
  );
}

function ReporteCarga({ reporte }: { reporte: ReporteImportacion }) {
  const cifra = (n: number, texto: string, color: string) => (
    <div style={{ display: 'grid', gap: 2 }}>
      <span style={{ fontSize: '1.4rem', fontWeight: 700, color }}>{n}</span>
      <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>{texto}</span>
    </div>
  );
  return (
    <section aria-label="Reporte de la carga" style={{ display: 'grid', gap: 'var(--space-sm)' }}>
      <div style={{ display: 'flex', gap: 'var(--space-xl)', flexWrap: 'wrap' }}>
        {cifra(reporte.importados, 'importados', 'var(--success)')}
        {cifra(reporte.duplicados, 'ya existían', 'var(--text-primary)')}
        {cifra(reporte.rechazados.length, 'rechazados', reporte.rechazados.length ? 'var(--danger)' : 'var(--text-primary)')}
      </div>
      {reporte.rfc_deducido && (
        <p role="status" style={{ margin: 0, fontSize: '0.85rem', color: 'var(--warning)' }}>
          Este cliente no tiene RFC capturado. Se clasificó con <strong>{reporte.rfc_cliente}</strong>,
          el RFC que más se repite en los comprobantes. Captúralo en su ficha si no es el correcto.
        </p>
      )}
      {reporte.rechazados.length > 0 && (
        <details open={reporte.rechazados.length <= 10}>
          <summary style={{ cursor: 'pointer', fontSize: '0.88rem' }}>Archivos rechazados</summary>
          <ul style={{ margin: '8px 0 0', paddingLeft: 18, fontSize: '0.83rem', color: 'var(--text-secondary)' }}>
            {reporte.rechazados.map((r) => (
              <li key={r.archivo}><code>{r.archivo}</code>: {r.razon}</li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}
