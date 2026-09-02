import { Outlet, Link, useLocation, useNavigate, Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useProfile } from '../context/ProfileContext';
import { LayoutDashboard, History, Scale, User, LogOut, Loader, Radio, Users, Calendar, Contact, Fingerprint } from 'lucide-react';
import { esContador, getSidebarLinks, navActivo, type NavId } from '../services/navigation';
import { useClienteActivo } from '../context/clienteActivoStore';
// DEMO E-02: barra de cliente activo, sólo en las rutas con alcance de cliente.
import SelectorCliente from './SelectorCliente';
import FiscalitoVoiceChat from './FiscalitoVoiceChat';
import ThemeToggle from './ThemeToggle';

/** Icono de cada entrada del sidebar. La lista de entradas y su orden viven en
 *  `services/navigation.ts` (modulo puro); aqui solo se les pone cara. */
const ICONOS: Record<NavId, React.ReactNode> = {
  dashboard: <LayoutDashboard size={20} />,
  fiscalito: <Scale size={20} />,
  historial: <History size={20} />,
  nomina: <Radio size={20} />,
  clientes: <Users size={20} />,
  // R-05. `Users` ya lo usa Clientes: repetirlo haria el sidebar ilegible
  // de un vistazo, que es justo para lo que sirve un icono.
  empleados: <Contact size={20} />,
  dispositivos: <Fingerprint size={20} />,
  calendario: <Calendar size={20} />,
  perfil: <User size={20} />,
};

