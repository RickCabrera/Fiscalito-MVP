/**
 * Estado de cuenta de UN cliente (P5-03): saldo y antigüedad, movimientos con saldo corrido,
 * honorarios, cargos y pagos, recordatorios por correo/WhatsApp y descarga PDF/Excel.
 */

import { useCallback, useEffect, useState } from 'react';
import { Download, Loader, Receipt, Send, X } from 'lucide-react';
import {
  borrarPago, cancelarCargo, detalleCobranza, enviarRecordatorio, estadoDeCuenta,
  guardarHonorarios, NOMBRE_TRAMO, nuevoCargo, nuevoPago, pesos,
  type DetalleCobranza, type Tramo,
} from '../../services/cobranzaApi';
import { facturarCargo } from '../../services/facturacionApi';
import FormHonorarios from './FormHonorarios';
import FormMovimiento, { type DatosMovimiento } from './FormMovimiento';
import ErrorAlert from '../common/ErrorAlert';

interface Props {
  clave: string;
  onCambio: () => void;
}

function bajar(blob: Blob, nombre: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = nombre;
  a.click();
  URL.revokeObjectURL(url);
}

export default function DetalleCliente({ clave, onCambio }: Props) {
  const [d, setD] = useState<DetalleCobranza | null>(null);
  const [error, setError] = useState('');
  const [aviso, setAviso] = useState('');
  const [ocupado, setOcupado] = useState(false);

  const cargar = useCallback(() => {
    detalleCobranza(clave).then(setD)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : 'No se pudo cargar el estado de cuenta.'));
  }, [clave]);
  useEffect(() => { cargar(); }, [cargar]);

  const hacer = async (fn: () => Promise<unknown>, ok = ''): Promise<boolean> => {
    setOcupado(true);
    setError('');
    setAviso('');
    try {
      await fn();
      if (ok) setAviso(ok);
      cargar();
      onCambio();
      return true;
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo guardar.');
      return false;
    } finally {
      setOcupado(false);
    }
  };

  if (!d) {
    return error ? <ErrorAlert message={error} /> : (
      <span style={{ display: 'flex', gap: 8, alignItems: 'center' }}><Loader size={16} className="spin" /> Cargando…</span>
    );
  }
  const hoy = d.hoy;
  const guardarCargo = (m: DatosMovimiento) => hacer(() => nuevoCargo(clave, {
    concepto: m.texto, importe: m.importe, fecha: m.fecha, facturar: m.facturar }), 'Cargo agregado.');
  const guardarPago = (m: DatosMovimiento) => hacer(() => nuevoPago(clave, {
    fecha: m.fecha, importe: m.importe, forma_pago: m.texto, referencia: '',
    cfdi_uuid: m.extra.trim() || null }), 'Pago registrado.');
  const recordar = (canal: 'correo' | 'whatsapp') => void hacer(async () => {
    const r = await enviarRecordatorio(clave, canal);
    setAviso(r.recordatorio.estado === 'enviado' ? `Recordatorio enviado por ${canal}.`
      : `Recordatorio ${r.recordatorio.estado}: ${r.recordatorio.error}`);
  });
  const descargar = (formato: 'pdf' | 'xlsx') => void hacer(async () =>
    bajar(await estadoDeCuenta(clave, formato), `estado-cuenta-${clave}.${formato}`));

  return (
    <section aria-label={`Estado de cuenta de ${d.cliente_nombre}`} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', alignItems: 'baseline' }}>
        <h2 style={{ fontSize: '1.05rem', flex: 1 }}>{d.cliente_nombre || d.cliente}</h2>
        <span>Saldo <b>{pesos(d.saldo)}</b></span>
        <span style={{ color: Number(d.vencido) > 0 ? 'var(--danger)' : 'var(--text-secondary)' }}>
          Vencido {pesos(d.vencido)}{d.vencido_desde && ` desde ${d.vencido_desde}`}
        </span>
        {d.desde && <span style={{ color: 'var(--text-secondary)' }}>Debe desde {d.desde}</span>}
      </div>
      <div style={{ display: 'flex', gap: 16, fontSize: '0.82rem', flexWrap: 'wrap' }}>
        {(Object.keys(NOMBRE_TRAMO) as Tramo[]).map((t) => (
          <span key={t}>{NOMBRE_TRAMO[t]}: <b>{pesos(d.antiguedad[t])}</b></span>
        ))}
      </div>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <button className="btn-secondary" disabled={ocupado} onClick={() => descargar('pdf')}><Download size={14} /> PDF</button>
        <button className="btn-secondary" disabled={ocupado} onClick={() => descargar('xlsx')}><Download size={14} /> Excel</button>
        <button className="btn-secondary" disabled={ocupado} onClick={() => recordar('correo')}><Send size={14} /> Recordar por correo</button>
        <button className="btn-secondary" disabled={ocupado} onClick={() => recordar('whatsapp')}><Send size={14} /> Recordar por WhatsApp</button>
      </div>
      {error && <ErrorAlert message={error} />}
      {aviso && <p role="status" style={{ color: 'var(--success)', fontSize: '0.85rem' }}>{aviso}</p>}

      <details className="card">
        <summary style={{ cursor: 'pointer', fontWeight: 600 }}>Honorarios (iguala mensual)</summary>
        <div style={{ marginTop: 10 }}>
          <FormHonorarios key={JSON.stringify(d.honorarios)} inicial={d.honorarios} ocupado={ocupado}
            onGuardar={(h) => void hacer(() => guardarHonorarios(clave, h), 'Honorarios guardados.')} />
        </div>
      </details>
      <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        <FormMovimiento tipo="cargo" hoy={hoy} ocupado={ocupado} onGuardar={guardarCargo} />
        <FormMovimiento tipo="pago" hoy={hoy} ocupado={ocupado} onGuardar={guardarPago} />
      </div>

      <table style={{ width: '100%', fontSize: '0.82rem', borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ textAlign: 'left', color: 'var(--text-secondary)' }}>
            <th>Fecha</th><th>Concepto</th><th>Vence</th><th>Cargo</th><th>Abono</th><th>Saldo</th><th />
          </tr>
        </thead>
        <tbody>
          {d.movimientos.length === 0 && (
            <tr><td colSpan={7} style={{ color: 'var(--text-muted)', padding: 8 }}>Sin movimientos.</td></tr>
          )}
          {d.movimientos.map((m) => (
            <tr key={`${m.tipo}-${m.id}`} style={{ borderTop: '1px solid var(--border)' }}>
              <td>{m.fecha}</td>
              <td>{m.concepto}{m.uuid && <span style={{ color: 'var(--text-muted)' }}> · CFDI {m.uuid.slice(0, 8)}</span>}</td>
              <td>{m.vencimiento ?? ''}</td>
              <td>{Number(m.cargo) ? pesos(m.cargo) : ''}</td>
              <td>{Number(m.abono) ? pesos(m.abono) : ''}</td>
              <td>{pesos(m.saldo)}</td>
              <td style={{ display: 'flex', gap: 4 }}>
                {m.tipo === 'cargo' && !m.uuid && (
                  // P5-04: CFDI de los honorarios, emitido desde el cliente marcado como el despacho.
                  <button className="btn-secondary" style={{ padding: '2px 6px' }} disabled={ocupado}
                    aria-label={`Facturar ${m.concepto}`}
                    onClick={() => void hacer(() => facturarCargo(m.id), 'Cargo facturado (CFDI timbrado).')}>
                    <Receipt size={12} />
                  </button>
                )}
                <button className="btn-secondary" style={{ padding: '2px 6px' }} disabled={ocupado}
                  aria-label={m.tipo === 'cargo' ? `Cancelar cargo ${m.concepto}` : `Borrar pago ${m.concepto}`}
                  onClick={() => void hacer(() => (m.tipo === 'cargo' ? cancelarCargo(clave, m.id) : borrarPago(clave, m.id)))}>
                  <X size={12} />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {d.recordatorios.length > 0 && (
        <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
          Recordatorios: {d.recordatorios.slice(0, 5).map((r) =>
            `${r.canal} ${r.estado} (${(r.enviado_en ?? r.programado_para).slice(0, 10)})`).join(' · ')}
        </div>
      )}
    </section>
  );
}
