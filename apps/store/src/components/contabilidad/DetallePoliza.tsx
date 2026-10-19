/**
 * Detalle de una póliza (P2-03): sus movimientos, totales, advertencias del
 * generador (diferencia contra el total del CFDI, pagos sin factura en la
 * bóveda…), descarga del XML del CFDI de origen y cancelación con motivo.
 */

import { useEffect, useState } from 'react';
import { Ban, Download, Loader, X } from 'lucide-react';
import { cancelarPoliza, obtenerPoliza, type Poliza } from '../../services/contabilidadApi';
import { descargarXml } from '../../services/bovedaApi';
import ErrorAlert from '../common/ErrorAlert';
import { ETIQUETA_TIPO_POLIZA, descargarBlob, dinero, mensaje } from './comun';
import { tdMonoStyle, tdStyle, thStyle } from '../../utils/styles';

interface Props {
  clave: string;
  polizaId: number;
  onCerrar: () => void;
  onCambio: () => void;
}

export default function DetallePoliza({ clave, polizaId, onCerrar, onCambio }: Props) {
  const [carga, setCarga] = useState<{ id: number; poliza: Poliza } | null>(null);
  const poliza = carga?.id === polizaId ? carga.poliza : null;
  const setPoliza = (p: Poliza) => setCarga({ id: polizaId, poliza: p });
  const [error, setError] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);

  useEffect(() => {
    let vivo = true;
    obtenerPoliza(clave, polizaId)
      .then((r) => { if (vivo) setCarga({ id: polizaId, poliza: r.poliza }); })
      .catch((e: unknown) => { if (vivo) setError(mensaje(e, 'No se pudo abrir la póliza.')); });
    return () => { vivo = false; };
  }, [clave, polizaId]);

  async function xml(uuid: string) {
    setError(null);
    try {
      descargarBlob(`${uuid}.xml`, await descargarXml(clave, uuid));
    } catch (e) {
      setError(mensaje(e, 'No se pudo descargar el XML.'));
    }
  }

  async function cancelar() {
    const motivo = window.prompt('Motivo de la cancelación');
    if (motivo === null) return;
    setOcupado(true);
    setError(null);
    try {
      const r = await cancelarPoliza(clave, polizaId, motivo);
      setPoliza({ ...r.poliza, movimientos: poliza?.movimientos });
      onCambio();
    } catch (e) {
      setError(mensaje(e, 'No se pudo cancelar la póliza.'));
    } finally {
      setOcupado(false);
    }
  }

  return (
    <section className="card" aria-label="Detalle de la póliza" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)', borderColor: 'var(--border-active)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)' }}>
        <strong style={{ flex: 1 }}>
          {poliza ? `Póliza ${poliza.folio} · ${ETIQUETA_TIPO_POLIZA[poliza.tipo]} · ${poliza.fecha}` : 'Póliza'}
        </strong>
        {poliza?.uuid_cfdi && (
          <button type="button" className="btn-secondary" onClick={() => void xml(poliza.uuid_cfdi!)}>
            <Download size={14} /> XML
          </button>
        )}
        {poliza?.estado === 'activa' && (
          <button type="button" className="btn-secondary" disabled={ocupado} onClick={() => void cancelar()}>
            <Ban size={14} /> Cancelar póliza
          </button>
        )}
        <button type="button" className="btn-secondary" aria-label="Cerrar detalle" onClick={onCerrar}><X size={14} /></button>
      </div>
      {error && <ErrorAlert message={error} />}
      {!poliza ? (!error && <div><Loader size={16} className="spin" /> Cargando…</div>) : (
        <>
          <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
            {poliza.concepto}
            {poliza.estado === 'cancelada' && (
              <div style={{ color: 'var(--danger)' }}>Cancelada: {poliza.motivo_cancelacion}</div>
            )}
            {poliza.advertencias.map((a) => <div key={a} style={{ color: 'var(--warning)' }}>{a}</div>)}
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.84rem' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border)' }}>
                  <th style={thStyle}>Cuenta</th><th style={thStyle}>Concepto</th>
                  <th style={thStyle}>RFC</th><th style={{ ...thStyle, textAlign: 'right' }}>Cargo</th>
                  <th style={{ ...thStyle, textAlign: 'right' }}>Abono</th>
                </tr>
              </thead>
              <tbody>
                {(poliza.movimientos ?? []).map((m, i) => (
                  <tr key={m.id ?? i} style={{ borderBottom: '1px solid var(--border)' }}>
                    <td style={tdStyle}>
                      <span style={{ fontFamily: "'JetBrains Mono', monospace" }}>{m.cuenta}</span> {m.nombre_cuenta}
                    </td>
                    <td style={tdStyle}>{m.concepto}</td>
                    <td style={{ ...tdStyle, fontFamily: "'JetBrains Mono', monospace", fontSize: '0.75rem' }}>{m.rfc}</td>
                    <td style={tdMonoStyle}>{dinero(m.cargo, '')}</td>
                    <td style={tdMonoStyle}>{dinero(m.abono, '')}</td>
                  </tr>
                ))}
                <tr>
                  <td style={{ ...tdStyle, fontWeight: 600 }} colSpan={3}>
                    Totales {poliza.total_cargos === poliza.total_abonos ? '· cuadra' : '· NO CUADRA'}
                  </td>
                  <td style={{ ...tdMonoStyle, fontWeight: 600 }}>{dinero(poliza.total_cargos)}</td>
                  <td style={{ ...tdMonoStyle, fontWeight: 600 }}>{dinero(poliza.total_abonos)}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}
