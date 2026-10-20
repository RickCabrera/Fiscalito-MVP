/**
 * "Facturación" en la ficha del cliente (P5-04): el cliente es el EMISOR.
 *
 * Lista sus CFDI emitidos (ingreso, egreso, pago), descarga XML y PDF con QR, cancela con
 * motivo 01-04 y emite nuevos (FormFactura / FormPago). El backend calcula, sella con el CSD del
 * cliente, valida contra el XSD y timbra con el PAC de `FISCALITO_PAC`. Un cliente puede
 * marcarse como "el propio despacho": desde él se facturan los honorarios de la cartera.
 */

import { useCallback, useEffect, useState } from 'react';
import { FileCode, FileText, Loader, Receipt, XCircle } from 'lucide-react';
import {
  cancelarFactura, catalogosFacturacion, configFacturacion, descargarFactura, emitirFactura,
  emitirPago, guardarConfigFacturacion, listarFacturas,
  type Catalogos, type Factura, type FacturaCaptura, type PagoCaptura,
} from '../../services/facturacionApi';
import { pesos } from '../../services/cobranzaApi';
import { descargarBlob } from '../contabilidad/comun';
import { tdStyle, thStyle } from '../../utils/styles';
import ErrorAlert from '../common/ErrorAlert';
import FormFactura from './FormFactura';
import FormPago from './FormPago';

interface Props {
  clave: string;
  /** Otros clientes del despacho (posibles receptores). */
  receptores: { id: string; nombre: string }[];
}

const TIPO: Record<Factura['tipo'], string> = { I: 'Ingreso', E: 'Egreso', P: 'Pago' };
const ESTADO: Record<Factura['estado'], string> = {
  timbrado: 'Vigente', cancelacion_en_proceso: 'Cancelación en proceso', cancelado: 'Cancelada',
};
type Panel = '' | 'factura' | 'pago';

