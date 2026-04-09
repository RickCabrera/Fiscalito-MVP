import { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { SERVICES } from '../services/storeServices';
import { limpiarDuplicados, borrarTodasDeclaraciones } from '../services/declaracionesHistory';
import { Settings, Users, Activity, Package, Database, RefreshCw, Trash2, Loader } from 'lucide-react';

export default function AdminPage() {
  const { user } = useAuth();
  const [limpiando, setLimpiando] = useState(false);
  const [borrando, setBorrando] = useState(false);
  const [mensajeAdmin, setMensajeAdmin] = useState('');

  const mostrarMensaje = (msg: string) => {
    setMensajeAdmin(msg);
    setTimeout(() => setMensajeAdmin(''), 4000);
  };

  const handleLimpiar = async () => {
    if (!user?.uid) return;
    if (!window.confirm('¿Limpiar declaraciones duplicadas? Se conservará solo la más reciente de cada periodo.')) return;
    setLimpiando(true);
    setMensajeAdmin('');
    try {
      const eliminados = await limpiarDuplicados(user.uid);
      mostrarMensaje(eliminados > 0 ? `Se eliminaron ${eliminados} duplicado${eliminados > 1 ? 's' : ''}` : 'No se encontraron duplicados');
    } catch {
      mostrarMensaje('Error al limpiar duplicados');
    } finally {
      setLimpiando(false);
    }
  };

  const handleBorrarTodo = async () => {
    if (!user?.uid) return;
    if (!window.confirm('⚠️ ¿Estás seguro? Se eliminarán TODOS tus cálculos fiscales guardados. Esta acción es IRREVERSIBLE.')) return;
    const confirmacion = window.prompt('Escribe BORRAR para confirmar:');
    if (confirmacion !== 'BORRAR') return;
    setBorrando(true);
    setMensajeAdmin('');
    try {
      const eliminados = await borrarTodasDeclaraciones(user.uid);
      mostrarMensaje(eliminados > 0 ? `Se eliminaron ${eliminados} registro${eliminados > 1 ? 's' : ''}` : 'No había datos que borrar');
    } catch {
      mostrarMensaje('Error al borrar datos');
    } finally {
      setBorrando(false);
    }
  };

  return (
    <div className="page-container">
      <div className="page-header animate-in">
        <h1>Panel de administracion</h1>
        <p>Gestion interna de Fiscalito Store.</p>
      </div>

      {/* Stats */}
      <div className="animate-in" style={{ animationDelay: '0.1s', display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 32 }}>
        {[
          { icon: <Package size={20} />, label: 'Servicios totales', value: SERVICES.length.toString(), color: 'var(--teal-light)' },
          { icon: <Activity size={20} />, label: 'Servicios activos', value: SERVICES.filter(s => s.status === 'active').length.toString(), color: 'var(--success)' },
          { icon: <Users size={20} />, label: 'Usuarios registrados', value: '—', color: 'var(--purple-light)' },
          { icon: <Settings size={20} />, label: 'API uptime', value: '99.9%', color: 'var(--teal-light)' },
        ].map((stat, i) => (
          <div key={i} className="card" style={{ textAlign: 'center', padding: 20 }}>
            <div style={{ color: stat.color, marginBottom: 8, display: 'flex', justifyContent: 'center' }}>{stat.icon}</div>
            <div style={{ fontSize: '1.6rem', fontWeight: 700, fontFamily: "'JetBrains Mono', monospace", color: stat.color }}>{stat.value}</div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: 4 }}>{stat.label}</div>
          </div>
        ))}
      </div>

      {/* Services management */}
      <div className="card animate-in" style={{ animationDelay: '0.2s' }}>
        <h3 style={{ fontSize: '1.05rem', fontWeight: 600, marginBottom: 20 }}>Servicios en el marketplace</h3>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border)' }}>
              {['Servicio', 'Categoria', 'Status', 'API', 'Acciones'].map(h => (
                <th key={h} style={{
                  textAlign: 'left', padding: '10px 12px', fontSize: '0.75rem',
                  color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 1, fontWeight: 500,
                }}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {SERVICES.map((service) => (
              <tr key={service.id} style={{ borderBottom: '1px solid var(--border)' }}>
                <td style={{ padding: '14px 12px', display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span style={{ fontSize: '1.2rem' }}>{service.icon}</span>
                  <div>
                    <div style={{ fontWeight: 600, fontSize: '0.9rem' }}>{service.name}</div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{service.tagline}</div>
                  </div>
                </td>
                <td style={{ padding: '14px 12px', fontSize: '0.85rem', color: 'var(--text-secondary)', textTransform: 'capitalize' }}>
                  {service.category}
                </td>
                <td style={{ padding: '14px 12px' }}>
                  <span style={{
                    padding: '3px 10px', borderRadius: 'var(--radius-full)',
                    fontSize: '0.7rem', fontWeight: 600,
                    background: service.status === 'active' ? 'rgba(46,204,113,0.12)' : 'rgba(224,160,96,0.12)',
                    color: service.status === 'active' ? 'var(--success)' : 'var(--warning)',
                  }}>
                    {service.status === 'active' ? 'Activo' : 'Pendiente'}
                  </span>
                </td>
                <td style={{ padding: '14px 12px' }}>
                  {service.apiEndpoint ? (
                    <code style={{ fontFamily: "'JetBrains Mono'", fontSize: '0.75rem', color: 'var(--teal-light)' }}>
                      {service.apiEndpoint}
                    </code>
                  ) : (
                    <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>—</span>
                  )}
                </td>
                <td style={{ padding: '14px 12px' }}>
                  <button className="btn-secondary" style={{ padding: '6px 14px', fontSize: '0.75rem' }}>
                    Editar
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Mantenimiento de datos */}
      <div className="card animate-in" style={{ animationDelay: '0.3s', marginTop: 32 }}>
        <h3 style={{ fontSize: '1.05rem', fontWeight: 600, marginBottom: 6, display: 'flex', alignItems: 'center', gap: 10 }}>
          <Database size={18} color="var(--teal-light)" />
          Mantenimiento de datos
        </h3>
        <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginBottom: 20 }}>
          Herramientas para gestionar los datos de Fiscalito almacenados en tu cuenta.
        </p>

        <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginBottom: 16 }}>
          {/* Limpiar duplicados */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <button
              onClick={handleLimpiar}
              disabled={limpiando}
              style={{
                display: 'inline-flex', alignItems: 'center', gap: 8,
                background: 'none', border: '1px solid var(--border)',
                borderRadius: 'var(--radius-xs)', padding: '8px 16px',
                color: 'var(--text-secondary)', fontSize: '0.82rem',
                cursor: limpiando ? 'default' : 'pointer',
                opacity: limpiando ? 0.6 : 1,
              }}
            >
              {limpiando ? <Loader size={14} className="spin" /> : <RefreshCw size={14} />}
              Limpiar duplicados del historial
            </button>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', maxWidth: 320 }}>
              Consolida declaraciones duplicadas, conservando solo la más reciente por periodo
            </span>
          </div>

          {/* Borrar todo */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <button
              onClick={handleBorrarTodo}
              disabled={borrando}
              style={{
                display: 'inline-flex', alignItems: 'center', gap: 8,
                background: 'none', border: '1px solid var(--danger)',
                borderRadius: 'var(--radius-xs)', padding: '8px 16px',
                color: 'var(--danger)', fontSize: '0.82rem',
                cursor: borrando ? 'default' : 'pointer',
                opacity: borrando ? 0.6 : 1,
              }}
              onMouseEnter={(e) => { if (!borrando) (e.currentTarget.style.background = 'rgba(231,76,60,0.1)'); }}
              onMouseLeave={(e) => { e.currentTarget.style.background = 'none'; }}
            >
              {borrando ? <Loader size={14} className="spin" /> : <Trash2 size={14} />}
              Borrar todos los datos de Fiscalito
            </button>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', maxWidth: 320 }}>
              Elimina TODAS las declaraciones, DIOT, retenciones, multi-periodo, estado de cuenta y deducciones guardadas
            </span>
          </div>
        </div>

        {mensajeAdmin && (
          <div style={{
            fontSize: '0.82rem', padding: '8px 14px', borderRadius: 'var(--radius-xs)',
            background: mensajeAdmin.startsWith('Error') ? 'rgba(231,76,60,0.08)' : 'rgba(46,204,113,0.08)',
            border: `1px solid ${mensajeAdmin.startsWith('Error') ? 'rgba(231,76,60,0.2)' : 'rgba(46,204,113,0.2)'}`,
            color: mensajeAdmin.startsWith('Error') ? 'var(--danger)' : 'var(--success)',
          }}>
            {mensajeAdmin}
          </div>
        )}
      </div>
    </div>
  );
}
