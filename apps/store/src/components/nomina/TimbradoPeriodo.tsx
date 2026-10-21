/**
 * Timbrado del CFDI de nómina de un periodo cerrado (P4-11).
 *
 * "Timbrar" encola el trabajo en el backend (sella con el CSD del cliente, valida contra el XSD
 * y timbra con el PAC de `FISCALITO_PAC`); la pantalla consulta el estado por recibo cada pocos
 * segundos mientras haya pendientes. Descarga XML/PDF por recibo y el ZIP de todos; cancela con
 * motivo del SAT. Con el PAC falso dice que los comprobantes NO son fiscales.
 */

import { useCallback, useEffect, useState } from 'react';
import { Download, FileCode, FileText, Loader, Stamp, XCircle } from 'lucide-react';
import {
  cancelarCfdi, descargarCfdi, descargarZip, estadoTimbrado, timbrarPeriodo,
  type CfdiRecibo, type EstadoTimbrado,
} from '../../services/nominaImssApi';
import { descargarBlob, dinero } from '../contabilidad/comun';
import { tdStyle, thStyle } from '../../utils/styles';
import ErrorAlert from '../common/ErrorAlert';

const ESTADO: Record<CfdiRecibo['estado'], string> = {
  pendiente: 'Pendiente', timbrado: 'Timbrado', error: 'Error', reintento: 'Reintentando',
  cancelado: 'Cancelado', cancelacion_en_proceso: 'Cancelación en proceso',
};
const MOTIVOS: [string, string][] = [
  ['02', '02 · Con errores sin relación'], ['01', '01 · Con errores con relación'],
  ['03', '03 · No se llevó a cabo la operación'], ['04', '04 · Operación nominativa en factura global'],
];
const INTERVALO_MS = 3000;

interface Props {
  clienteId: string;
  periodoId: number;
  onCambio?: () => void;
}

export default function TimbradoPeriodo({ clienteId, periodoId, onCambio }: Props) {
  const [estado, setEstado] = useState<EstadoTimbrado | null>(null);
  const [error, setError] = useState('');
  const [ocupado, setOcupado] = useState('');
  const [motivo, setMotivo] = useState('02');
  const [sustituto, setSustituto] = useState('');

  const cargar = useCallback(() => {
    estadoTimbrado(clienteId, periodoId)
      .then((r) => { setEstado(r); setError(''); })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : 'No se pudo consultar.'));
  }, [clienteId, periodoId]);

  useEffect(() => { cargar(); }, [cargar]);

  const enCurso = !!estado && (estado.recibos.some((r) => r.estado === 'pendiente' || r.estado === 'reintento')
    || estado.trabajo?.estado === 'pendiente' || estado.trabajo?.estado === 'corriendo');
  useEffect(() => {
    if (!enCurso) return undefined;
    const t = setInterval(cargar, INTERVALO_MS);
    return () => clearInterval(t);
  }, [enCurso, cargar]);

  const accion = async (llave: string, fn: () => Promise<unknown>) => {
    setOcupado(llave);
    setError('');
    try {
      await fn();
      cargar();
      onCambio?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo completar.');
    } finally {
      setOcupado('');
    }
  };

  const bajar = (c: CfdiRecibo, tipo: 'xml' | 'pdf') => accion(`${c.id}-${tipo}`, async () => {
    descargarBlob(`nomina-${c.empleado_no}-${c.uuid}.${tipo}`, await descargarCfdi(clienteId, periodoId, c.id, tipo));
  });

  const cancelar = (c: CfdiRecibo) => {
    if (!window.confirm(`¿Cancelar el CFDI de ${c.empleado_no} con motivo ${motivo}?`)) return;
    void accion(`${c.id}-cancelar`, () => cancelarCfdi(clienteId, periodoId, c.id, motivo, sustituto));
  };

  const timbrados = estado?.recibos.filter((r) => r.estado === 'timbrado').length ?? 0;
  const prueba = estado?.recibos.some((r) => r.es_prueba);
  return (
    <section className="card" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
      <h3 style={{ fontSize: '0.95rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 8, margin: 0 }}>
        <Stamp size={16} /> CFDI de nómina
        {estado && <span style={{ fontWeight: 400, color: 'var(--text-secondary)' }}>· periodo {estado.estado_periodo}</span>}
      </h3>
      {prueba && (
        <p role="note" style={{ margin: 0, fontSize: '0.8rem', color: 'var(--danger)' }}>
          El PAC configurado es el de PRUEBAS: estos comprobantes NO tienen validez fiscal.
        </p>
      )}
      {error && <ErrorAlert message={error} />}
      <div style={{ display: 'flex', gap: 'var(--space-xs)', flexWrap: 'wrap', alignItems: 'center' }}>
        <button className="btn-primary" disabled={!!ocupado || enCurso} onClick={() => accion('timbrar', () => timbrarPeriodo(clienteId, periodoId))}>
          {enCurso ? <Loader size={14} className="spin" /> : <Stamp size={14} />} {enCurso ? 'Timbrando…' : 'Timbrar'}
        </button>
        <button
          className="btn-secondary"
          disabled={!!ocupado || timbrados === 0}
          onClick={() => accion('zip', async () => descargarBlob(`nomina-${periodoId}.zip`, await descargarZip(clienteId, periodoId)))}
        >
          <Download size={14} /> ZIP de todos
        </button>
        <select aria-label="Motivo de cancelación" value={motivo} onChange={(e) => setMotivo(e.target.value)}>
          {MOTIVOS.map(([v, t]) => <option key={v} value={v}>{t}</option>)}
        </select>
        {motivo === '01' && (
          <input aria-label="UUID que sustituye" placeholder="UUID que sustituye" value={sustituto} onChange={(e) => setSustituto(e.target.value)} />
        )}
      </div>
      {estado?.trabajo?.error && (
        <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--warning)' }}>{estado.trabajo.error}</p>
      )}
      {estado && estado.recibos.length === 0 && (
        <p style={{ margin: 0, color: 'var(--text-muted)' }}>Aún no se ha pedido el timbrado de este periodo.</p>
      )}
      {estado && estado.recibos.length > 0 && (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 680 }}>
            <thead>
              <tr>
                <th style={thStyle}>Empleado</th><th style={thStyle}>Estado</th><th style={thStyle}>UUID</th>
                <th style={thStyle}>Neto</th><th style={thStyle}>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {estado.recibos.map((c) => (
                <tr key={c.id}>
                  <td style={tdStyle}>{c.empleado_no} {c.nombre}</td>
                  <td style={tdStyle} title={c.error}>
                    {ESTADO[c.estado]}{c.error ? ` — ${c.error}` : ''}
                  </td>
                  <td style={{ ...tdStyle, fontFamily: 'var(--font-mono)', fontSize: '0.75rem' }}>{c.uuid ?? '—'}</td>
                  <td style={tdStyle}>{dinero(c.total)}</td>
                  <td style={{ ...tdStyle, display: 'flex', gap: 4 }}>
                    {c.estado === 'timbrado' && (
                      <>
                        <button className="btn-secondary" aria-label={`XML de ${c.empleado_no}`} onClick={() => bajar(c, 'xml')}><FileCode size={14} /></button>
                        <button className="btn-secondary" aria-label={`PDF de ${c.empleado_no}`} onClick={() => bajar(c, 'pdf')}><FileText size={14} /></button>
                        <button className="btn-secondary" aria-label={`Cancelar ${c.empleado_no}`} onClick={() => cancelar(c)}><XCircle size={14} /></button>
                      </>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