export default function FacturacionCliente({ clave, receptores }: Props) {
  const [facturas, setFacturas] = useState<Factura[] | null>(null);
  const [catalogos, setCatalogos] = useState<Catalogos | null>(null);
  const [propio, setPropio] = useState<string | null>(null);
  const [panel, setPanel] = useState<Panel>('');
  const [motivo, setMotivo] = useState('02');
  const [sustituto, setSustituto] = useState('');
  const [error, setError] = useState('');
  const [aviso, setAviso] = useState('');
  const [ocupado, setOcupado] = useState(false);

  const cargar = useCallback(() => {
    listarFacturas(clave).then((r) => setFacturas(r.facturas))
      .catch((e: unknown) => setError(e instanceof Error ? e.message : 'No se pudieron cargar las facturas.'));
  }, [clave]);

  useEffect(() => {
    cargar();
    Promise.all([catalogosFacturacion(), configFacturacion()])
      .then(([c, p]) => { setCatalogos(c); setPropio(p); })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : 'No se pudieron cargar los catálogos.'));
  }, [cargar]);

  const hacer = async (fn: () => Promise<unknown>, ok: string) => {
    setOcupado(true);
    setError('');
    setAviso('');
    try {
      await fn();
      setAviso(ok);
      cargar();
      return true;
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo completar.');
      return false;
    } finally {
      setOcupado(false);
    }
  };

  const emitir = async (f: FacturaCaptura) => {
    if (await hacer(() => emitirFactura(clave, f), 'Factura timbrada.')) setPanel('');
  };
  const pagar = async (p: PagoCaptura) => {
    if (await hacer(() => emitirPago(clave, p), 'Pago timbrado.')) setPanel('');
  };
  const bajar = (f: Factura, formato: 'xml' | 'pdf') => void hacer(async () =>
    descargarBlob(`${f.serie}-${f.folio}_${f.uuid}.${formato}`, await descargarFactura(clave, f.id, formato)), '');
  const cancelar = (f: Factura) => {
    if (!window.confirm(`¿Cancelar ${f.serie}-${f.folio} con motivo ${motivo}?`)) return;
    void hacer(() => cancelarFactura(clave, f.id, motivo, sustituto), 'Factura cancelada.');
  };
  const esPropio = propio === clave;
  const marcarPropio = () => void hacer(async () =>
    setPropio(await guardarConfigFacturacion(esPropio ? null : clave)), '');

  const prueba = facturas?.some((f) => f.es_prueba);
  const pendientes = (facturas ?? []).filter((f) => f.tipo === 'I' && f.metodo_pago === 'PPD'
    && f.estado === 'timbrado' && Number(f.saldo ?? 0) > 0);
  return (
    <section className="card animate-in" aria-label="Facturación" style={{ marginTop: 'var(--space-lg)', padding: 'var(--space-lg)', display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
      <h3 style={{ margin: 0, fontSize: '1rem', display: 'flex', alignItems: 'center', gap: 8 }}>
        <Receipt size={16} /> Facturación (CFDI 4.0)
      </h3>
      <label style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', display: 'flex', gap: 6, alignItems: 'center' }}>
        <input type="checkbox" checked={esPropio} disabled={ocupado} onChange={marcarPropio} />
        Este cliente es el propio despacho (desde aquí se facturan los honorarios de la cartera)
      </label>
      {prueba && (
        <p role="note" style={{ margin: 0, fontSize: '0.8rem', color: 'var(--danger)' }}>
          El PAC configurado es el de PRUEBAS: estos comprobantes NO tienen validez fiscal.
        </p>
      )}
      {error && <ErrorAlert message={error} />}
      {aviso && <p role="status" style={{ margin: 0, color: 'var(--success)', fontSize: '0.85rem' }}>{aviso}</p>}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
        <button className="btn-primary" disabled={!catalogos} onClick={() => setPanel(panel === 'factura' ? '' : 'factura')}>Nueva factura</button>
        <button className="btn-secondary" disabled={!catalogos} onClick={() => setPanel(panel === 'pago' ? '' : 'pago')}>Registrar pago (REP)</button>
        <select aria-label="Motivo de cancelación" value={motivo} onChange={(e) => setMotivo(e.target.value)}>
          {(catalogos?.motivo_cancelacion ?? []).map((m) => <option key={m.clave} value={m.clave}>{m.clave} · {m.descripcion}</option>)}
        </select>
        {motivo === '01' && (
          <input aria-label="UUID que sustituye" placeholder="UUID de la factura que la sustituye" value={sustituto} onChange={(e) => setSustituto(e.target.value)} />
        )}
      </div>
      {catalogos && panel === 'factura' && (
        <FormFactura catalogos={catalogos} receptores={receptores} ocupado={ocupado} onEmitir={(f) => void emitir(f)} />
      )}
      {catalogos && panel === 'pago' && (
        <FormPago catalogos={catalogos} pendientes={pendientes} ocupado={ocupado} onEmitir={(p) => void pagar(p)} />
      )}
      {facturas === null && !error && (
        <span style={{ display: 'flex', gap: 8, alignItems: 'center' }}><Loader size={16} className="spin" /> Cargando…</span>
      )}
      {facturas && facturas.length === 0 && (
        <p style={{ margin: 0, color: 'var(--text-muted)' }}>Este cliente aún no ha emitido facturas desde Fiscalito.</p>
      )}
      {facturas && facturas.length > 0 && (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 720 }}>
            <thead>
              <tr>
                <th style={thStyle}>Folio</th><th style={thStyle}>Tipo</th><th style={thStyle}>Receptor</th>
                <th style={thStyle}>Total</th><th style={thStyle}>Saldo</th><th style={thStyle}>Estado</th><th style={thStyle}>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {facturas.map((f) => (
                <tr key={f.id}>
                  <td style={tdStyle} title={f.uuid}>{f.serie}-{f.folio}</td>
                  <td style={tdStyle}>{TIPO[f.tipo]}{f.metodo_pago ? ` · ${f.metodo_pago}` : ''}</td>
                  <td style={tdStyle}>{f.nombre_receptor}</td>
                  <td style={tdStyle}>{pesos(f.total)}</td>
                  <td style={tdStyle}>{f.saldo !== null ? pesos(f.saldo) : '—'}</td>
                  <td style={tdStyle}>{ESTADO[f.estado]}{f.motivo_cancelacion ? ` (${f.motivo_cancelacion})` : ''}</td>
                  <td style={{ ...tdStyle, display: 'flex', gap: 4 }}>
                    <button className="btn-secondary" aria-label={`XML de ${f.serie}-${f.folio}`} onClick={() => bajar(f, 'xml')}><FileCode size={14} /></button>
                    <button className="btn-secondary" aria-label={`PDF de ${f.serie}-${f.folio}`} onClick={() => bajar(f, 'pdf')}><FileText size={14} /></button>
                    {f.estado === 'timbrado' && (
                      <button className="btn-secondary" aria-label={`Cancelar ${f.serie}-${f.folio}`} disabled={ocupado} onClick={() => cancelar(f)}><XCircle size={14} /></button>
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
