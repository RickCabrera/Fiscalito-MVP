/**
 * Tab Buzón de Contabilito (P2-07): contabilidad electrónica del Anexo 24.
 *
 * Se elige periodo y documento, se genera y valida contra el XSD oficial (el
 * backend devuelve los errores tal cual) y se descarga el ZIP con el nombre que
 * pide el SAT. El ENVÍO no tiene API: la pantalla dice cómo subirlo al portal y
 * no hay un botón que prometa enviarlo. El sello con la e.firma es opcional.
 */

import { useEffect, useState } from 'react';
import { CheckCircle2, Download, FileCheck2, Loader, XCircle } from 'lucide-react';
import {
  descargarZipAnexo24, obtenerDocumentos, validarAnexo24,
  type InfoDocumentos, type ResultadoValidacion, type SolicitudAnexo24,
} from '../../services/contabilidadElectronicaApi';
import ErrorAlert from '../common/ErrorAlert';
import { descargarBlob, mensaje } from './comun';
import { labelStyle } from '../../utils/styles';

interface Props { clave: string }

function inicial(): SolicitudAnexo24 {
  const hoy = new Date();
  const previo = new Date(hoy.getFullYear(), hoy.getMonth() - 1, 1);
  return {
    documento: 'balanza', anio: previo.getFullYear(), mes: previo.getMonth() + 1, tipo_envio: 'N',
    fecha_mod_bal: null, tipo_solicitud: '', num_orden: '', num_tramite: '', sellar: false,
  };
}