export default function AppLayout() {
  const { user, loading: authLoading, signOut } = useAuth();
  const { isOnboardingComplete, loading: profileLoading, profile } = useProfile();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  // E-06: el sidebar de un despacho dice EN QUÉ CLIENTE está. El contexto se
  // lee siempre (los hooks no pueden ir tras un `if`) y sólo se pinta para un
  // contador; para un contribuyente la cartera está vacía.
  const { cliente } = useClienteActivo();

  if (authLoading || profileLoading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100vh' }}>
        <Loader size={28} className="spin" color="var(--accent-active)" />
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  if (!isOnboardingComplete()) {
    return <Navigate to="/app/onboarding" replace />;
  }

  const handleSignOut = async () => {
    await signOut();
    navigate('/');
  };

  const links = getSidebarLinks(profile.contributorType);
  const esDespacho = esContador(profile.contributorType);
  /** Nombre del cliente bajo la entrada "Nómina": es de quién es esa nómina. */
  const subEtiqueta = (id: NavId): string | null =>
    esDespacho && id === 'nomina' && cliente ? cliente.nombre : null;

  const sidebarBase: React.CSSProperties = {
    background: 'var(--bg-surface)',
    borderRight: '1px solid var(--border)',
    display: 'flex',
    flexDirection: 'column',
    position: 'fixed',
    top: 0, left: 0, bottom: 0,
    zIndex: 10,
  };

  return (
    <div style={{ display: 'flex', minHeight: '100vh' }}>
      {/* Sidebar — full (desktop) */}
      <aside className="sidebar-full" style={{ ...sidebarBase, width: 240, padding: '24px 0' }}>
        <div style={{ padding: '0 20px', marginBottom: 40 }}>
          <div style={{ fontSize: '1.2rem', fontWeight: 700, letterSpacing: -0.5 }}>
            <span className="gradient-text">Fiscalito</span>{' '}
            <span style={{ color: 'var(--text-muted)', fontWeight: 400 }}>Store</span>
          </div>
        </div>
        <nav style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 4 }}>
          {links.map((link) => {
            // E-06: el resaltado lo decide `navActivo`, no `NavLink`. Con
            // `NavLink` la nómina de un cliente (`/app/clientes/{id}/nomina`)
            // encendía "Clientes" y dejaba "Nómina" apagada — y el
            // `aria-current` habría seguido diciendo "Clientes" aunque el color
            // cambiara, que es por lo que tampoco basta con pisar el estilo.
            const activo = navActivo(link, pathname);
            const cliente = subEtiqueta(link.id);
            return (
              <Link key={link.id} to={link.to}
                aria-current={activo ? 'page' : undefined}
                className={`nav-item${activo ? ' nav-item-active' : ''}`}
                style={{
                  display: 'flex', alignItems: 'center', gap: 12,
                  padding: '12px 20px', margin: '0 12px',
                  borderRadius: 'var(--radius-sm)',
                  color: activo ? 'var(--accent-active)' : 'var(--text-primary)',
                  background: activo ? 'var(--accent-active-bg)' : 'transparent',
                  fontSize: '0.9rem', fontWeight: activo ? 600 : 400,
                  transition: 'all 0.2s', textDecoration: 'none',
                }}
              >
                {ICONOS[link.id]}
                <span style={{ display: 'flex', flexDirection: 'column', minWidth: 0 }}>
                  {link.label}
                  {cliente && (
                    // `data-cliente` marca lo que NO es la etiqueta del enlace:
                    // el test de E-01 asserta la lista exacta de entradas del
                    // sidebar y tiene que poder descontar este renglón.
                    <span data-cliente="" style={{
                      fontSize: '0.72rem', fontWeight: 400, color: 'var(--text-secondary)',
                      overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                    }}>
                      {cliente}
                    </span>
                  )}
                </span>
              </Link>
            );
          })}
        </nav>
        <div style={{ padding: '16px 12px', borderTop: '1px solid var(--border)', marginTop: 'auto', display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div style={{ fontSize: '0.78rem', color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', padding: '0 8px', textAlign: 'center' }}>
            {user?.email}
          </div>
          <ThemeToggle />
          <button onClick={handleSignOut}
            style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, padding: '9px 12px', background: 'transparent', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', color: 'var(--text-primary)', fontSize: '0.85rem', fontWeight: 500, cursor: 'pointer', transition: 'all 0.2s', width: '100%' }}
            onMouseOver={(e) => { e.currentTarget.style.background = 'var(--danger-bg)'; e.currentTarget.style.borderColor = 'var(--danger)'; e.currentTarget.style.color = 'var(--danger)'; }}
            onMouseOut={(e) => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.color = 'var(--text-primary)'; }}
          >
            <LogOut size={15} />Cerrar sesión
          </button>
        </div>
      </aside>

      {/* Sidebar — mini (mobile) */}
      <aside className="sidebar-mini" style={{ ...sidebarBase, width: 64, padding: '20px 0', display: 'none' }}>
        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 32 }}>
          <span className="gradient-text" style={{ fontSize: '1.1rem', fontWeight: 800 }}>F</span>
        </div>
        <nav style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 4, alignItems: 'center' }}>
          {links.map((link) => {
            const activo = navActivo(link, pathname);
            const cliente = subEtiqueta(link.id);
            return (
              <Link key={link.id} to={link.to}
                // Sin espacio para el nombre del cliente, va en el tooltip: en
                // móvil es la única pista de a qué cliente lleva.
                title={cliente ? `${link.label} · ${cliente}` : link.label}
                aria-current={activo ? 'page' : undefined}
                className={`nav-item${activo ? ' nav-item-active' : ''}`}
                style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  width: 44, height: 44, borderRadius: 'var(--radius-sm)',
                  color: activo ? 'var(--accent-active)' : 'var(--text-primary)',
                  background: activo ? 'var(--accent-active-bg)' : 'transparent',
                  transition: 'all 0.2s', textDecoration: 'none',
                }}
              >
                {ICONOS[link.id]}
              </Link>
            );
          })}
        </nav>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4, padding: '12px 0', borderTop: '1px solid var(--border)' }}>
          <ThemeToggle mini />
          <button onClick={handleSignOut} title="Cerrar sesión"
            style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', width: 44, height: 44, background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', borderRadius: 'var(--radius-sm)', transition: 'all 0.2s' }}
            onMouseOver={(e) => { e.currentTarget.style.color = 'var(--danger)'; }}
            onMouseOut={(e) => { e.currentTarget.style.color = 'var(--text-muted)'; }}
          >
            <LogOut size={18} />
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="main-with-sidebar" style={{ flex: 1, marginLeft: 240, minHeight: '100vh' }}>
        <SelectorCliente />
        <Outlet />
      </main>
      <FiscalitoVoiceChat />
    </div>
  );
}
