/**
 * Dashboard del despacho (P5-02) — `/app/inicio`, la pantalla de entrada.
 *
 * Una sola llamada (`GET /dashboard`) con lo que hay que atender en la cartera VISIBLE (el
 * auxiliar sólo ve sus clientes asignados). Cada tarjeta y cada renglón llevan a su detalle;
 * los enlaces los decide el backend para que no haya dos copias de las rutas.
 */

import { useEffect, useState } from 'react';
import { AlertTriangle, Bell, Calendar, CloudDownload, FileCheck, KeyRound, ListTodo, Loader,
  Radio, Wallet } from 'lucide-react';
import { obtenerDashboard, type Dashboard } from '../services/dashboardApi';
import { pesos } from '../services/cobranzaApi';
import { COLOR_SEMAFORO, ETIQUETA_SEMAFORO } from '../services/semaforoSat';
import Tarjeta from '../components/dashboard/Tarjeta';
import ErrorAlert from '../components/common/ErrorAlert';

const ESTADO_SAT: Record<string, string> = {
  con_error: 'Con error', pausada: 'Pausada', sin_configurar: 'Sin configurar',
  en_proceso: 'En proceso', al_dia: 'Al día',
};

function fecha(iso: string | null): string {
  if (!iso) return '—';
  const [a, m, d] = iso.slice(0, 10).split('-');
  return `${d}/${m}/${a}`;
}

