/** Lista de solicitudes al SAT con su estado y el mensaje en español (P1-01). */

import type { EstadoSolicitud, SolicitudSat } from '../../services/satDescargaApi';
import { envoltura, tabla, td, th } from '../nomina/estilosTabla';

const ETIQUETA_SOLICITUD: Record<EstadoSolicitud, string> = {
  pendiente: 'Pendiente',
  solicitada: 'Solicitada',
  en_proceso: 'En proceso en el SAT',
  descargando: 'Descargando',
  terminada: 'Terminada',
  sin_datos: 'Sin movimientos',
  fallida: 'Fallida',
  dividida: 'Partida en rangos',
};

const COLOR: Partial<Record<EstadoSolicitud, string>> = {
  terminada: 'var(--success)',
  fallida: 'var(--danger)',
  en_proceso: 'var(--warning)',
  solicitada: 'var(--warning)',
};

function rango(s: SolicitudSat): string {
  const a = s.fecha_inicial.slice(0, 10);
  const b = s.fecha_final.slice(0, 10);
  return a === b ? a : `${a} → ${b}`;
}

interface Props {
  solicitudes: SolicitudSat[];
  total: number;
  pagina: number;
  porPagina: number;
  onPagina: (p: number) => void;
}

export default function ListaSolicitudesSat({ solicitudes, total, pagina, porPagina, onPagina }: Props) {
  if (total === 0) {
    return (
      <div className="card" style={{ padding: 'var(--space-lg)', color: 'var(--text-secondary)', textAlign: 'center' }}>
        Todavía no hay solicitudes al SAT para este cliente.
      </div>
    );
  }
  const paginas = Math.max(1, Math.ceil(total / porPagina));
  return (
    <div style={{ display: 'grid', gap: 'var(--space-xs)' }}>
      <div style={envoltura}>
        <table style={tabla(720)}>
          <thead>
            <tr>
              <th style={th}>Rango</th>
              <th style={th}>Qué</th>
              <th style={th}>Estado</th>
              <th style={th}>Resultado</th>
              <th style={th}>Mensaje del SAT</th>
            </tr>
          </thead>
          <tbody>
            {solicitudes.map((s) => (
              <tr key={s.id}>
                <td style={td}>{rango(s)}</td>
                <td style={td}>{s.direccion === 'emitidos' ? 'Emitidos' : 'Recibidos'} · {s.tipo === 'cfdi' ? 'XML' : 'Metadata'}</td>
                <td style={{ ...td, color: COLOR[s.estado] ?? 'var(--text-secondary)' }}>{ETIQUETA_SOLICITUD[s.estado]}</td>
                <td style={td}>
                  {s.tipo === 'cfdi'
                    ? `${s.xml_importados} nuevos · ${s.duplicados} ya estaban`
                    : `${s.metadata_registros} registros`}
                </td>
                <td style={{ ...td, fontSize: '0.8rem', color: 'var(--text-secondary)' }}>{s.mensaje}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {paginas > 1 && (
        <div style={{ display: 'flex', gap: 'var(--space-xs)', alignItems: 'center' }}>
          <button type="button" className="btn-secondary" disabled={pagina <= 1} onClick={() => onPagina(pagina - 1)}>Anterior</button>
          <span style={{ fontSize: '0.85rem' }}>Página {pagina} de {paginas}</span>
          <button type="button" className="btn-secondary" disabled={pagina >= paginas} onClick={() => onPagina(pagina + 1)}>Siguiente</button>
        </div>
      )}
    </div>
  );
}
