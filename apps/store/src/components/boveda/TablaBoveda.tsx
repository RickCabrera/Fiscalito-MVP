/**
 * Tabla paginada de la bóveda (P0-03). Una fila por CFDI con su contraparte
 * —el receptor de lo emitido, el emisor de lo recibido— y la descarga del XML
 * original, que el backend devuelve byte por byte.
 */

import { Download } from 'lucide-react';
import type { ComprobanteBoveda } from '../../services/bovedaApi';
import { fmtMoney } from '../../utils/format';
import { tdMonoStyle, tdStyle, thStyle } from '../../utils/styles';
import { CeldaArt69b, CeldaEstatusSat } from './MarcasSat';

const NOMBRE_TIPO: Record<string, string> = {
  I: 'Ingreso', E: 'Egreso', P: 'Pago', N: 'Nómina', T: 'Traslado',
};

interface Props {
  filas: ComprobanteBoveda[];
  total: number;
  pagina: number;
  porPagina: number;
  descargando: string | null;
  onPagina: (p: number) => void;
  onDescargar: (uuid: string) => void;
}

export default function TablaBoveda({
  filas, total, pagina, porPagina, descargando, onPagina, onDescargar,
}: Props) {
  const paginas = Math.max(1, Math.ceil(total / porPagina));
  return (
    <div className="card" style={{ padding: 0, overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
        <thead>
          <tr style={{ borderBottom: '1px solid var(--border)' }}>
            <th style={thStyle}>Fecha</th>
            <th style={thStyle}>Tipo</th>
            <th style={thStyle}>Dirección</th>
            <th style={thStyle}>Contraparte</th>
            <th style={thStyle}>Serie/Folio</th>
            <th style={{ ...thStyle, textAlign: 'right' }}>Total</th>
            <th style={thStyle}>Estatus SAT</th>
            <th style={thStyle}>Art. 69-B</th>
            <th style={thStyle}>XML</th>
          </tr>
        </thead>
        <tbody>
          {filas.map((c) => {
            const emitido = c.direccion === 'emitido';
            return (
              <tr key={c.uuid} style={{ borderBottom: '1px solid var(--border)' }}>
                <td style={tdStyle}>{c.fecha.slice(0, 10)}</td>
                <td style={tdStyle}>{NOMBRE_TIPO[c.tipo] ?? c.tipo}</td>
                <td style={tdStyle}>{emitido ? 'Emitido' : 'Recibido'}</td>
                <td style={tdStyle}>
                  <div style={{ color: 'var(--text-primary)' }}>{emitido ? c.nombre_receptor : c.nombre_emisor}</div>
                  <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '0.75rem' }}>
                    {emitido ? c.rfc_receptor : c.rfc_emisor}
                  </div>
                </td>
                <td style={tdStyle}>{[c.serie, c.folio].filter(Boolean).join('-') || '—'}</td>
                <td style={tdMonoStyle}>{fmtMoney(Number(c.total))} {c.moneda !== 'MXN' ? c.moneda : ''}</td>
                <td style={tdStyle}><CeldaEstatusSat c={c} /></td>
                <td style={tdStyle}><CeldaArt69b c={c} /></td>
                <td style={tdStyle}>
                  <button
                    type="button"
                    className="btn-secondary"
                    aria-label={`Descargar XML ${c.uuid}`}
                    title={c.uuid}
                    disabled={descargando === c.uuid}
                    onClick={() => onDescargar(c.uuid)}
                    style={{ padding: '4px 10px' }}
                  >
                    <Download size={14} />
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <nav aria-label="Paginación" style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        padding: 'var(--space-sm) var(--space-md)', fontSize: '0.83rem', color: 'var(--text-secondary)',
      }}>
        <span>{total} comprobante{total === 1 ? '' : 's'} · página {pagina} de {paginas}</span>
        <span style={{ display: 'flex', gap: 'var(--space-sm)' }}>
          <button type="button" className="btn-secondary" disabled={pagina <= 1}
            onClick={() => onPagina(pagina - 1)}>Anterior</button>
          <button type="button" className="btn-secondary" disabled={pagina >= paginas}
            onClick={() => onPagina(pagina + 1)}>Siguiente</button>
        </span>
      </nav>
    </div>
  );
}
