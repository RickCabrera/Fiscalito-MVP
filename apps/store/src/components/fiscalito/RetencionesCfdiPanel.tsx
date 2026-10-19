/**
 * CFDI de retenciones e información de pagos 2.0 de los terceros del periodo (P3-04).
 *
 * Reemplaza a la "constancia PDF no fiscal" como salida principal de `RetencionesTab`: por
 * cada tercero con retenciones en la bóveda del cliente, el backend arma el XML, lo sella con
 * el CSD del cliente, lo valida contra el XSD y lo timbra con el PAC configurado. Aquí se
 * genera, se descarga (XML y PDF con QR) y se cancela. La constancia simple sigue en la tabla
 * de abajo como alternativa.
 */

import { useCallback, useEffect, useState } from 'react';
import { FileCode, FileText, Loader, Stamp, XCircle } from 'lucide-react';
import {
  cancelarCfdiRetencion, descargarCfdiRetencion, emitirCfdiRetencion, obtenerTerceros,
  type CfdiRetencion, type TerceroRetencion,
} from '../../services/retencionesCfdiApi';
import { descargarBlob } from '../contabilidad/comun';
import { fmtMoney } from '../../utils/format';
import { thStyle, tdStyle, tdMonoStyle } from '../../utils/styles';
import ErrorAlert from '../common/ErrorAlert';

interface Props {
  clave: string;
  anio: number;
  mes: number;
}

const ESTADO: Record<CfdiRetencion['estado'], string> = {
  timbrado: 'Timbrado', cancelacion_en_proceso: 'Cancelación en proceso', cancelado: 'Cancelado',
};

export default function RetencionesCfdiPanel({ clave, anio, mes }: Props) {
  const periodo = { ejercicio: anio, mes_ini: mes, mes_fin: mes };
  const [terceros, setTerceros] = useState<TerceroRetencion[] | null>(null);
  const [emitidos, setEmitidos] = useState<CfdiRetencion[]>([]);
  const [error, setError] = useState('');
  const [ocupado, setOcupado] = useState('');

  const cargar = useCallback(() => {
    obtenerTerceros(clave, { ejercicio: anio, mes_ini: mes, mes_fin: mes })
      .then((r) => { setError(''); setTerceros(r.terceros); setEmitidos(r.emitidos); })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : 'No se pudo cargar.'));
  }, [clave, anio, mes]);

  useEffect(() => { cargar(); }, [cargar]);

  const accion = async (llave: string, fn: () => Promise<unknown>) => {
    setOcupado(llave);
    setError('');
    try {
      await fn();
      cargar();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo completar.');
    } finally {
      setOcupado('');
    }
  };

  const bajar = (c: CfdiRetencion, tipo: 'xml' | 'pdf') => accion(`${c.uuid}-${tipo}`, async () => {
    descargarBlob(`retenciones-${c.rfc_tercero}-${c.uuid}.${tipo}`,
      await descargarCfdiRetencion(clave, c.uuid, tipo));
  });

  const vigente = (rfc: string) => emitidos.find((c) => c.rfc_tercero === rfc && c.estado !== 'cancelado');
  const prueba = emitidos.some((c) => c.es_prueba);

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <h3 style={{ fontSize: '0.95rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 8 }}>
        <Stamp size={16} /> CFDI de retenciones (timbrado)
      </h3>
      {prueba && (
        <p role="note" style={{ fontSize: '0.8rem', color: 'var(--danger)', margin: 0 }}>
          El PAC configurado es el de PRUEBAS: estos comprobantes NO tienen validez fiscal.
        </p>
      )}
      {error && <ErrorAlert message={error} />}
      {!terceros && !error && <Loader size={16} className="spin" aria-label="Cargando terceros" />}
      {terceros && terceros.length === 0 && (
        <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', margin: 0 }}>
          La bóveda no tiene CFDI recibidos con retenciones pagados en el mes.
        </p>
      )}
      {terceros && terceros.length > 0 && (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' }}>
            <thead>
              <tr>{['Tercero', 'Operación', 'ISR', 'IVA', 'CFDI', ''].map((h) => <th key={h} style={thStyle}>{h}</th>)}</tr>
            </thead>
            <tbody>
              {terceros.map((t) => {
                const c = vigente(t.rfc);
                return (
                  <tr key={t.rfc} style={{ borderTop: '1px solid var(--border)' }}>
                    <td style={tdStyle}>{t.nombre}<br /><span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '0.72rem' }}>{t.rfc}</span></td>
                    <td style={tdMonoStyle}>{fmtMoney(Number(t.monto_operacion))}</td>
                    <td style={tdMonoStyle}>{fmtMoney(Number(t.isr_retenido))}</td>
                    <td style={tdMonoStyle}>{fmtMoney(Number(t.iva_retenido))}</td>
                    <td style={tdStyle}>{c ? `${ESTADO[c.estado]} · ${c.uuid.slice(0, 8)}` : 'Sin emitir'}</td>
                    <td style={{ ...tdStyle, textAlign: 'right', whiteSpace: 'nowrap' }}>
                      {!c && (
                        <button className="btn-primary" disabled={!!ocupado}
                          onClick={() => accion(t.rfc, () => emitirCfdiRetencion(clave, t.rfc, periodo))}
                          style={{ padding: '4px 10px', fontSize: '0.75rem' }}>
                          {ocupado === t.rfc ? 'Timbrando…' : 'Generar CFDI'}
                        </button>
                      )}
                      {c && (
                        <span style={{ display: 'inline-flex', gap: 6 }}>
                          <button className="btn-secondary" onClick={() => bajar(c, 'xml')} title="Descargar XML"
                            style={{ padding: '4px 8px' }} aria-label={`XML de ${t.rfc}`}><FileCode size={13} /></button>
                          <button className="btn-secondary" onClick={() => bajar(c, 'pdf')} title="Descargar PDF"
                            style={{ padding: '4px 8px' }} aria-label={`PDF de ${t.rfc}`}><FileText size={13} /></button>
                          <button className="btn-secondary" disabled={!!ocupado} title="Cancelar (motivo 02)"
                            aria-label={`Cancelar CFDI de ${t.rfc}`}
                            onClick={() => {
                              if (!window.confirm(`¿Cancelar ante el SAT el CFDI ${c.uuid}? (motivo 02, sin sustitución)`)) return;
                              void accion(`c-${c.uuid}`, () => cancelarCfdiRetencion(clave, c.uuid, '02'));
                            }}
                            style={{ padding: '4px 8px', color: 'var(--danger)' }}><XCircle size={13} /></button>
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