export default function InicioPage() {
  const [datos, setDatos] = useState<Dashboard | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let vivo = true;
    obtenerDashboard()
      .then((d) => { if (vivo) setDatos(d); })
      .catch((e) => { if (vivo) setError(e instanceof Error ? e.message : 'No se pudo cargar el dashboard.'); });
    return () => { vivo = false; };
  }, []);

  if (error) return <div style={{ padding: 24 }}><ErrorAlert message={error} /></div>;
  if (!datos) {
    return (
      <div style={{ padding: 24, display: 'flex', gap: 8, alignItems: 'center', color: 'var(--text-secondary)' }}>
        <Loader size={16} className="spin" /> Cargando el despacho…
      </div>
    );
  }
  const d = datos;
  const v = d.vencimientos;
  return (
    <div style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 16 }}>
      <h1 style={{ fontSize: '1.3rem' }}>Inicio</h1>
      <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
        {d.clientes} {d.clientes === 1 ? 'cliente' : 'clientes'} a la vista · al {fecha(d.hoy)}
      </p>
      <div style={{ display: 'grid', gap: 16, gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))' }}>
        <Tarjeta titulo="Vencimientos de la semana" icono={<Calendar size={18} />} enlace={v.enlace}
          cifra={v.semana} subtitulo={v.vencidas ? `${v.vencidas} vencidas sin presentar` : undefined}
          vacio="Nada vence esta semana."
          renglones={v.renglones.map((r) => ({
            id: `${r.cliente}-${r.clave}`, texto: `${r.cliente_nombre} · ${r.nombre}`,
            detalle: fecha(r.fecha_limite), enlace: r.enlace,
            tono: r.estado === 'vencida' ? 'peligro' : 'normal',
          }))} />
        <Tarjeta titulo="Alertas abiertas" icono={<Bell size={18} />} enlace={d.alertas.enlace}
          cifra={d.alertas.total} vacio="Sin alertas abiertas."
          renglones={(['alta', 'media', 'baja'] as const).filter((s) => d.alertas[s] > 0).map((s) => ({
            id: s, texto: `Severidad ${s}`, detalle: d.alertas[s], enlace: d.alertas.enlaces[s],
            tono: s === 'alta' ? 'peligro' : s === 'media' ? 'alerta' : 'normal',
          }))} />
        <Tarjeta titulo="Descarga SAT" icono={<CloudDownload size={18} />} enlace={d.descarga_sat.enlace}
          cifra={d.descarga_sat.resumen.con_error ?? 0}
          subtitulo="clientes con error en la descarga" vacio="Sin clientes."
          renglones={d.descarga_sat.renglones.map((r) => ({
            id: r.cliente, texto: r.cliente_nombre, detalle: ESTADO_SAT[r.estado] ?? r.estado,
            enlace: r.enlace,
            tono: r.estado === 'con_error' ? 'peligro' : r.estado === 'al_dia' ? 'ok' : 'alerta',
          }))} />
        <Tarjeta titulo="Opinión de cumplimiento" icono={<FileCheck size={18} />} enlace={d.opinion.enlace}
          cifra={d.opinion.rojo} subtitulo={`negativas · ${d.opinion.amarillo} por actualizar`}
          vacio="Sin clientes."
          renglones={d.opinion.renglones.map((r) => ({
            id: r.cliente, texto: r.cliente_nombre, enlace: r.enlace,
            detalle: <span style={{ color: COLOR_SEMAFORO[r.semaforo] }}>{ETIQUETA_SEMAFORO[r.semaforo]}</span>,
          }))} />
        <Tarjeta titulo="e.firma y CSD por vencer" icono={<KeyRound size={18} />}
          enlace={d.credenciales.enlace} cifra={d.credenciales.total}
          subtitulo={d.credenciales.vencidas ? `${d.credenciales.vencidas} ya vencidas` : 'en los próximos 30 días'}
          vacio="Ninguna vence en 30 días."
          renglones={d.credenciales.renglones.map((r) => ({
            id: `${r.cliente}-${r.tipo}-${r.vence}`, texto: `${r.cliente_nombre} · ${r.nombre}`,
            detalle: r.vencida ? 'Vencida' : `${r.dias} días`, enlace: r.enlace,
            tono: r.vencida ? 'peligro' : 'alerta',
          }))} />
        <Tarjeta titulo="Nóminas pendientes" icono={<Radio size={18} />}
          enlace={d.nominas.renglones[0]?.enlace ?? '/app/nomina'}
          cifra={d.nominas.por_cerrar + d.nominas.por_timbrar}
          subtitulo={`${d.nominas.por_cerrar} por cerrar · ${d.nominas.por_timbrar} por timbrar`}
          vacio="Todas las nóminas están cerradas y timbradas."
          renglones={d.nominas.renglones.map((r) => ({
            id: String(r.id), texto: `${r.cliente_nombre} · ${fecha(r.inicio)}–${fecha(r.fin)}`,
            detalle: r.accion === 'timbrar' ? 'Por timbrar' : 'Por cerrar', enlace: r.enlace,
            tono: 'alerta',
          }))} />
        <Tarjeta titulo="Mis pendientes" icono={<ListTodo size={18} />} enlace={d.agenda.enlace}
          cifra={d.agenda.total} subtitulo={d.agenda.atrasadas ? `${d.agenda.atrasadas} atrasadas` : 'esta semana'}
          vacio="No tienes tareas asignadas esta semana."
          renglones={d.agenda.renglones.map((r) => ({
            id: String(r.id), texto: r.cliente_nombre ? `${r.titulo} · ${r.cliente_nombre}` : r.titulo,
            detalle: fecha(r.fecha), enlace: r.enlace, tono: r.atrasada ? 'peligro' : 'normal',
          }))} />
        {d.cobranza && (
          <Tarjeta titulo="Cuentas por cobrar vencidas" icono={<Wallet size={18} />}
            enlace={d.cobranza.enlace} cifra={pesos(d.cobranza.vencido)}
            subtitulo={`${d.cobranza.clientes} clientes con saldo vencido`}
            vacio="Ningún cliente tiene saldo vencido."
            renglones={d.cobranza.renglones.map((r) => ({
              id: r.cliente, texto: r.cliente_nombre, detalle: pesos(r.vencido), enlace: r.enlace,
              tono: 'peligro',
            }))} />
        )}
      </div>
      {d.clientes === 0 && (
        <p style={{ display: 'flex', gap: 6, alignItems: 'center', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
          <AlertTriangle size={14} /> Aún no tienes clientes a la vista. Da de alta uno en Clientes
          (o pide al dueño del despacho que te asigne).
        </p>
      )}
    </div>
  );
}
