/**
 * "Enviar documentos" en la ficha del cliente (P5-05).
 *
 * CFDI, facturas, constancias de retención, opinión de cumplimiento, declaraciones/acuses y
 * recibos de nómina, por correo y WhatsApp, a los contactos del cliente. El envío corre en
 * segundo plano en el backend (`documentos.enviar`, con reintentos): la pantalla consulta el
 * estado cada pocos segundos mientras haya pendientes y permite reenviar uno.
 */

import { useCallback, useEffect, useState } from 'react';
import { Loader, RotateCcw, Send } from 'lucide-react';
import {
  documentosEnviables, enviarDocumentos, estadoEnvios, listarContactos, reenviar,
  type Canal, type Contacto, type DocumentoEnviable, type EstadoEnvios,
} from '../../services/enviosDocumentosApi';
import { tdStyle, thStyle } from '../../utils/styles';
import ErrorAlert from '../common/ErrorAlert';
import ContactosCliente from './ContactosCliente';
import SubirExpediente from './SubirExpediente';

const INTERVALO_MS = 3000;
const ESTADO: Record<string, string> = {
  pendiente: 'Pendiente', enviado: 'Enviado', fallido: 'Falló', rebotado: 'Rebotó',
};
const llave = (d: DocumentoEnviable) => `${d.tipo}:${d.ref}`;

