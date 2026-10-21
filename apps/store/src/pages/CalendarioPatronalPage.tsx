/**
 * Calendario de la cartera y agenda del despacho (P3-10, absorbe E-07 y F1-06). Ruta
 * `/app/calendario`.
 *
 * Une en una vista los vencimientos FISCALES de cada cliente (por su régimen, con la prórroga
 * por sexto dígito del RFC y el día 17 inhábil corregido), los PATRONALES (los del IMSS con su
 * propia regla de viernes e inhábil, F1-06) y los vencimientos de e.firma y CSD, más las tareas
 * del despacho. Todas las fechas las calcula el backend (`GET /calendario/cartera`); aquí sólo
 * se filtran y se pintan. El nombre del archivo se conserva para no mover la ruta.
 *
 * `hoy` SE INYECTA: "vencida" y "hoy" dependen del reloj, y los tests lo fijan.
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import { CalendarDays, ChevronLeft, ChevronRight, Loader } from 'lucide-react';
import { useSearchParams } from 'react-router-dom';
import { useClienteActivo } from '../context/clienteActivoStore';
import {
  actualizarTarea, crearTarea, generarTareas, iso, marcarObligacion, obtenerCalendario,
  rangoDe, sumarDias, usuariosDespacho,
  type CalendarioCartera, type ObligacionCartera, type TareaAgenda, type TareaNueva,
  type UsuarioDespacho, type Vista,
} from '../services/agendaApi';
import VistaCalendario from '../components/calendario/VistaCalendario';
import NuevaTarea from '../components/calendario/NuevaTarea';
import ErrorAlert from '../components/common/ErrorAlert';

const campo: React.CSSProperties = {
  background: 'var(--bg-input)', color: 'var(--text-primary)', border: '1px solid var(--border)',
  borderRadius: 'var(--radius-sm)', padding: '6px 8px', fontSize: '0.82rem',
};
const SIGUIENTE_ESTADO: Record<TareaAgenda['estado'], TareaAgenda['estado']> = {
  pendiente: 'en_proceso', en_proceso: 'hecha', hecha: 'pendiente',
};

export default function CalendarioPatronalPage({ hoy = new Date() }: { hoy?: Date }) {
  const { clientes } = useClienteActivo();
  // P5-02: el dashboard entra con filtros en la URL (`?cliente=`, `?tipo=`, `?vista=agenda`).
  const [params] = useSearchParams();
  const [vista, setVista] = useState<Vista>(() =>
    (['semana', 'mes', 'agenda'] as string[]).includes(params.get('vista') ?? '')
      ? params.get('vista') as Vista : 'semana');
  const [ancla, setAncla] = useState<Date>(hoy);
  const [cliente, setCliente] = useState(() => params.get('cliente') ?? '');
  const [tipo, setTipo] = useState(() => params.get('tipo') ?? '');
  const [responsable, setResponsable] = useState('');
  const [datos, setDatos] = useState<CalendarioCartera | null>(null);
  const [usuarios, setUsuarios] = useState<UsuarioDespacho[]>([]);
  const [error, setError] = useState('');
  const [ocupado, setOcupado] = useState(false);

  const { desde, hasta } = useMemo(() => rangoDe(vista, ancla), [vista, ancla]);

  const cargar = useCallback(() => {
    obtenerCalendario({ desde: iso(desde), hasta: iso(hasta), cliente, tipo, responsable })
      .then((d) => { setError(''); setDatos(d); })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : 'No se pudo cargar el calendario.'));
  }, [desde, hasta, cliente, tipo, responsable]);

  useEffect(() => { cargar(); }, [cargar]);
  useEffect(() => {
    usuariosDespacho().then((r) => setUsuarios(r.usuarios)).catch(() => setUsuarios([]));
  }, []);

  const hacer = async (fn: () => Promise<unknown>) => {
    setOcupado(true);
    setError('');
    try {
      await fn();
      cargar();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo completar.');
    } finally {
      setOcupado(false);
    }
  };

  const marcar = (o: ObligacionCartera) => hacer(() =>
    marcarObligacion(o.cliente, o.clave, o.estado === 'presentada' ? 'pendiente' : 'presentada'));
  const avanzarTarea = (t: TareaAgenda) => hacer(() => actualizarTarea(t.id, { estado: SIGUIENTE_ESTADO[t.estado] }));
  const nueva = (t: TareaNueva) => hacer(() => crearTarea(t));
  const generar = (resp: string) => hacer(() =>
    generarTareas({ desde: iso(desde), hasta: iso(hasta), cliente: cliente || undefined, responsable_uid: resp }));

  const mover = (paso: number) => setAncla((a) => (vista === 'semana'
    ? sumarDias(a, 7 * paso) : new Date(a.getFullYear(), a.getMonth() + paso, 1)));

  // El filtro por tipo es de obligaciones: con uno puesto, las tareas no se pintan.
  const tareas = tipo ? [] : datos?.tareas ?? [];
  const resumen = datos ? {
    vencidas: datos.obligaciones.filter((o) => o.estado === 'vencida').length,
    pendientes: datos.obligaciones.filter((o) => o.estado === 'pendiente').length,
    presentadas: datos.obligaciones.filter((o) => o.estado === 'presentada').length,
  } : null;

  return (
    <div style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 14 }}>
      <h1 style={{ fontSize: '1.3rem', display: 'flex', alignItems: 'center', gap: 10 }}>
        <CalendarDays size={20} /> Calendario de la cartera
      </h1>
      <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', margin: 0 }}>
        Vencimientos fiscales (con la prórroga por sexto dígito del RFC y el día inhábil corregido),
        patronales y de e.firma/CSD de todos tus clientes, más las tareas del despacho.
      </p>
      <div className="card" style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
        <div role="group" aria-label="Vista" style={{ display: 'flex', gap: 4 }}>
          {(['semana', 'mes', 'agenda'] as Vista[]).map((v) => (
            <button key={v} className={vista === v ? 'btn-primary' : 'btn-secondary'} aria-pressed={vista === v}
              onClick={() => setVista(v)} style={{ padding: '4px 12px', fontSize: '0.8rem', textTransform: 'capitalize' }}>
              {v}
            </button>
          ))}
        </div>
        <button className="btn-secondary" aria-label="Anterior" onClick={() => mover(-1)} style={{ padding: '4px 8px' }}><ChevronLeft size={14} /></button>
        <span style={{ fontSize: '0.85rem', minWidth: 180, textAlign: 'center' }}>{iso(desde)} — {iso(hasta)}</span>
        <button className="btn-secondary" aria-label="Siguiente" onClick={() => mover(1)} style={{ padding: '4px 8px' }}><ChevronRight size={14} /></button>
        <button className="btn-secondary" onClick={() => setAncla(hoy)} style={{ padding: '4px 10px', fontSize: '0.8rem' }}>Hoy</button>
        <select aria-label="Filtrar por cliente" style={campo} value={cliente} onChange={(e) => setCliente(e.target.value)}>
          <option value="">Todos los clientes</option>
          {clientes.map((c) => <option key={c.id} value={c.id}>{c.nombre}</option>)}
        </select>
        <select aria-label="Filtrar por tipo" style={campo} value={tipo} onChange={(e) => setTipo(e.target.value)}>
          <option value="">Fiscal, patronal y credenciales</option>
          <option value="fiscal">Fiscal</option>
          <option value="patronal">Patronal</option>
          <option value="credencial">e.firma / CSD</option>
        </select>
        <select aria-label="Filtrar por responsable" style={campo} value={responsable} onChange={(e) => setResponsable(e.target.value)}>
          <option value="">Cualquier responsable</option>
          {usuarios.map((u) => <option key={u.uid} value={u.uid}>{u.nombre}</option>)}
        </select>
      </div>
      {resumen && (
        <p style={{ fontSize: '0.8rem', margin: 0, color: 'var(--text-secondary)' }}>
          <span style={{ color: 'var(--danger)' }}>{resumen.vencidas} vencidas</span> ·{' '}
          <span style={{ color: 'var(--warning)' }}>{resumen.pendientes} pendientes</span> ·{' '}
          <span style={{ color: 'var(--success)' }}>{resumen.presentadas} presentadas</span> ·{' '}
          {tareas.length} tareas
        </p>
      )}
      {error && <ErrorAlert message={error} />}
      {!datos && !error && <Loader size={20} className="spin" aria-label="Cargando calendario" />}
      {datos && (
        <VistaCalendario vista={vista} desde={desde} hasta={hasta} hoy={hoy}
          obligaciones={datos.obligaciones} tareas={tareas} onMarcar={marcar} onTarea={avanzarTarea} />
      )}
      <NuevaTarea clientes={clientes} usuarios={usuarios} fechaInicial={iso(hoy)} ocupado={ocupado}
        onCrear={nueva} onGenerar={generar} />
    </div>
  );
}
