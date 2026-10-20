/** Tabla de renglones de la bitácora (P0-07). Sólo pinta; la página trae los datos. */

import { envoltura, fila, tabla, td, th } from '../nomina/estilosTabla';
import type { EventoAuditoria } from '../../services/trabajosApi';

function fecha(iso: string): string {
  return new Date(iso).toLocaleString('es-MX', {
    timeZone: 'America/Mexico_City',
    day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
  });
}

/** `http.POST` lo escribe la red del middleware: se lee mejor como "POST /ruta (200)". */
function descripcion(e: EventoAuditoria): string {
  if (e.accion.startsWith('http.')) {
    const status = e.detalle.status !== undefined ? ` (${String(e.detalle.status)})` : '';
    return `${e.accion.slice(5)} ${e.entidad_id}${status}`;
  }
  return e.entidad ? `${e.entidad} ${e.entidad_id}` : e.entidad_id;
}

export default function TablaAuditoria({ eventos }: { eventos: EventoAuditoria[] }) {
  return (
    <div style={envoltura}>
      <table style={tabla(760)}>
        <thead>
          <tr>
            <th style={th}>Fecha</th>
            <th style={th}>Usuario</th>
            <th style={th}>Cliente</th>
            <th style={th}>Acción</th>
            <th style={th}>Detalle</th>
          </tr>
        </thead>
        <tbody>
          {eventos.map((e, i) => (
            <tr key={e.id} style={fila(i)}>
              <td style={{ ...td, whiteSpace: 'nowrap' }}>{fecha(e.fecha)}</td>
              <td style={{ ...td, fontFamily: "'JetBrains Mono', monospace", fontSize: '0.8rem' }}>{e.uid}</td>
              <td style={td}>{e.cliente ?? '—'}</td>
              <td style={{ ...td, fontFamily: "'JetBrains Mono', monospace", fontSize: '0.8rem' }}>{e.accion}</td>
              <td style={{ ...td, color: 'var(--text-secondary)' }}>{descripcion(e)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
