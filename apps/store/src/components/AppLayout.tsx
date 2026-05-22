import { Outlet, NavLink, useNavigate, Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useProfile } from '../context/ProfileContext';
import { LayoutDashboard, History, Scale, User, LogOut, Loader } from 'lucide-react';
import FiscalitoVoiceChat from './FiscalitoVoiceChat';
import ThemeToggle from './ThemeToggle';

export default function AppLayout() {
  const { user, loading: authLoading, signOut } = useAuth();
  const { isOnboardingComplete, loading: profileLoading } = useProfile();
  const navigate = useNavigate();

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

  const links = [
    { to: '/app', icon: <LayoutDashboard size={20} />, label: 'Dashboard', end: true },
    { to: '/app/store/fiscalito/use', icon: <Scale size={20} />, label: 'Fiscalito' },
    { to: '/app/historial', icon: <History size={20} />, label: 'Historial' },
    { to: '/app/profile', icon: <User size={20} />, label: 'Perfil' },
  ];

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
          {links.map((link) => (
            <NavLink key={link.to} to={link.to} end={link.end}
              style={({ isActive }) => ({
                display: 'flex', alignItems: 'center', gap: 12,
                padding: '12px 20px', margin: '0 12px',
                borderRadius: 'var(--radius-sm)',
                color: isActive ? 'var(--accent-active)' : 'var(--text-primary)',
                background: isActive ? 'var(--accent-active-bg)' : 'transparent',
                fontSize: '0.9rem', fontWeight: isActive ? 600 : 400,
                transition: 'all 0.2s', textDecoration: 'none',
              })}
            >
              {link.icon}{link.label}
            </NavLink>
          ))}
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
          {links.map((link) => (
            <NavLink key={link.to} to={link.to} end={link.end}
              title={link.label}
              style={({ isActive }) => ({
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                width: 44, height: 44, borderRadius: 'var(--radius-sm)',
                color: isActive ? 'var(--accent-active)' : 'var(--text-primary)',
                background: isActive ? 'var(--accent-active-bg)' : 'transparent',
                transition: 'all 0.2s', textDecoration: 'none',
              })}
            >
              {link.icon}
            </NavLink>
          ))}
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
        <Outlet />
      </main>
      <FiscalitoVoiceChat />
    </div>
  );
}