export default function BuzonTab({ clave }: Props) {
  const [info, setInfo] = useState<InfoDocumentos | null>(null);
  const [s, setS] = useState<SolicitudAnexo24>(inicial);
  const [resultado, setResultado] = useState<ResultadoValidacion | null>(null);
  const [ocupado, setOcupado] = useState<'validar' | 'zip' | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let vivo = true;
    obtenerDocumentos()
      .then((r) => { if (vivo) setInfo(r); })
      .catch((e: unknown) => { if (vivo) setError(mensaje(e, 'No se pudo cargar la lista de documentos.')); });
    return () => { vivo = false; };
  }, []);

  const aSolicitud = info?.documentos.find((d) => d.clave === s.documento)?.a_solicitud ?? false;
  const cambiar = (c: Partial<SolicitudAnexo24>) => { setS({ ...s, ...c }); setResultado(null); };

  const validar = async () => {
    setOcupado('validar'); setError(null);
    try { setResultado(await validarAnexo24(clave, s)); }
    catch (e) { setError(mensaje(e, 'No se pudo generar el XML.')); }
    finally { setOcupado(null); }
  };

  const descargar = async () => {
    if (!resultado) return;
    setOcupado('zip'); setError(null);
    try { descargarBlob(`${resultado.nombre}.zip`, await descargarZipAnexo24(clave, s)); }
    catch (e) { setError(mensaje(e, 'No se pudo descargar el ZIP.')); }
    finally { setOcupado(null); }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
      <div className="card" style={{ display: 'flex', gap: 'var(--space-md)', flexWrap: 'wrap', alignItems: 'flex-end' }}>
        <label><span style={labelStyle}>Documento</span>
          <select className="input-field" aria-label="Documento" value={s.documento}
            onChange={(e) => cambiar({ documento: e.target.value as SolicitudAnexo24['documento'] })}>
            {(info?.documentos ?? []).map((d) => <option key={d.clave} value={d.clave}>{d.nombre}</option>)}
          </select></label>
        <label><span style={labelStyle}>Periodo</span>
          <input className="input-field" type="month" aria-label="Periodo"
            value={`${s.anio}-${String(s.mes).padStart(2, '0')}`}
            onChange={(e) => { const [a, m] = e.target.value.split('-').map(Number); if (a && m) cambiar({ anio: a, mes: m }); }} /></label>
        {s.documento === 'balanza' && (
          <label><span style={labelStyle}>Envío</span>
            <select className="input-field" value={s.tipo_envio} onChange={(e) => cambiar({ tipo_envio: e.target.value as 'N' | 'C' })}>
              <option value="N">Normal</option><option value="C">Complementaria</option>
            </select></label>
        )}
        {s.documento === 'balanza' && s.tipo_envio === 'C' && (
          <label><span style={labelStyle}>Fecha de modificación</span>
            <input className="input-field" type="date" value={s.fecha_mod_bal ?? ''}
              onChange={(e) => cambiar({ fecha_mod_bal: e.target.value || null })} /></label>
        )}
        {aSolicitud && (
          <>
            <label><span style={labelStyle}>Tipo de solicitud</span>
              <select className="input-field" aria-label="Tipo de solicitud" value={s.tipo_solicitud}
                onChange={(e) => cambiar({ tipo_solicitud: e.target.value as SolicitudAnexo24['tipo_solicitud'] })}>
                <option value="">Elige…</option>
                <option value="AF">AF · Acto de fiscalización</option>
                <option value="FC">FC · Fiscalización compulsa</option>
                <option value="DE">DE · Devolución</option>
                <option value="CO">CO · Compensación</option>
              </select></label>
            {(s.tipo_solicitud === 'AF' || s.tipo_solicitud === 'FC') && (
              <label><span style={labelStyle}>Número de orden</span>
                <input className="input-field" placeholder="ABC1234567/26" value={s.num_orden}
                  onChange={(e) => cambiar({ num_orden: e.target.value.toUpperCase() })} /></label>
            )}
            {(s.tipo_solicitud === 'DE' || s.tipo_solicitud === 'CO') && (
              <label><span style={labelStyle}>Número de trámite</span>
                <input className="input-field" placeholder="AB123456789012" value={s.num_tramite}
                  onChange={(e) => cambiar({ num_tramite: e.target.value.toUpperCase() })} /></label>
            )}
          </>
        )}
        <label style={{ display: 'flex', gap: 6, alignItems: 'center', fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
          <input type="checkbox" checked={s.sellar} onChange={(e) => cambiar({ sellar: e.target.checked })} />
          Sellar con la e.firma
        </label>
        <button type="button" className="btn-primary" onClick={validar} disabled={ocupado !== null}>
          {ocupado === 'validar' ? <Loader size={14} className="spin" /> : <FileCheck2 size={14} />} Generar y validar
        </button>
      </div>

      {error && <ErrorAlert message={error} />}

      {resultado && (
        <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div role="status" style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: '0.9rem',
            color: resultado.valido ? 'var(--success)' : 'var(--danger)' }}>
            {resultado.valido ? <CheckCircle2 size={16} /> : <XCircle size={16} />}
            <span style={{ fontFamily: "'JetBrains Mono', monospace" }}>{resultado.nombre}.xml</span>
            {resultado.valido ? 'valida contra el XSD oficial' : `NO valida (${resultado.errores.length} errores)`}
            {resultado.sellado && ' · sellado'}
          </div>
          {resultado.errores.length > 0 && (
            <ul style={{ margin: 0, paddingLeft: 18, fontSize: '0.8rem', color: 'var(--danger)' }}>
              {resultado.errores.map((e) => <li key={e}>{e}</li>)}
            </ul>
          )}
          {resultado.advertencias.map((a) => (
            <div key={a} style={{ fontSize: '0.8rem', color: 'var(--warning)' }}>{a}</div>
          ))}
          <div>
            <button type="button" className="btn-secondary" onClick={descargar}
              disabled={!resultado.valido || ocupado !== null}>
              {ocupado === 'zip' ? <Loader size={14} className="spin" /> : <Download size={14} />} Descargar ZIP
            </button>
          </div>
        </div>
      )}

      <div className="card">
        <h3 style={{ margin: '0 0 8px', fontSize: '0.95rem', fontWeight: 600 }}>Cómo se envía al SAT</h3>
        <ul style={{ margin: 0, paddingLeft: 18, fontSize: '0.82rem', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
          {(info?.instrucciones_portal ?? []).map((t) => <li key={t}>{t}</li>)}
        </ul>
      </div>
    </div>
  );
}