export default function EnviarDocumentos({ clave }: { clave: string }) {
  const [contactos, setContactos] = useState<Contacto[]>([]);
  const [docs, setDocs] = useState<DocumentoEnviable[] | null>(null);
  const [estado, setEstado] = useState<EstadoEnvios | null>(null);
  const [elegidos, setElegidos] = useState<string[]>([]);
  const [para, setPara] = useState<number[]>([]);
  const [canales, setCanales] = useState<Canal[]>(['correo']);
  const [mensaje, setMensaje] = useState('');
  const [error, setError] = useState('');
  const [aviso, setAviso] = useState('');
  const [ocupado, setOcupado] = useState(false);

  const fallo = (e: unknown, defecto: string) => setError(e instanceof Error ? e.message : defecto);
  const cargarEstado = useCallback(() => {
    estadoEnvios(clave).then(setEstado).catch((e: unknown) => fallo(e, 'No se pudo consultar los envíos.'));
  }, [clave]);
  const cargar = useCallback(() => {
    listarContactos(clave).then(setContactos).catch((e: unknown) => fallo(e, 'No se pudieron cargar los contactos.'));
    documentosEnviables(clave).then(setDocs).catch((e: unknown) => fallo(e, 'No se pudieron cargar los documentos.'));
    cargarEstado();
  }, [clave, cargarEstado]);
  useEffect(() => { cargar(); }, [cargar]);

  const enCurso = !!estado && ((estado.resumen.pendiente ?? 0) > 0
    || estado.trabajo?.estado === 'pendiente' || estado.trabajo?.estado === 'corriendo');
  useEffect(() => {
    if (!enCurso) return undefined;
    const t = setInterval(cargarEstado, INTERVALO_MS);
    return () => clearInterval(t);
  }, [enCurso, cargarEstado]);

  const alternar = <T,>(lista: T[], v: T) => (lista.includes(v) ? lista.filter((x) => x !== v) : [...lista, v]);

  const enviar = async () => {
    setOcupado(true);
    setError('');
    setAviso('');
    try {
      const documentos = (docs ?? []).filter((d) => elegidos.includes(llave(d))).map((d) => ({ tipo: d.tipo, ref: d.ref }));
      const r = await enviarDocumentos(clave, documentos, canales, para, mensaje);
      setEstado(r);
      const omitidos = r.omitidos ?? [];
      setAviso(omitidos.length
        ? `Enviando. No se manda a: ${omitidos.map((o) => `${o.contacto} por ${o.canal} (${o.motivo})`).join('; ')}`
        : 'Enviando en segundo plano.');
      setElegidos([]);
    } catch (e) {
      fallo(e, 'No se pudo enviar.');
    } finally {
      setOcupado(false);
    }
  };

  const listo = elegidos.length > 0 && para.length > 0 && canales.length > 0;
  return (
    <section className="card animate-in" aria-label="Enviar documentos" style={{ marginTop: 'var(--space-lg)', padding: 'var(--space-lg)', display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
      <h3 style={{ margin: 0, fontSize: '1rem', display: 'flex', alignItems: 'center', gap: 8 }}>
        <Send size={16} /> Enviar documentos al cliente
      </h3>
      {error && <ErrorAlert message={error} />}
      {aviso && <p role="status" style={{ margin: 0, color: 'var(--success)', fontSize: '0.85rem' }}>{aviso}</p>}
      <ContactosCliente clave={clave} contactos={contactos} onCambio={cargar} />
      <SubirExpediente clave={clave} onSubido={cargar} />
      {docs === null && !error && <span style={{ display: 'flex', gap: 8 }}><Loader size={16} className="spin" /> Cargando…</span>}
      {docs && docs.length === 0 && <p style={{ margin: 0, color: 'var(--text-muted)' }}>Este cliente aún no tiene documentos para enviar.</p>}
      {docs && docs.length > 0 && (
        <div style={{ maxHeight: 240, overflowY: 'auto', fontSize: '0.85rem', display: 'flex', flexDirection: 'column', gap: 2 }}>
          {docs.map((d) => (
            <label key={llave(d)} style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
              <input type="checkbox" checked={elegidos.includes(llave(d))} onChange={() => setElegidos(alternar(elegidos, llave(d)))} />
              <b>{d.nombre_tipo}</b> {d.descripcion}
              <span style={{ color: 'var(--text-muted)' }}>{d.fecha?.slice(0, 10)}{d.estado === 'cancelado' ? ' · cancelado' : ''}</span>
            </label>
          ))}
        </div>
      )}
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center', fontSize: '0.85rem' }}>
        <span>Para:</span>
        {contactos.filter((c) => c.activo).map((c) => (
          <label key={c.id} style={{ display: 'inline-flex', gap: 4 }}>
            <input type="checkbox" aria-label={`Enviar a ${c.nombre}`} checked={para.includes(c.id)} onChange={() => setPara(alternar(para, c.id))} /> {c.nombre}
          </label>
        ))}
        <span>Por:</span>
        {(['correo', 'whatsapp'] as Canal[]).map((c) => (
          <label key={c} style={{ display: 'inline-flex', gap: 4 }}>
            <input type="checkbox" aria-label={`Canal ${c}`} checked={canales.includes(c)} onChange={() => setCanales(alternar(canales, c))} /> {c === 'correo' ? 'Correo' : 'WhatsApp'}
          </label>
        ))}
      </div>
      <textarea aria-label="Mensaje" placeholder="Mensaje (opcional, sólo correo)" rows={2} value={mensaje} onChange={(e) => setMensaje(e.target.value)}
        style={{ background: 'var(--bg-input)', color: 'var(--text-primary)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', padding: 6 }} />
      <div>
        <button className="btn-primary" disabled={ocupado || !listo} onClick={() => void enviar()}>
          {ocupado ? <Loader size={14} className="spin" /> : <Send size={14} />} Enviar
        </button>
      </div>
      {estado && estado.envios.length > 0 && (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 640 }}>
            <thead>
              <tr><th style={thStyle}>Documento</th><th style={thStyle}>Canal</th><th style={thStyle}>Destino</th><th style={thStyle}>Estado</th><th style={thStyle} /></tr>
            </thead>
            <tbody>
              {estado.envios.map((e) => (
                <tr key={e.id}>
                  <td style={tdStyle}>{e.descripcion}</td>
                  <td style={tdStyle}>{e.canal === 'correo' ? 'Correo' : 'WhatsApp'}</td>
                  <td style={tdStyle}>{e.destino}</td>
                  <td style={tdStyle} title={e.error}>{ESTADO[e.estado] ?? e.estado}{e.error ? ` — ${e.error}` : ''}</td>
                  <td style={tdStyle}>
                    {e.estado !== 'pendiente' && (
                      <button className="btn-secondary" aria-label={`Reenviar ${e.id}`} onClick={() => void reenviar(clave, e.id).then(setEstado).catch((x: unknown) => fallo(x, 'No se pudo reenviar.'))}>
                        <RotateCcw size={12} />
                      </button>
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
