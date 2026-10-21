/**
 * Contactos del cliente (P5-05): a quién se le mandan documentos, por correo y WhatsApp.
 *
 * El consentimiento de WhatsApp es explícito por contacto (el backend guarda cuándo y quién lo
 * registró); sin él, los envíos por WhatsApp a ese contacto se omiten con motivo.
 */

import { useState } from 'react';
import { Trash2, UserPlus } from 'lucide-react';
import {
  borrarContacto, guardarContacto, type Contacto, type ContactoCaptura,
} from '../../services/enviosDocumentosApi';
import ErrorAlert from '../common/ErrorAlert';

interface Props {
  clave: string;
  contactos: Contacto[];
  onCambio: () => void;
}

const VACIO: ContactoCaptura = {
  nombre: '', puesto: '', correo: '', telefono: '', consentimiento_whatsapp: false, activo: true,
};
const campo = { padding: '4px 6px', background: 'var(--bg-input)', color: 'var(--text-primary)', border: '1px solid var(--border)', borderRadius: 'var(--radius)' };

export default function ContactosCliente({ clave, contactos, onCambio }: Props) {
  const [nuevo, setNuevo] = useState<ContactoCaptura>(VACIO);
  const [error, setError] = useState('');
  const [ocupado, setOcupado] = useState(false);

  const hacer = async (fn: () => Promise<unknown>) => {
    setOcupado(true);
    setError('');
    try {
      await fn();
      onCambio();
      return true;
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo guardar el contacto.');
      return false;
    } finally {
      setOcupado(false);
    }
  };

  const agregar = async () => {
    if (await hacer(() => guardarContacto(clave, nuevo))) setNuevo(VACIO);
  };
  const consentir = (c: Contacto, valor: boolean) => void hacer(() => guardarContacto(clave, {
    nombre: c.nombre, puesto: c.puesto, correo: c.correo, telefono: c.telefono,
    consentimiento_whatsapp: valor, activo: c.activo }, c.id));

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: '0.85rem' }}>
      <strong>Contactos</strong>
      {error && <ErrorAlert message={error} />}
      {contactos.length === 0 && <span style={{ color: 'var(--text-muted)' }}>Sin contactos todavía.</span>}
      {contactos.map((c) => (
        <div key={c.id} style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
          <span style={{ minWidth: 160 }}>{c.nombre}{c.puesto && ` · ${c.puesto}`}</span>
          <span style={{ color: 'var(--text-secondary)' }}>{c.correo || 'sin correo'} · {c.telefono || 'sin celular'}</span>
          <label style={{ display: 'inline-flex', gap: 4, alignItems: 'center' }}>
            <input type="checkbox" checked={c.consentimiento_whatsapp} disabled={ocupado || !c.telefono}
              aria-label={`Consentimiento WhatsApp de ${c.nombre}`} onChange={(e) => consentir(c, e.target.checked)} />
            Acepta WhatsApp
          </label>
          <button className="btn-secondary" aria-label={`Borrar ${c.nombre}`} disabled={ocupado}
            onClick={() => void hacer(() => borrarContacto(clave, c.id))}><Trash2 size={12} /></button>
        </div>
      ))}
      <form aria-label="Nuevo contacto" onSubmit={(e) => { e.preventDefault(); void agregar(); }}
        style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
        <input style={campo} aria-label="Nombre del contacto" placeholder="Nombre" required value={nuevo.nombre} onChange={(e) => setNuevo({ ...nuevo, nombre: e.target.value })} />
        <input style={campo} aria-label="Correo del contacto" type="email" placeholder="correo@empresa.mx" value={nuevo.correo} onChange={(e) => setNuevo({ ...nuevo, correo: e.target.value })} />
        <input style={campo} aria-label="Celular del contacto" placeholder="521 55 1234 5678" value={nuevo.telefono} onChange={(e) => setNuevo({ ...nuevo, telefono: e.target.value })} />
        <label style={{ display: 'inline-flex', gap: 4, alignItems: 'center' }}>
          <input type="checkbox" checked={nuevo.consentimiento_whatsapp} onChange={(e) => setNuevo({ ...nuevo, consentimiento_whatsapp: e.target.checked })} />
          Dio su consentimiento para WhatsApp
        </label>
        <button type="submit" className="btn-secondary" disabled={ocupado}><UserPlus size={14} /> Agregar</button>
      </form>
    </div>
  );
}
