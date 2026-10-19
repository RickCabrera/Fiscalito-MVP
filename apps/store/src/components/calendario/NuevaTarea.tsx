/**
 * Alta de una tarea de la agenda del despacho y generación de tareas desde las obligaciones
 * del rango visible (P3-10). El responsable es un usuario del despacho.
 */

import { useState } from 'react';
import { ListPlus, Plus } from 'lucide-react';
import type { ClienteResumen } from '../../services/despachoApi';
import type { TareaNueva, UsuarioDespacho } from '../../services/agendaApi';

const campo: React.CSSProperties = {
  background: 'var(--bg-input)', color: 'var(--text-primary)', border: '1px solid var(--border)',
  borderRadius: 'var(--radius-sm)', padding: '6px 8px', fontSize: '0.82rem',
};

interface Props {
  clientes: ClienteResumen[];
  usuarios: UsuarioDespacho[];
  fechaInicial: string;
  ocupado: boolean;
  onCrear: (t: TareaNueva) => void;
  onGenerar: (responsable: string) => void;
}

export default function NuevaTarea({ clientes, usuarios, fechaInicial, ocupado, onCrear, onGenerar }: Props) {
  const [titulo, setTitulo] = useState('');
  const [fecha, setFecha] = useState(fechaInicial);
  const [cliente, setCliente] = useState('');
  const [responsable, setResponsable] = useState('');

  const crear = (e: React.FormEvent) => {
    e.preventDefault();
    if (!titulo.trim()) return;
    onCrear({ titulo: titulo.trim(), fecha, cliente: cliente || null, responsable_uid: responsable });
    setTitulo('');
  };

  return (
    <form onSubmit={crear} className="card" style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'flex-end' }}>
      <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: '0.72rem', flex: '2 1 200px' }}>
        Nueva tarea
        <input aria-label="Título de la tarea" style={campo} value={titulo}
          onChange={(e) => setTitulo(e.target.value)} placeholder="Ej. Pedir estados de cuenta" />
      </label>
      <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: '0.72rem' }}>
        Fecha
        <input type="date" aria-label="Fecha de la tarea" style={campo} value={fecha}
          onChange={(e) => setFecha(e.target.value)} />
      </label>
      <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: '0.72rem' }}>
        Cliente
        <select aria-label="Cliente de la tarea" style={campo} value={cliente} onChange={(e) => setCliente(e.target.value)}>
          <option value="">Del despacho</option>
          {clientes.map((c) => <option key={c.id} value={c.id}>{c.nombre}</option>)}
        </select>
      </label>
      <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: '0.72rem' }}>
        Responsable
        <select aria-label="Responsable de la tarea" style={campo} value={responsable}
          onChange={(e) => setResponsable(e.target.value)}>
          <option value="">Sin asignar</option>
          {usuarios.map((u) => <option key={u.uid} value={u.uid}>{u.nombre}</option>)}
        </select>
      </label>
      <button type="submit" className="btn-primary" disabled={ocupado || !titulo.trim()}
        style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
        <Plus size={14} /> Agregar
      </button>
      <button type="button" className="btn-secondary" disabled={ocupado} onClick={() => onGenerar(responsable)}
        title="Una tarea por cada obligación pendiente o vencida del periodo visible"
        style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
        <ListPlus size={14} /> Tareas desde vencimientos
      </button>
    </form>
  );
}
